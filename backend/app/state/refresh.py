"""Background task: periodically run schema discovery."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session

from app.influx.client import InfluxClient
from app.influx.schema_discovery import discover

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 6 * 60 * 60


class SchemaRefresher:
    """Owns one async task that loops `discover` on a timer.

    Exposes `last_run` and `last_error` so the API can surface freshness.
    """

    def __init__(self, engine, influx: InfluxClient) -> None:
        self._engine = engine
        self._influx = influx
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self.last_run: datetime | None = None
        self.last_error: str | None = None
        self.measurements_seen: int = 0
        self.is_running: bool = False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="schema-refresher")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: S110 -- best-effort task teardown on shutdown
                pass

    async def trigger_now(self) -> None:
        """Run a discovery pass immediately (used on startup and by /api/schema/refresh)."""
        async with self._lock:
            self.is_running = True
            try:
                with Session(self._engine) as session:
                    report = await discover(self._influx, session)
                self.last_run = datetime.now(timezone.utc)
                self.last_error = None
                self.measurements_seen = report.measurements
                logger.info(
                    "schema refresh complete: %d measurements, %d errors",
                    report.measurements,
                    len(report.errors),
                )
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("schema refresh failed")
            finally:
                self.is_running = False

    async def _loop(self) -> None:
        try:
            await self.trigger_now()
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=REFRESH_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    pass
                if self._stop.is_set():
                    break
                await self.trigger_now()
        except asyncio.CancelledError:
            return
