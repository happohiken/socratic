from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    storage_path: Path = Path("data/socratic.db")
    host: str = "0.0.0.0"
    port: int = 8885
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
