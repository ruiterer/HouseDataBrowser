from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    influx = request.app.state.influx

    influx_status: dict[str, Any] = {"connected": False}
    try:
        version = await influx.ping()
        influx_status = {
            "connected": True,
            "version": version,
            "database": settings.influx_database,
        }
    except Exception as exc:
        logger.warning("InfluxDB ping failed: %s", exc)
        influx_status["error"] = str(exc)

    return {
        "status": "ok",
        "influx": influx_status,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model
            if settings.llm_provider == "claude"
            else settings.ollama_model,
        },
    }
