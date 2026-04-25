"""Ollama provider — talks to a local Ollama server (e.g. on a Raspberry Pi 5).

Uses Ollama's native /api/chat endpoint, which natively supports tool calling
on models that advertise it (qwen2.5, llama3.1+, hermes3, mistral-nemo, etc.).

We map our internal Message/ContentBlock structure to Ollama's flatter shape:
  - assistant turns with ToolUseBlocks → role=assistant + tool_calls[]
  - user turns with ToolResultBlocks → one role=tool message per result
  - text content stays as plain content strings

Ollama does not understand `effort` or adaptive thinking — those kwargs are
ignored. The tool schema is the same JSON Schema we send to Anthropic.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Any

import httpx

from app.config import Settings
from app.llm.provider import (
    AssistantTurn,
    LLMProvider,
    Message,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUseBlock,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.ollama_model
        self._host = settings.ollama_host.rstrip("/")
        # Small models on a Pi CPU are slow; allow up to 10 minutes per call.
        self._client = httpx.AsyncClient(timeout=600.0)

    async def chat(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        model: str | None = None,
        effort: str | None = None,
    ) -> AssistantTurn:
        ollama_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            ollama_messages.extend(self._to_ollama(m))

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": ollama_messages,
            "tools": [_tool_def_to_ollama(t) for t in tools],
            "stream": False,
        }

        try:
            r = await self._client.post(f"{self._host}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("ollama HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
            raise
        except httpx.HTTPError as exc:
            logger.warning("ollama request failed: %s", exc)
            raise

        return _from_ollama_response(r.json())

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _to_ollama(m: Message) -> list[dict[str, Any]]:
        if m.role == "user":
            return _user_to_ollama(m)
        return _assistant_to_ollama(m)


def _user_to_ollama(m: Message) -> list[dict[str, Any]]:
    """User turns may carry text or tool_results — split into separate messages.

    Ollama expects each tool_result to be its own role=tool message. If the user
    sent text alongside (rare in our agent loop), we append a role=user message
    after the tool messages.
    """
    out: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for b in m.content:
        if isinstance(b, TextBlock):
            if b.text:
                text_parts.append(b.text)
        elif isinstance(b, ToolResultBlock):
            out.append(
                {
                    "role": "tool",
                    "content": b.content,
                    # Some Ollama-compatible models look at tool_call_id to match
                    # the request; harmless when ignored.
                    "tool_call_id": b.tool_use_id,
                }
            )
    if text_parts:
        out.append({"role": "user", "content": "\n\n".join(text_parts)})
    return out


def _assistant_to_ollama(m: Message) -> list[dict[str, Any]]:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for b in m.content:
        if isinstance(b, TextBlock):
            if b.text:
                text_parts.append(b.text)
        elif isinstance(b, ToolUseBlock):
            tool_calls.append(
                {
                    "id": b.id,
                    "function": {"name": b.name, "arguments": b.input},
                }
            )
    msg: dict[str, Any] = {"role": "assistant", "content": "\n\n".join(text_parts)}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return [msg]


def _tool_def_to_ollama(t: ToolDef) -> dict[str, Any]:
    d = asdict(t)
    return {
        "type": "function",
        "function": {
            "name": d["name"],
            "description": d["description"],
            "parameters": d["input_schema"],
        },
    }


def _from_ollama_response(body: dict[str, Any]) -> AssistantTurn:
    msg = body.get("message") or {}
    content: list[TextBlock | ToolUseBlock] = []

    text = msg.get("content") or ""
    if text.strip():
        content.append(TextBlock(text=text))

    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        # Smaller Ollama models sometimes return arguments as a JSON-encoded
        # string instead of an object; coerce to dict.
        args = fn.get("arguments")
        if isinstance(args, str):
            import json as _json

            try:
                args = _json.loads(args)
            except Exception:
                args = {}
        content.append(
            ToolUseBlock(
                id=tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}",
                name=fn.get("name", ""),
                input=args or {},
            )
        )

    has_tools = any(isinstance(b, ToolUseBlock) for b in content)
    done_reason = body.get("done_reason") or "stop"
    if has_tools:
        stop_reason = "tool_use"
    elif done_reason == "stop":
        stop_reason = "end_turn"
    elif done_reason == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = done_reason

    usage = {
        "input_tokens": int(body.get("prompt_eval_count") or 0),
        "output_tokens": int(body.get("eval_count") or 0),
    }
    return AssistantTurn(content=content, stop_reason=stop_reason, usage=usage)
