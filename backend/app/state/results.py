"""In-memory cache for query results.

The agent never feeds the full result back to the LLM (would burn tokens). It
hands the LLM a small preview (head + describe) and stores the full points
under a UUID; the frontend fetches by UUID via /api/results/{ref}.

A simple TTL-based dict — fine for single-user usage. Cleared every minute.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class StoredResult:
    ref: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    created_at: float
    expires_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, StoredResult] = {}
        self._lock = Lock()

    def put(
        self,
        *,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ref = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            self._store[ref] = StoredResult(
                ref=ref,
                sql=sql,
                columns=columns,
                rows=rows,
                created_at=now,
                expires_at=now + self._ttl,
                metadata=metadata or {},
            )
        return ref

    def get(self, ref: str) -> StoredResult | None:
        with self._lock:
            self._evict_expired(time.time())
            return self._store.get(ref)

    def _evict_expired(self, now: float) -> None:
        expired = [k for k, v in self._store.items() if v.expires_at < now]
        for k in expired:
            del self._store[k]
