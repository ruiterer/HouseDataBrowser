from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{ref}")
async def get_result(ref: str, request: Request) -> dict[str, Any]:
    cache = request.app.state.results
    stored = cache.get(ref)
    if stored is None:
        raise HTTPException(status_code=404, detail="result expired or unknown")
    return {
        "ref": stored.ref,
        "sql": stored.sql,
        "columns": stored.columns,
        "rows": stored.rows,
        "metadata": stored.metadata,
    }
