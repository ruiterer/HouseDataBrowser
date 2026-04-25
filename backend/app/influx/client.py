"""Async wrapper over influxdb-python (v1).

The underlying client is sync; we shuttle calls to a thread pool so the FastAPI event
loop stays responsive. All queries go through `app.influx.safety.validate` first.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError

from app.config import Settings
from app.influx.safety import validate


@dataclass
class QueryResult:
    sql: str
    series: list[dict[str, Any]]
    rowcount: int


class InfluxClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = InfluxDBClient(
            host=settings.influx_host,
            port=settings.influx_port,
            username=settings.influx_username,
            password=settings.influx_password,
            database=settings.influx_database,
            ssl=settings.influx_ssl,
            verify_ssl=settings.influx_ssl,
            timeout=settings.influx_timeout_seconds,
        )

    async def ping(self) -> str:
        return await asyncio.to_thread(self._client.ping)

    async def query(self, sql: str) -> QueryResult:
        validated = validate(sql, default_limit=self._settings.influx_row_limit)
        result = await asyncio.to_thread(self._client.query, validated.sql)
        series: list[dict[str, Any]] = []
        rowcount = 0
        # influxdb-python's ResultSet.items() yields ((measurement, tags), iterator).
        for meta, points_iter in result.items():
            if isinstance(meta, tuple):
                measurement, tags = meta
            else:
                measurement, tags = meta, None
            points = list(points_iter)
            rowcount += len(points)
            series.append(
                {
                    "measurement": measurement,
                    "tags": tags,
                    "points": points,
                }
            )
        return QueryResult(sql=validated.sql, series=series, rowcount=rowcount)

    def close(self) -> None:
        self._client.close()


__all__ = ["InfluxClient", "QueryResult", "InfluxDBClientError", "InfluxDBServerError"]
