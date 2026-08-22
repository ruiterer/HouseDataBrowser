"""Pinned charts on the Dashboard.

Pins persist the InfluxQL + chart spec only; data is re-fetched on load so
charts stay current. The execute endpoint runs the saved query through the
same safety filter used elsewhere.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.state.models import PinnedChart

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pins", tags=["pins"])


class PinIn(BaseModel):
    title: str
    query: str
    chart_spec: dict[str, Any]


class PinOut(BaseModel):
    id: str
    title: str
    query: str
    chart_spec: dict[str, Any]
    layout: dict[str, int]
    created_at: datetime
    updated_at: datetime


class LayoutItem(BaseModel):
    id: str
    x: int
    y: int
    w: int
    h: int


def _to_out(p: PinnedChart) -> PinOut:
    return PinOut(
        id=p.id,
        title=p.title,
        query=p.query,
        chart_spec=p.chart_spec,
        layout={"x": p.layout_x, "y": p.layout_y, "w": p.layout_w, "h": p.layout_h},
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[PinOut])
async def list_pins(request: Request) -> list[PinOut]:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        rows = session.exec(select(PinnedChart).order_by(PinnedChart.created_at)).all()
        return [_to_out(p) for p in rows]


@router.post("", response_model=PinOut)
async def create_pin(body: PinIn, request: Request) -> PinOut:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        # Pick an open spot at the bottom of the grid (12-col layout).
        max_y = 0
        for p in session.exec(select(PinnedChart)).all():
            max_y = max(max_y, p.layout_y + p.layout_h)
        pin = PinnedChart(
            title=body.title.strip() or body.chart_spec.get("title") or "Grafiek",
            query=body.query,
            chart_spec=body.chart_spec,
            layout_x=0,
            layout_y=max_y,
            layout_w=6,
            layout_h=4,
        )
        session.add(pin)
        session.commit()
        session.refresh(pin)
        return _to_out(pin)


@router.delete("/{pin_id}")
async def delete_pin(pin_id: str, request: Request) -> dict[str, str]:
    engine = request.app.state.db_engine
    with Session(engine) as session:
        pin = session.get(PinnedChart, pin_id)
        if pin is None:
            raise HTTPException(status_code=404, detail="pin not found")
        session.delete(pin)
        session.commit()
    return {"status": "deleted"}


@router.put("/layout")
async def update_layout(items: list[LayoutItem], request: Request) -> dict[str, str]:
    """Bulk layout update. Called after the user drops a tile in a new spot."""
    engine = request.app.state.db_engine
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for item in items:
            pin = session.get(PinnedChart, item.id)
            if pin is None:
                continue
            pin.layout_x = item.x
            pin.layout_y = item.y
            pin.layout_w = item.w
            pin.layout_h = item.h
            pin.updated_at = now
            session.add(pin)
        session.commit()
    return {"status": "ok"}


@router.get("/{pin_id}/data")
async def get_pin_data(pin_id: str, request: Request) -> dict[str, Any]:
    """Re-run the saved query and return the rows for the chart."""
    engine = request.app.state.db_engine
    influx = request.app.state.influx
    with Session(engine) as session:
        pin = session.get(PinnedChart, pin_id)
        if pin is None:
            raise HTTPException(status_code=404, detail="pin not found")
    try:
        result = await influx.query(pin.query)
    except Exception as exc:
        logger.warning("pin %s query failed: %s", pin_id, exc)
        raise HTTPException(status_code=502, detail=f"query failed: {exc}") from exc

    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    for s in result.series:
        tags = s.get("tags") or {}
        for p in s["points"]:
            row = {**p}
            for k, v in tags.items():
                row.setdefault(k, v)
            for k in row:
                if k not in columns:
                    columns.append(k)
            rows.append(row)
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }
