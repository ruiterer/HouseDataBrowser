"""Ollama provider — placeholder for Phase 5.

Will use httpx against the Ollama HTTP API (`/api/chat` with `tools` parameter).
The Phase 3 build is Claude-only; this stub exists so the factory can be wired
up without conditional imports.
"""

from __future__ import annotations

from app.config import Settings
from app.llm.provider import AssistantTurn, LLMProvider, Message, ToolDef


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.ollama_model
        self._host = settings.ollama_host

    async def chat(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        model: str | None = None,
        effort: str | None = None,
    ) -> AssistantTurn:
        raise NotImplementedError(
            "OllamaProvider is planned for Phase 5. Set LLM_PROVIDER=claude for now."
        )
