from __future__ import annotations

from app.config import Settings
from app.llm.claude import ClaudeProvider
from app.llm.ollama import OllamaProvider
from app.llm.provider import LLMProvider


def make_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(settings)
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings)
    raise RuntimeError(f"unknown LLM provider: {settings.llm_provider!r}")
