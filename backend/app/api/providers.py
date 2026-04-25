from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
async def list_providers(request: Request) -> dict[str, Any]:
    registry = request.app.state.registry
    settings = request.app.state.settings
    # Refresh Ollama tags on every call — cheap, lets the UI show new models
    # the user just pulled without restarting the backend.
    await registry.refresh_ollama_models()
    return {
        "default_provider": settings.llm_provider,
        "default_effort": settings.llm_effort,
        "providers": [
            {
                "name": p.name,
                "default_model": p.default_model,
                "models": p.models,
                "available": p.available,
                "error": p.error,
            }
            for p in registry.info()
        ],
    }
