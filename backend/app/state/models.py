from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return uuid.uuid4().hex


class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    title: str = "New conversation"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ConversationMessage(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)
    role: str  # "user" | "assistant"
    content: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    final_summary: str | None = None
    final_query: str | None = None
    final_chart: dict | None = Field(default=None, sa_column=Column(JSON))
    final_data_ref: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class SchemaCache(SQLModel, table=True):
    """Per-measurement snapshot of the InfluxDB schema as last discovered."""

    measurement: str = Field(primary_key=True)
    tag_keys: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    field_keys: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of {name, type} dicts as returned by SHOW FIELD KEYS.",
    )
    tag_values: dict[str, list[str]] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Tag-key -> sample values, only for low-cardinality tags.",
    )
    updated_at: datetime = Field(default_factory=_utcnow)


class MeasurementAnnotation(SQLModel, table=True):
    """Human-written description for a measurement, surfaced to the LLM."""

    measurement: str = Field(primary_key=True)
    description: str = ""
    updated_at: datetime = Field(default_factory=_utcnow)
