from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    influx_host: str = Field(default="localhost")
    influx_port: int = Field(default=8086)
    influx_database: str = Field(default="house")
    influx_username: str | None = None
    influx_password: str | None = None
    influx_ssl: bool = False
    influx_timeout_seconds: int = 10
    influx_row_limit: int = 50_000

    llm_provider: Literal["claude", "ollama"] = "claude"
    # Claude Code model alias (opus | sonnet | haiku): resolves to the
    # subscription's current model of that tier, so it never goes stale.
    llm_model: str = "opus"
    # Effort levels supported by the Claude Agent SDK: low | medium | high |
    # xhigh | max. Default high balances quality and usage-quota spend; the
    # UI's "Diep nadenken" toggle bumps a message to max.
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    llm_max_agent_steps: int = 12

    # Subscription OAuth token for the Claude Code provider; generate once
    # with `claude setup-token` (valid ~1 year) and put it in .env.
    claude_code_oauth_token: str | None = None

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    state_db_path: str = "./data/state.db"
    results_ttl_seconds: int = 3600

    api_host: str = "0.0.0.0"  # noqa: S104 -- container bind; host exposure is 127.0.0.1 via compose
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
