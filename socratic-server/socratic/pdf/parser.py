from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import List

import pdfplumber

from socratic.domain.models import ContentBlock

LINE_TOLERANCE = 5


def classify_block(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "paragraph"
    if len(stripped) <= 100 and (
        stripped.endswith(":")
        or stripped.endswith(".")
        and len(stripped) < 80
    ):
        if len(stripped) <= 80:
            return "heading"
    if stripped[0] in ("•", "–", "—", "-") or stripped[0].isdigit():
        return "list"
    return "paragraph"


def _extract_lines_from_page(page) -> list[tuple[str, int]]:
    words = page.extract_words()
    if not words:
        return []

    groups: dict[int, list[str]] = defaultdict(list)
    for w in words:
        y_key = round(w["top"] / LINE_TOLERANCE) * LINE_TOLERANCE
        groups[y_key].append(w["text"])

    lines: list[tuple[str, int]] = []
    for y_key in sorted(groups.keys()):
        line_text = " ".join(groups[y_key])
        if line_text.strip():
            lines.append((line_text.strip(), round(y_key)))

    return lines


def extract_blocks_from_pdf(pdf_path: Path) -> List[ContentBlock]:
    blocks: List[ContentBlock] = []
    ordinal = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1
            lines = _extract_lines_from_page(page)
            for line_text, _y in lines:
                ordinal += 1
                blocks.append(
                    ContentBlock(
                        document_id="",
                        ordinal=ordinal,
                        text=line_text,
                        page_number=page_number,
                        block_type=classify_block(line_text),
                    )
                )

    return blocks


def count_pages(pdf_path: Path) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)
