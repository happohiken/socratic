from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber

from socratic.document_processing.classifier import classify_node
from socratic.document_processing.model import (
    DocumentNode,
    FontInfo,
    ParsedDocument,
    TocEntry,
)


def _try_load_pypdf() -> Any | None:
    try:
        import pypdf

        return pypdf
    except ImportError:
        return None


def _extract_toc_with_pypdf(pdf_path: Path) -> list[TocEntry]:
    pypdf = _try_load_pypdf()
    if pypdf is None:
        return []
    reader = pypdf.PdfReader(str(pdf_path))
    outlines = reader.outline
    if not outlines:
        return []
    toc: list[TocEntry] = []
    _build_toc(outlines, toc, level=1, reader=reader)
    return toc


def _build_toc(outlines: Any, toc: list[TocEntry], level: int, *, reader: Any) -> None:
    for entry in outlines:
        # pypdf returns Destination objects, not plain dicts
        title = ""
        page_number: int | None = None

        if hasattr(entry, "get_title"):
            # Destination object
            title = entry.get_title() or ""
            try:
                page_number = reader.get_destination_page_number(entry) + 1
            except Exception:
                page_number = None
        elif isinstance(entry, dict):
            title = entry.get("/Title", "")
            try:
                page_number = reader.get_destination_page_number(entry) + 1
            except Exception:
                page_number = None
        elif hasattr(entry, "__iter__"):
            _build_toc(entry, toc, level + 1, reader=reader)
            continue

        if title:
            toc.append(TocEntry(title=title, level=level, page_number=page_number))


def _extract_toc(pdf_path: Path) -> list[TocEntry]:
    return _extract_toc_with_pypdf(pdf_path)


def _get_font_info(chars: list[dict]) -> FontInfo:
    if not chars:
        return FontInfo(name="?", size=0, bold=False, italic=False)
    fontname = chars[0].get("fontname", "?") or "?"
    size = chars[0].get("size", 0) or 0
    bold = any("Bold" in (c.get("fontname", "") or "") for c in chars)
    italic = any("Italic" in (c.get("fontname", "") or "") for c in chars)
    return FontInfo(name=fontname, size=size, bold=bold, italic=italic)


def _extract_lines_from_page(page) -> list[dict]:
    text_lines = page.extract_text_lines()
    if not text_lines:
        return []
    result: list[dict] = []
    for tl in text_lines:
        chars = tl.get("chars", [])
        font = _get_font_info(chars)
        result.append(
            {
                "text": tl.get("text", "").strip(),
                "x0": tl.get("x0", 0),
                "x1": tl.get("x1", 0),
                "top": tl.get("top", 0),
                "bottom": tl.get("bottom", 0),
                "font": font,
            }
        )
    return result


def _merge_lines_into_paragraphs(
    lines: list[dict],
    y_threshold: float = 4.0,
    indent_threshold: float = 10.0,
) -> list[dict]:
    if not lines:
        return []
    merged: list[dict] = []
    current: dict | None = None

    for line in lines:
        if current is None:
            current = dict(line)
            continue

        y_gap = line["top"] - current["bottom"]
        same_font = (
            current["font"].name == line["font"].name
            and abs(current["font"].size - line["font"].size) < 0.5
        )

        if y_gap <= y_threshold and same_font:
            current["text"] += " " + line["text"]
            current["x1"] = line["x1"]
            current["bottom"] = line["bottom"]
        else:
            merged.append(current)
            current = dict(line)

    if current is not None:
        merged.append(current)

    return merged


def _join_hyphenated_words(text: str) -> str:
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def _sort_nodes_by_reading_order(nodes: list[DocumentNode]) -> list[DocumentNode]:
    return sorted(
        nodes,
        key=lambda n: (
            n.page_number,
            n.bbox[1] if n.bbox else 0,
            n.bbox[0] if n.bbox else 0,
        ),
    )


def parse_pdf(
    pdf_path: Path,
    page_range: tuple[int, int] | None = None,
) -> ParsedDocument:
    doc = ParsedDocument()
    doc.toc = _extract_toc(pdf_path)

    nodes: list[DocumentNode] = []
    ordinal = 0

    with pdfplumber.open(pdf_path) as pdf:
        start_page = page_range[0] if page_range else 1
        end_page = page_range[1] if page_range else len(pdf.pages)

        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1

            if page_range:
                if page_number < start_page or page_number > end_page:
                    continue

            lines = _extract_lines_from_page(page)
            paragraphs = _merge_lines_into_paragraphs(lines)

            for para in paragraphs:
                text = para["text"].strip()
                if not text:
                    continue

                text = _join_hyphenated_words(text)

                ordinal += 1
                bbox = (
                    para["x0"],
                    para["top"],
                    para["x1"],
                    para["bottom"],
                )
                node_type, level = classify_node(text, para["font"])

                nodes.append(
                    DocumentNode(
                        id=ordinal,
                        node_type=node_type,
                        text=text,
                        page_number=page_number,
                        ordinal=ordinal,
                        level=level,
                        bbox=bbox,
                        font=para["font"],
                    )
                )

    if nodes:
        first_heading = next(
            (n for n in nodes if n.node_type == "heading"), None
        )
        if first_heading:
            doc.title = first_heading.text

    nodes = _sort_nodes_by_reading_order(nodes)
    for i, n in enumerate(nodes):
        n.ordinal = i + 1

    doc.nodes = nodes
    return doc
