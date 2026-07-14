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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import os
        print("\n=== DEBUG Settings ===")
        print(f"  llm_provider          = {self.llm_provider!r}")
        print(f"  llm_base_url          = {self.llm_base_url!r}")
        print(f"  llm_model             = {self.llm_model!r}")
        print(f"  llm_temperature       = {self.llm_temperature!r}")
        print(f"  llm_api_key           = {self.llm_api_key!r}")
        print(f"  llm_timeout_seconds   = {self.llm_timeout_seconds!r}")
        print(f"  SOCRATIC_LLM_PROVIDER (env) = {os.environ.get('SOCRATIC_LLM_PROVIDER')!r}")
        print(f"  SOCRATIC_LLM_BASE_URL (env) = {os.environ.get('SOCRATIC_LLM_BASE_URL')!r}")
        print(f"  SOCRATIC_LLM_MODEL (env)    = {os.environ.get('SOCRATIC_LLM_MODEL')!r}")
        print(f"  SOCRATIC_LLM_API_KEY (env)  = {os.environ.get('SOCRATIC_LLM_API_KEY')!r}")
        print(f"  SOCRATIC_LLM_TIMEOUT_SECONDS (env) = {os.environ.get('SOCRATIC_LLM_TIMEOUT_SECONDS')!r}")
        print("======================\n")
