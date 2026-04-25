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
    llm_model: str = "claude-opus-4-7"
    # Supported by the Messages API on Opus 4.7: low | medium | high | max.
    # ("xhigh" is documented for some clients but currently rejected by /v1/messages.)
    llm_effort: Literal["low", "medium", "high", "max"] = "high"
    # 64K is the recommended default for streaming requests on Opus 4.7 — leaves
    # room for thinking + tool calls + final response at high/max effort. We use
    # streaming + get_final_message() in the Claude provider so this is safe.
    llm_max_tokens: int = 64000
    llm_max_agent_steps: int = 12

    anthropic_api_key: str | None = None

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    state_db_path: str = "./data/state.db"
    results_ttl_seconds: int = 3600

    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
