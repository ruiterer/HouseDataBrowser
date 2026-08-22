"""Provider registry.

Holds one instance of every LLM provider the user has configured (Claude if
ANTHROPIC_API_KEY is set, Ollama if OLLAMA_HOST is reachable). The chat
endpoint resolves a per-request `provider` field through this registry.

For Claude the model list is hard-coded — a curated set of current Anthropic IDs.
For Ollama we query /api/tags to surface whichever models the user has pulled
locally; an unreachable Ollama just returns an empty list (the UI will then
hide that option) without crashing the app.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import Settings
from app.llm.claude import ClaudeProvider
from app.llm.ollama import OllamaProvider
from app.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# First entry doubles as the fallback default when LLM_MODEL is not in the
# list. claude-fable-5 (Mythos tier, 2x Opus pricing) requires the API org to
# be on 30-day data retention; it is offered as a manual pick, not a default.
CLAUDE_MODELS: tuple[str, ...] = (
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-haiku-4-5",
    "claude-fable-5",
)


@dataclass
class ProviderInfo:
    name: str
    default_model: str
    models: list[str] = field(default_factory=list)
    available: bool = True
    error: str | None = None


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {}
        self._info: dict[str, ProviderInfo] = {}
        self._init_claude()
        self._init_ollama()

    def _init_claude(self) -> None:
        try:
            self._providers["claude"] = ClaudeProvider(self._settings)
            self._info["claude"] = ProviderInfo(
                name="claude",
                default_model=self._settings.llm_model
                if self._settings.llm_model in CLAUDE_MODELS
                else CLAUDE_MODELS[0],
                models=list(CLAUDE_MODELS),
                available=True,
            )
            logger.info("claude provider loaded (default %s)", self._info["claude"].default_model)
        except Exception as exc:
            self._info["claude"] = ProviderInfo(
                name="claude",
                default_model=CLAUDE_MODELS[0],
                models=list(CLAUDE_MODELS),
                available=False,
                error=str(exc),
            )
            logger.info("claude provider unavailable: %s", exc)

    def _init_ollama(self) -> None:
        # Ollama is best-effort: if the host can't be reached we leave it as
        # unavailable. The UI shows it greyed out with the error.
        try:
            self._providers["ollama"] = OllamaProvider(self._settings)
            self._info["ollama"] = ProviderInfo(
                name="ollama",
                default_model=self._settings.ollama_model,
                available=True,
            )
            logger.info("ollama provider loaded (host %s)", self._settings.ollama_host)
        except Exception as exc:
            self._info["ollama"] = ProviderInfo(
                name="ollama",
                default_model=self._settings.ollama_model,
                available=False,
                error=str(exc),
            )

    def get(self, name: str | None) -> LLMProvider:
        """Resolve a provider by name; falls back to the configured default."""
        wanted = name or self._settings.llm_provider
        if wanted not in self._providers:
            raise RuntimeError(f"provider {wanted!r} is not available")
        return self._providers[wanted]

    def info(self) -> list[ProviderInfo]:
        # Return both, available first
        return sorted(self._info.values(), key=lambda p: (not p.available, p.name))

    async def refresh_ollama_models(self) -> None:
        """Probe Ollama's /api/tags to discover locally-pulled models.

        Updates self._info["ollama"].models. Tolerates connection errors.
        """
        info = self._info.get("ollama")
        if info is None:
            return
        try:
            host = self._settings.ollama_host.rstrip("/")
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{host}/api/tags")
                r.raise_for_status()
                data = r.json()
            tags = [m["name"] for m in (data.get("models") or []) if m.get("name")]
            info.models = sorted(tags)
            info.available = True
            info.error = None
            if info.default_model not in tags and tags:
                info.default_model = tags[0]
        except Exception as exc:
            logger.debug("ollama /api/tags probe failed: %s", exc)
            info.available = False
            info.error = str(exc)
            info.models = []
