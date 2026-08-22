"""The agent loop.

For one user question:
  1. Build the system prompt (with the cached schema overview).
  2. Compose the message history.
  3. Loop: LLM call -> emit text/tool-call events -> execute tools -> feed results
     back -> repeat. Stop when `render_response` is called, when stop_reason is
     `end_turn` with no tool calls, or when we hit `max_steps`.

Yields a stream of dict events (the API layer wraps these in SSE).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlmodel import Session

from app.agent.system_prompt import build_system_prompt
from app.agent.tools import (
    ALL_TOOLS,
    TERMINAL_TOOL_NAME,
    FinalResponse,
    ToolContext,
    handle_tool_call,
)
from app.config import Settings
from app.influx.client import InfluxClient
from app.llm.provider import (
    AssistantTurn,
    LLMProvider,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.state.results import ResultCache

logger = logging.getLogger(__name__)


async def run_agent(
    *,
    user_text: str,
    history: list[Message],
    settings: Settings,
    provider: LLMProvider,
    influx: InfluxClient,
    db_session: Session,
    results: ResultCache,
    model_override: str | None = None,
    effort_override: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run one user turn and yield SSE events."""
    system = build_system_prompt(db_session)
    ctx = ToolContext(influx=influx, db_session=db_session, results=results)

    messages: list[Message] = list(history) + [
        Message(role="user", content=[TextBlock(text=user_text)])
    ]

    final: FinalResponse | None = None
    last_assistant: list[TextBlock | ToolUseBlock] = []
    final_assistant_message: Message | None = None
    last_stop_reason: str | None = None

    effective_model = model_override or provider.model
    effective_effort = effort_override or settings.llm_effort

    yield {
        "event": "agent_start",
        "data": {
            "provider": provider.name,
            "model": effective_model,
            "effort": effective_effort,
        },
    }

    own_loop = getattr(provider, "runs_own_loop", False)
    if own_loop:
        # Episode delegation (Claude Code / Agent SDK): the provider drives the
        # agent loop itself and yields the same event dicts. Tool execution
        # stays here via the handler callback, so the safety filter and the
        # terminal-tool bookkeeping are identical to the classic path.
        async def _handle(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
            nonlocal final
            result_text, maybe_final, is_error = await handle_tool_call(name, tool_input, ctx)
            if maybe_final is not None and name == TERMINAL_TOOL_NAME:
                final = maybe_final
            return result_text, is_error

        try:
            async for ev in provider.run_episode(
                system=system,
                messages=messages,
                tools=ALL_TOOLS,
                tool_handler=_handle,
                model=model_override,
                effort=effort_override,
            ):
                if ev["event"] == "assistant_text":
                    last_assistant.append(TextBlock(text=ev["data"]["text"]))
                elif ev["event"] == "tool_call":
                    d = ev["data"]
                    last_assistant.append(
                        ToolUseBlock(id=d["id"], name=d["name"], input=d["input"])
                    )
                elif ev["event"] == "usage":
                    last_stop_reason = ev["data"].get("stop_reason")
                yield ev
        except Exception as exc:
            logger.exception("agent episode failed")
            yield {"event": "error", "data": {"message": f"LLM error: {exc}"}}
            return
        if last_assistant:
            final_assistant_message = Message(role="assistant", content=list(last_assistant))
    else:
        for step in range(settings.llm_max_agent_steps):
            try:
                turn: AssistantTurn = await provider.chat(
                    system=system,
                    messages=messages,
                    tools=ALL_TOOLS,
                    model=model_override,
                    effort=effort_override,
                )
            except Exception as exc:
                logger.exception("LLM call failed at step %d", step)
                yield {"event": "error", "data": {"message": f"LLM error: {exc}"}}
                return

            last_assistant = [b for b in turn.content if isinstance(b, (TextBlock, ToolUseBlock))]
            last_stop_reason = turn.stop_reason
            text_blocks = [b.text for b in last_assistant if isinstance(b, TextBlock) and b.text]
            tool_calls = [b for b in last_assistant if isinstance(b, ToolUseBlock)]

            for t in text_blocks:
                yield {"event": "assistant_text", "data": {"text": t, "step": step}}

            if turn.usage:
                yield {"event": "usage", "data": {**turn.usage, "stop_reason": turn.stop_reason}}

            if not tool_calls:
                final_assistant_message = Message(role="assistant", content=list(last_assistant))
                break

            messages.append(Message(role="assistant", content=list(last_assistant)))

            tool_result_blocks: list[ToolResultBlock] = []
            for tc in tool_calls:
                yield {
                    "event": "tool_call",
                    "data": {"id": tc.id, "name": tc.name, "input": tc.input, "step": step},
                }
                result_text, maybe_final, is_error = await handle_tool_call(tc.name, tc.input, ctx)
                tool_result_blocks.append(
                    ToolResultBlock(tool_use_id=tc.id, content=result_text, is_error=is_error)
                )
                yield {
                    "event": "tool_result",
                    "data": {
                        "id": tc.id,
                        "name": tc.name,
                        "is_error": is_error,
                        "preview": _shorten(result_text),
                        "step": step,
                    },
                }
                if maybe_final is not None and tc.name == TERMINAL_TOOL_NAME:
                    final = maybe_final

            messages.append(Message(role="user", content=list(tool_result_blocks)))
            final_assistant_message = Message(role="assistant", content=list(last_assistant))

            if final is not None:
                break
        else:
            yield {
                "event": "error",
                "data": {"message": f"agent hit step cap ({settings.llm_max_agent_steps})"},
            }

    if final is not None:
        yield {
            "event": "final",
            "data": {
                "summary": final.summary,
                "query": final.query,
                "chart": final.chart,
                "data_ref": final.data_ref,
            },
        }
    else:
        # No render_response was called — best-effort fallback. Surface the
        # stop_reason so the user can act on max_tokens / refusal / etc.
        text = " ".join(
            b.text for b in last_assistant if isinstance(b, TextBlock) and b.text
        ).strip()
        if not text:
            text = _fallback_message(last_stop_reason)
        yield {
            "event": "final",
            "data": {"summary": text, "query": "", "chart": None, "data_ref": None},
        }

    yield {
        "event": "done",
        "data": {
            "messages_added": [
                # In episode mode `messages` is never extended (the SDK owns the
                # transcript), so there is no tool-results message to report.
                _serialize_message(messages[-2]) if not own_loop and len(messages) >= 2 else None,
                _serialize_message(final_assistant_message)
                if final_assistant_message is not None
                else None,
            ]
        },
    }


def _shorten(s: str, n: int = 400) -> str:
    return s if len(s) <= n else s[:n] + "…"


def _fallback_message(stop_reason: str | None) -> str:
    if stop_reason == "max_tokens":
        return (
            "Claude liep tegen de tokenlimiet aan voordat hij `render_response` kon "
            "aanroepen. Probeer de vraag op te splitsen, of zet 'Diep nadenken' uit "
            "en probeer opnieuw. Verhogen van LLM_MAX_TOKENS in .env helpt ook."
        )
    if stop_reason == "refusal":
        return (
            "Claude weigerde dit antwoord te geven (veiligheidsfilter). "
            "Herformuleer de vraag of vraag iets anders."
        )
    if stop_reason == "model_context_window_exceeded":
        return (
            "Het gesprek is te lang voor het contextvenster. Start een nieuw "
            "gesprek of wis oudere berichten."
        )
    return (
        f"Claude eindigde zonder antwoord (stop_reason={stop_reason!r}). "
        "Soms gebeurt dit bij maximale effort op vage vragen — herformuleer of "
        "zet 'Diep nadenken' uit en probeer opnieuw."
    )


def _serialize_message(m: Message | None) -> dict[str, Any] | None:
    if m is None:
        return None
    blocks: list[dict[str, Any]] = []
    for b in m.content:
        if isinstance(b, TextBlock):
            blocks.append({"type": "text", "text": b.text})
        elif isinstance(b, ToolUseBlock):
            blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
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
