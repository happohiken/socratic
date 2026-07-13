from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOCRATIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_path: Path = Path("data/socratic.db")
    host: str = "0.0.0.0"
    port: int = 8885

    # LLM configuration
    llm_provider: str = "openai-compatible"
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_api_key: str | None = None
    llm_timeout_seconds: int = 120
