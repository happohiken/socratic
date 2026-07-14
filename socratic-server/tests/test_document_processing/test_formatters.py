from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.formatters import format_json, format_text
from socratic.document_processing.model import (
    DocumentNode,
    FontInfo,
    ParsedDocument,
    TocEntry,
)


def _make_doc() -> ParsedDocument:
    doc = ParsedDocument(
        title="Documento de prueba",
        toc=[
            TocEntry(title="Introducción", level=1, page_number=3),
            TocEntry(title="Conceptos básicos", level=1, page_number=7),
        ],
        nodes=[
            DocumentNode(
                id=1,
                node_type="heading",
                text="Introducción",
                page_number=3,
                ordinal=1,
                level=1,
                bbox=(31.2, 34.6, 215.2, 50.6),
                font=FontInfo(name="Helvetica-Bold", size=16.0, bold=True),
            ),
            DocumentNode(
                id=2,
                node_type="paragraph",
                text="Este es el primer párrafo.",
                page_number=3,
                ordinal=2,
                font=FontInfo(name="Helvetica", size=12.0),
            ),
            DocumentNode(
                id=3,
                node_type="list_item",
                text="- Primer elemento",
                page_number=4,
                ordinal=3,
                font=FontInfo(name="Helvetica", size=12.0),
            ),
        ],
    )
    return doc


def test_format_text_includes_title():
    output = format_text(_make_doc())
    assert "Document title: Documento de prueba" in output


def test_format_text_includes_toc():
    output = format_text(_make_doc())
    assert "TOC:" in output
    assert "[1] Introducción" in output
    assert "[2] Conceptos básicos" in output
    assert "page 3" in output
    assert "page 7" in output


def test_format_text_includes_nodes():
    output = format_text(_make_doc())
    assert "[0001] page=3 type=heading" in output
    assert "[0002] page=3 type=paragraph" in output
    assert "[0003] page=4 type=list_item" in output
    assert "Introducción" in output
    assert "Este es el primer párrafo." in output


def test_format_text_includes_font_info():
    output = format_text(_make_doc())
    assert "font=Helvetica-Bold size=16.0" in output
    assert "font=Helvetica size=12.0" in output


def test_format_json_structure():
    output = format_json(_make_doc())
    data = json.loads(output)
    assert data["title"] == "Documento de prueba"
    assert len(data["toc"]) == 2
    assert data["toc"][0]["title"] == "Introducción"
    assert data["toc"][0]["page_number"] == 3
    assert len(data["nodes"]) == 3
    assert data["nodes"][0]["type"] == "heading"
    assert data["nodes"][0]["level"] == 1
    assert data["nodes"][0]["font"]["bold"] is True
    assert data["nodes"][0]["font"]["name"] == "Helvetica-Bold"
    assert data["nodes"][0]["bbox"] == [31.2, 34.6, 215.2, 50.6]


def test_format_json_is_valid():
    output = format_json(_make_doc())
    data = json.loads(output)
    assert isinstance(data, dict)
    assert "title" in data
    assert "nodes" in data


def test_format_text_no_toc():
    doc = ParsedDocument(
        title="Sin índice",
        nodes=[
            DocumentNode(
                id=1,
                node_type="paragraph",
                text="Contenido",
                page_number=1,
                ordinal=1,
                font=FontInfo(name="Helvetica", size=12.0),
            ),
        ],
    )
    output = format_text(doc)
    assert "Document title: Sin índice" in output
    assert "TOC:" not in output


def test_format_json_no_toc():
    doc = ParsedDocument(
        title="Sin índice",
        nodes=[],
    )
    output = format_json(doc)
    data = json.loads(output)
    assert "toc" not in data or data.get("toc") == []
