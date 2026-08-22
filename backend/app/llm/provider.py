"""Provider-agnostic LLM interface.

Both Claude and Ollama implementations conform to this. Tool-use is the only
agent surface; we intentionally avoid Claude-specific features (adaptive thinking,
prompt caching) leaking into the abstraction so the Ollama swap is a pure config
change.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class TextBlock:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: list[ContentBlock]


@dataclass
class AssistantTurn:
    content: list[ContentBlock]
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    """All providers expose a single non-streaming chat call.

    Streaming to the UI happens at the agent-loop level (per-turn / per-tool-call
    events), not at the token level — that keeps Ollama and Claude shaped the same
    way and avoids per-provider streaming code in the agent.

    `model` and `effort` are per-call overrides (e.g. for a "Diep nadenken"
    toggle in the UI). Providers that don't understand `effort` ignore it.
    """

    name: str
    model: str

    async def chat(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        model: str | None = None,
        effort: str | None = None,
    ) -> AssistantTurn: ...


# Optional capability on top of LLMProvider: a provider that drives the whole
# agent episode itself (Claude Code via the Agent SDK). The agent loop checks
# the `runs_own_loop` attribute and, when true, calls `run_episode()` instead
# of driving per-turn chat() calls. Tool execution stays on the loop's side:
# the provider calls back through an EpisodeToolHandler, which returns
# (result_text, is_error). This keeps the safety filter and terminal-tool
# bookkeeping in agent code, out of provider implementations.
EpisodeToolHandler = Callable[[str, dict[str, Any]], Awaitable[tuple[str, bool]]]
