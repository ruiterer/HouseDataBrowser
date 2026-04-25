from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
