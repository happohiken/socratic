from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    storage_path: Path = Path("data/socratic.db")
    host: str = "0.0.0.0"
    port: int = 8885
