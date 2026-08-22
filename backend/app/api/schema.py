from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.influx.schema_discovery import list_cached
from app.state.models import MeasurementAnnotation, SchemaCache

router = APIRouter(prefix="/api/schema", tags=["schema"])


class MeasurementOut(BaseModel):
    measurement: str
    description: str
    tag_keys: list[str]
    field_keys: list[dict[str, Any]]
    tag_values: dict[str, list[str]]
    updated_at: datetime


class SchemaSummary(BaseModel):
    measurements: list[MeasurementOut]
    last_refresh: datetime | None
    last_error: str | None
    is_refreshing: bool


class DescriptionUpdate(BaseModel):
    description: str


@router.get("", response_model=SchemaSummary)
async def get_schema(request: Request) -> SchemaSummary:
    engine = request.app.state.db_engine
    refresher = request.app.state.refresher
    with Session(engine) as session:
        cached = list_cached(session)
        annotations = {
            a.measurement: a.description for a in session.exec(select(MeasurementAnnotation)).all()
        }
        measurements = [
            MeasurementOut(
                measurement=row.measurement,
                description=annotations.get(row.measurement, ""),
                tag_keys=row.tag_keys,
                field_keys=row.field_keys,
                tag_values=row.tag_values,
                updated_at=row.updated_at,
            )
            for row in cached
        ]
    return SchemaSummary(
        measurements=measurements,
        last_refresh=refresher.last_run,
        last_error=refresher.last_error,
        is_refreshing=refresher.is_running,
    )


@router.put("/{measurement}/description", response_model=MeasurementOut)
async def update_description(
    measurement: str, body: DescriptionUpdate, request: Request
) -> MeasurementOut:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        cached = session.get(SchemaCache, measurement)
        if cached is None:
            raise HTTPException(status_code=404, detail=f"unknown measurement: {measurement}")
        ann = session.get(MeasurementAnnotation, measurement)
        if ann is None:
            ann = MeasurementAnnotation(measurement=measurement, description=body.description)
            session.add(ann)
        else:
            ann.description = body.description
            ann.updated_at = datetime.utcnow()
            session.add(ann)
        session.commit()
        session.refresh(ann)
        return MeasurementOut(
            measurement=cached.measurement,
            description=ann.description,
            tag_keys=cached.tag_keys,
            field_keys=cached.field_keys,
            tag_values=cached.tag_values,
            updated_at=cached.updated_at,
        )


@router.post("/refresh")
async def refresh(request: Request) -> dict[str, str]:
    refresher = request.app.state.refresher
    if refresher.is_running:
        return {"status": "already-running"}
    # Fire-and-forget so the HTTP call returns quickly.
    import asyncio

    asyncio.create_task(refresher.trigger_now())
    return {"status": "started"}
