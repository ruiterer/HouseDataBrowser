"""Claude Code provider via the Claude Agent SDK.

Replaces the direct Anthropic API provider (session 2026-08-22): the Claude
Code engine runs as a bundled-binary subprocess and authenticates with the
owner's Claude subscription through CLAUDE_CODE_OAUTH_TOKEN (generated once
with `claude setup-token`), so no API credits are needed.

Claude Code drives its own agent loop, so this provider implements the
`runs_own_loop` capability from app.llm.provider instead of per-turn chat():
the agent loop delegates the whole episode to `run_episode()`. HDB's three
tools are registered as in-process MCP tools whose execution is a callback
supplied by the loop — every InfluxQL query still passes through the safety
filter. All built-in Claude Code tools (Bash, Read, Write, ...) are disabled.

Conversation history arrives collapsed (summary + query per prior turn, see
chat._load_history) and is rendered into the user prompt; the system prompt
stays byte-stable so the schema overview rides Claude Code's prompt cache.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    UserMessage,
    create_sdk_mcp_server,
    query,
)
from claude_agent_sdk import (
    TextBlock as SDKTextBlock,
)
from claude_agent_sdk import (
    ToolResultBlock as SDKToolResultBlock,
)
from claude_agent_sdk import (
    ToolUseBlock as SDKToolUseBlock,
)
from claude_agent_sdk import (
    tool as sdk_tool,
)

from app.config import Settings
from app.llm.provider import EpisodeToolHandler, Message, TextBlock, ToolDef

logger = logging.getLogger(__name__)

_MCP_SERVER = "hdb"
_MCP_PREFIX = f"mcp__{_MCP_SERVER}__"


class ClaudeCodeProvider:
    name = "claude"
    runs_own_loop = True

    def __init__(self, settings: Settings) -> None:
        token = settings.claude_code_oauth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token:
            raise RuntimeError(
                "CLAUDE_CODE_OAUTH_TOKEN is not set; cannot use the Claude Code "
                "provider. Generate one with `claude setup-token` and add it to .env."
            )
        self._token = token
        self.model = settings.llm_model
        self._effort = settings.llm_effort
        self._max_turns = settings.llm_max_agent_steps

    async def chat(self, **_kwargs: Any):  # pragma: no cover - protocol stub
        raise RuntimeError("claude-code provider runs its own loop; use run_episode()")

    async def run_episode(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        tool_handler: EpisodeToolHandler,
        model: str | None = None,
        effort: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run one full agent episode; yield the same event dicts as the classic loop."""
        server = create_sdk_mcp_server(
            name=_MCP_SERVER,
            tools=[_wrap_tool(t, tool_handler) for t in tools],
        )
        options = ClaudeAgentOptions(
            system_prompt=system,
            model=model or self.model,
            effort=effort or self._effort,  # same literal levels as llm_effort
            max_turns=self._max_turns,
            tools=[],  # no built-in Claude Code tools; HDB's MCP tools only
            mcp_servers={_MCP_SERVER: server},
            allowed_tools=[f"{_MCP_PREFIX}{t.name}" for t in tools],
            permission_mode="dontAsk",
            # Explicit env so subscription auth also works when the token only
            # exists in .env (pydantic) and not in this process's environment.
            env={"CLAUDE_CODE_OAUTH_TOKEN": self._token},
        )

        step = 0
        tool_names: dict[str, str] = {}  # tool_use_id -> HDB tool name
        async for msg in query(prompt=_render_prompt(messages), options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, SDKTextBlock) and block.text.strip():
                        yield {
                            "event": "assistant_text",
                            "data": {"text": block.text, "step": step},
                        }
                    elif isinstance(block, SDKToolUseBlock):
                        name = _strip_prefix(block.name)
                        tool_names[block.id] = name
                        yield {
                            "event": "tool_call",
                            "data": {
                                "id": block.id,
                                "name": name,
                                "input": dict(block.input or {}),
                                "step": step,
                            },
                        }
                step += 1
            elif isinstance(msg, UserMessage):
                blocks = msg.content if isinstance(msg.content, list) else []
                for block in blocks:
                    if isinstance(block, SDKToolResultBlock):
                        yield {
                            "event": "tool_result",
                            "data": {
                                "id": block.tool_use_id,
                                "name": tool_names.get(block.tool_use_id, ""),
                                "is_error": bool(block.is_error),
                                "preview": _shorten(_result_text(block.content)),
                                "step": max(step - 1, 0),
                            },
                        }
            elif isinstance(msg, ResultMessage):
                usage = {
                    k: v for k, v in dict(msg.usage or {}).items() if isinstance(v, (int, float))
                }
                if msg.total_cost_usd is not None:
                    usage["total_cost_usd"] = msg.total_cost_usd
                usage["stop_reason"] = msg.stop_reason or (
                    "end_turn" if not msg.is_error else msg.subtype
                )
                yield {"event": "usage", "data": usage}
                if msg.is_error:
                    logger.warning("claude-code episode ended with %s: %s", msg.subtype, msg.result)


def _wrap_tool(t: ToolDef, handler: EpisodeToolHandler):
    async def _run(args: dict[str, Any]) -> dict[str, Any]:
        result_text, is_error = await handler(t.name, args or {})
        out: dict[str, Any] = {"content": [{"type": "text", "text": result_text}]}
        if is_error:
            out["is_error"] = True
        return out

    return sdk_tool(t.name, t.description, t.input_schema)(_run)


def _strip_prefix(name: str) -> str:
    return name[len(_MCP_PREFIX) :] if name.startswith(_MCP_PREFIX) else name


def _render_prompt(messages: list[Message]) -> str:
    """Render collapsed history + the current question into one prompt string.

    History changes every turn, so it must live in the (uncached) prompt, not
    in the system prompt — keeping the big schema overview cacheable.
    """
    *history, current = messages
    parts: list[str] = []
    if history:
        lines = []
        for m in history:
            label = "User" if m.role == "user" else "Assistant"
            lines.append(f"{label}: {_text_of(m)}")
        parts.append("<conversation_history>\n" + "\n\n".join(lines) + "\n</conversation_history>")
    parts.append(_text_of(current))
    return "\n\n".join(parts)


def _text_of(m: Message) -> str:
    return "\n".join(b.text for b in m.content if isinstance(b, TextBlock) and b.text).strip()


def _result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _shorten(s: str, n: int = 400) -> str:
    return s if len(s) <= n else s[:n] + "…"
