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
    llm_model: str = "claude-sonnet-4-6"

    anthropic_api_key: str | None = None

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    state_db_path: str = "./data/state.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
