"""Walk the InfluxDB schema and persist it to the state DB.

This runs on startup and on a 6-hour timer (see app.main lifespan). It uses the
read-only `SHOW ...` family of statements that go through the regular safety gate.

For each measurement we record:
  - tag keys
  - field keys (name + type)
  - tag values, but only for tags with <= LOW_CARDINALITY_LIMIT distinct values
    (high-cardinality tags like a timestamp-derived id would balloon the JSON)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from app.influx.client import InfluxClient
from app.state.models import SchemaCache

logger = logging.getLogger(__name__)

LOW_CARDINALITY_LIMIT = 50


@dataclass
class DiscoveryReport:
    measurements: int
    refreshed_at: str
    errors: list[str]


async def discover(client: InfluxClient, session: Session) -> DiscoveryReport:
    """Walk the schema and commit per-measurement.

    Per-measurement commits keep each write transaction tiny so concurrent
    writers (the chat endpoint creating a new Conversation, the schema
    description editor) aren't blocked on a long-running discovery transaction.
    With 562 measurements, one big transaction at the end can hold the lock for
    30+ seconds and break the chat endpoint with `database is locked`.
    """
    errors: list[str] = []
    measurements = await _list_measurements(client)
    logger.info("schema discovery: %d measurements", len(measurements))

    for m in measurements:
        try:
            tag_keys = await _list_tag_keys(client, m)
            field_keys = await _list_field_keys(client, m)
            tag_values: dict[str, list[str]] = {}
            for tk in tag_keys:
                values = await _list_tag_values(client, m, tk)
                if 0 < len(values) <= LOW_CARDINALITY_LIMIT:
                    tag_values[tk] = values
            row = session.get(SchemaCache, m)
            if row is None:
                row = SchemaCache(measurement=m)
            row.tag_keys = tag_keys
            row.field_keys = field_keys
            row.tag_values = tag_values
            row.updated_at = _now()
            session.merge(row)
            session.commit()
        except Exception as exc:
            logger.warning("discovery failed for %s: %s", m, exc)
            errors.append(f"{m}: {exc}")
            session.rollback()

    return DiscoveryReport(
        measurements=len(measurements),
        refreshed_at=_now().isoformat(),
        errors=errors,
    )


def list_cached(session: Session) -> list[SchemaCache]:
    return list(session.exec(select(SchemaCache).order_by(SchemaCache.measurement)).all())


async def _list_measurements(client: InfluxClient) -> list[str]:
    res = await client.query("SHOW MEASUREMENTS")
    out: list[str] = []
    for s in res.series:
        for p in s["points"]:
            name = p.get("name") or p.get("measurement")
            if name:
                out.append(name)
    return out


async def _list_tag_keys(client: InfluxClient, measurement: str) -> list[str]:
    sql = f'SHOW TAG KEYS FROM "{_q(measurement)}"'
    res = await client.query(sql)
    out: list[str] = []
    for s in res.series:
        for p in s["points"]:
            v = p.get("tagKey") or p.get("name")
            if v:
                out.append(v)
    return out


async def _list_field_keys(client: InfluxClient, measurement: str) -> list[dict]:
    sql = f'SHOW FIELD KEYS FROM "{_q(measurement)}"'
    res = await client.query(sql)
    out: list[dict] = []
    for s in res.series:
        for p in s["points"]:
            name = p.get("fieldKey") or p.get("name")
            ftype = p.get("fieldType") or p.get("type") or "unknown"
            if name:
                out.append({"name": name, "type": ftype})
    return out


async def _list_tag_values(client: InfluxClient, measurement: str, tag_key: str) -> list[str]:
    sql = (
        f'SHOW TAG VALUES FROM "{_q(measurement)}" WITH KEY = "{_q(tag_key)}" '
        f"LIMIT {LOW_CARDINALITY_LIMIT + 1}"
    )
    res = await client.query(sql)
    out: list[str] = []
    for s in res.series:
        for p in s["points"]:
            v = p.get("value")
            if v is not None:
                out.append(str(v))
    return out


def _q(identifier: str) -> str:
    """Escape an InfluxQL identifier for safe quoting between double quotes."""
    return identifier.replace('"', '\\"')


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
