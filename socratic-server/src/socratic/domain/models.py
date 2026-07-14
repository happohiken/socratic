from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    page_count: int = 0
    block_count: int = 0
    format: str = "pdf"
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class ContentBlock:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    ordinal: int = 0
    text: str = ""
    page_number: int = 0
    block_type: str = "paragraph"  # paragraph | heading | list | unknown
    metadata: dict = field(default_factory=dict)


@dataclass
class Study:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    current_block_id: Optional[str] = None
    last_completed_block_id: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str = ""
    content_block_id: Optional[str] = None
    role: str = ""  # user | assistant
    content: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
