from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TocEntry:
    title: str
    level: int
    page_number: int | None = None


@dataclass
class FontInfo:
    name: str
    size: float
    bold: bool = False
    italic: bool = False


@dataclass
class DocumentNode:
    id: int
    node_type: Literal["heading", "paragraph", "list", "unknown"]
    text: str
    page_number: int
    ordinal: int
    level: int | None = None
    parent_id: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    font: FontInfo | None = None
    list_items: list[ListItem] | None = None
    is_ordered: bool = False


@dataclass
class ListItem:
    text: str
    marker: str


@dataclass
class ParsedDocument:
    title: str | None = None
    toc: list[TocEntry] = field(default_factory=list)
    nodes: list[DocumentNode] = field(default_factory=list)
