"""Chat + conversation endpoints.

POST /api/chat                    — start/continue a conversation, streams SSE
GET  /api/conversations           — list
POST /api/conversations           — create empty conversation
GET  /api/conversations/{id}      — fetch conversation + messages
DELETE /api/conversations/{id}    — delete

The /api/chat endpoint takes { conversation_id?, message } and returns an SSE
stream of `agent_start | assistant_text | tool_call | tool_result | usage |
final | done | error` events. It also persists the user + assistant turns to
SQLite as part of the `done` event.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from app.agent.loop import run_agent
from app.llm.provider import (
    Message as LLMMessage,
)
from app.llm.provider import (
    TextBlock,
)
from app.state.models import Conversation, ConversationMessage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    title_hint: str | None = None
    deep: bool = False  # When true, use effort=max for this single message
    provider: str | None = None  # Optional per-request provider override
    model: str | None = None  # Optional per-request model override


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: list[dict[str, Any]]
    final_summary: str | None = None
    final_query: str | None = None
    final_chart: dict[str, Any] | None = None
    final_data_ref: str | None = None
    created_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


@router.get("/api/conversations")
async def list_conversations(request: Request) -> list[ConversationOut]:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        rows = session.exec(select(Conversation).order_by(Conversation.updated_at.desc())).all()
        return [ConversationOut(**c.model_dump()) for c in rows]


@router.post("/api/conversations")
async def create_conversation(request: Request) -> ConversationOut:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        c = Conversation(title="New conversation")
        session.add(c)
        session.commit()
        session.refresh(c)
        return ConversationOut(**c.model_dump())


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> ConversationDetail:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        c = session.get(Conversation, conversation_id)
        if c is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        msgs = session.exec(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at)
        ).all()
        return ConversationDetail(
            conversation=ConversationOut(**c.model_dump()),
            messages=[MessageOut(**m.model_dump()) for m in msgs],
        )


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request) -> dict[str, str]:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        c = session.get(Conversation, conversation_id)
        if c is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        msgs = session.exec(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            )
        ).all()
        for m in msgs:
            session.delete(m)
        session.delete(c)
        session.commit()
    return {"status": "deleted"}


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    engine = request.app.state.db_engine
    settings = request.app.state.settings
    registry = request.app.state.registry
    influx = request.app.state.influx
    results = request.app.state.results

    try:
        provider = registry.get(body.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with Session(engine) as session:
        if body.conversation_id:
            convo = session.get(Conversation, body.conversation_id)
            if convo is None:
                raise HTTPException(status_code=404, detail="conversation not found")
        else:
            convo = Conversation(title=_derive_title(body.title_hint or body.message))
            session.add(convo)
            session.commit()
            session.refresh(convo)
        history = _load_history(session, convo.id)

    async def event_stream():
        with Session(engine) as session:
            convo_local = session.get(Conversation, convo.id)
            yield {
                "event": "conversation",
                "data": json.dumps(
                    {
                        "id": convo_local.id,
                        "title": convo_local.title,
                    }
                ),
            }

            user_msg = ConversationMessage(
                conversation_id=convo_local.id,
                role="user",
                content=[{"type": "text", "text": body.message}],
            )
            session.add(user_msg)
            session.commit()
            session.refresh(user_msg)
            yield {"event": "user_message_saved", "data": json.dumps({"id": user_msg.id})}

            final_payload: dict[str, Any] | None = None
            agent_blocks: list[dict[str, Any]] = []

            try:
                async for ev in run_agent(
                    user_text=body.message,
                    history=history,
                    settings=settings,
                    provider=provider,
                    influx=influx,
                    db_session=session,
                    results=results,
                    model_override=body.model,
                    effort_override="max" if body.deep else None,
                ):
                    name = ev["event"]
                    data = ev["data"]
                    if name == "final":
                        final_payload = data
                    if name == "assistant_text":
                        agent_blocks.append({"type": "text", "text": data["text"]})
                    elif name == "tool_call":
                        agent_blocks.append(
                            {
                                "type": "tool_use",
                                "id": data["id"],
                                "name": data["name"],
                                "input": data["input"],
                            }
                        )
                    yield {"event": name, "data": json.dumps(data, default=str)}
            except Exception as exc:
                logger.exception("agent failed")
                yield {"event": "error", "data": json.dumps({"message": str(exc)})}
                return

            assistant_msg = ConversationMessage(
                conversation_id=convo_local.id,
                role="assistant",
                content=agent_blocks,
                final_summary=(final_payload or {}).get("summary"),
                final_query=(final_payload or {}).get("query"),
                final_chart=(final_payload or {}).get("chart"),
                final_data_ref=(final_payload or {}).get("data_ref"),
            )
            session.add(assistant_msg)
            convo_local.updated_at = datetime.now(timezone.utc)
            session.add(convo_local)
            session.commit()
            session.refresh(assistant_msg)

            yield {"event": "saved", "data": json.dumps({"assistant_message_id": assistant_msg.id})}

    return EventSourceResponse(event_stream())


def _derive_title(seed: str) -> str:
    seed = seed.strip().splitlines()[0] if seed else "New conversation"
    return (seed[:60] + "…") if len(seed) > 60 else seed or "New conversation"


def _load_history(session: Session, conversation_id: str) -> list[LLMMessage]:
    """Load chat history for a follow-up turn.

    Each prior assistant turn is replayed as a single text block combining the
    final summary AND the InfluxQL that produced it. We do NOT replay the raw
    tool_use/tool_result sequence — re-sending tool_use blocks without their
    tool_result counterparts would 400 the Anthropic API, and replaying the full
    tool trace would balloon context without much added value. Including the
    query keeps follow-ups like "now do the same for 2024" coherent.
    """
    msgs = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    ).all()
    out: list[LLMMessage] = []
    for m in msgs:
        if m.role == "assistant":
            text = _render_assistant_history(m)
            if not text:
                continue
            out.append(LLMMessage(role="assistant", content=[TextBlock(text=text)]))
        else:
            user_text = " ".join(
                b.get("text", "") for b in (m.content or []) if b.get("type") == "text"
            ).strip()
            if user_text:
                out.append(LLMMessage(role="user", content=[TextBlock(text=user_text)]))
    if len(out) > 20:
        out = out[-20:]
    return out


def _render_assistant_history(m: ConversationMessage) -> str:
    parts: list[str] = []
    summary = (m.final_summary or "").strip()
    if summary:
        parts.append(summary)
    if m.final_query:
        parts.append(f"InfluxQL gebruikt:\n```sql\n{m.final_query}\n```")
    if not parts:
        # Fallback: stitch any plain text blocks if nothing else was saved
        text = " ".join(
            b.get("text", "") for b in (m.content or []) if b.get("type") == "text"
        ).strip()
        return text
    return "\n\n".join(parts)
