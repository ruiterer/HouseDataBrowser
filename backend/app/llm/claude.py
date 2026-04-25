"""Claude provider via the Anthropic SDK.

Defaults: claude-opus-4-7 with adaptive thinking + effort=high. The system prompt
and tool list are marked with `cache_control: ephemeral` so the (large) schema
overview rides the prompt cache at ~0.1x cost on subsequent turns.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import anthropic

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


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set; cannot use the Claude provider."
            )
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self._effort = settings.llm_effort
        self._max_tokens = settings.llm_max_tokens

    async def chat(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        model: str | None = None,
        effort: str | None = None,
    ) -> AssistantTurn:
        api_messages = [_to_api_message(m) for m in messages]
        api_tools = [_to_api_tool(t) for t in tools]
        if api_tools:
            api_tools[-1]["cache_control"] = {"type": "ephemeral"}

        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": self._max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": api_messages,
            "tools": api_tools,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort or self._effort},
        }

        # Use streaming + get_final_message() so high max_tokens (64K) doesn't
        # hit the SDK's non-streaming HTTP-timeout guard. We don't actually
        # surface tokens to the UI per-token — the agent loop emits per-step
        # events instead.
        async with self._client.messages.stream(**kwargs) as stream:
            response = await stream.get_final_message()

        content: list[TextBlock | ToolUseBlock] = []
        for block in response.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(
                    ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
                )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": getattr(
                response.usage, "cache_creation_input_tokens", 0
            )
            or 0,
            "cache_read_input_tokens": getattr(
                response.usage, "cache_read_input_tokens", 0
            )
            or 0,
        }
        logger.debug("claude usage: %s, stop=%s", usage, response.stop_reason)

        return AssistantTurn(
            content=content,
            stop_reason=response.stop_reason or "end_turn",
            usage=usage,
        )


def _to_api_message(m: Message) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for b in m.content:
        if isinstance(b, TextBlock):
            blocks.append({"type": "text", "text": b.text})
        elif isinstance(b, ToolUseBlock):
            blocks.append(
                {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            )
        elif isinstance(b, ToolResultBlock):
            blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.tool_use_id,
                    "content": b.content,
                    "is_error": b.is_error,
                }
            )
    return {"role": m.role, "content": blocks}


def _to_api_tool(t: ToolDef) -> dict[str, Any]:
    d = asdict(t)
    return {
        "name": d["name"],
        "description": d["description"],
        "input_schema": d["input_schema"],
    }
