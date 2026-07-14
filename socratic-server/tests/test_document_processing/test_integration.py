from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.extractor import parse_pdf
from socratic.document_processing.formatters import format_json, format_text
from socratic.document_processing.model import TocEntry


@pytest.fixture
def simple_pdf(tmp_path: Path) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Título del documento", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "Primer párrafo con texto.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Segunda línea del mismo párrafo.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Primer elemento de lista", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Segundo elemento de lista", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Párrafo después de la lista.", new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=14)
    pdf.cell(200, 10, "Segunda sección", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "Contenido de la segunda sección.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "simple.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def tight_pdf(tmp_path: Path) -> Path:
    """PDF con líneas muy juntas para probar fusión de párrafos."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.set_auto_page_break(False)
    # Usar alturas pequeñas para que las líneas queden juntas en pdfplumber
    pdf.set_y(30)
    pdf.cell(200, 3, "Primera línea del párrafo.", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(33)
    pdf.cell(200, 3, "Segunda línea del mismo párrafo.", new_x="LMARGIN", new_y="NEXT")
    # Salto grande (fuera del umbral)
    pdf.set_y(80)
    pdf.cell(200, 3, "Párrafo separado.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "tight.pdf"
    pdf.output(str(path))
    return path


def test_parse_simple_pdf(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    assert doc.title == "Título del documento"
    assert len(doc.nodes) > 0


def test_parse_simple_pdf_node_types(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    types = [n.node_type for n in doc.nodes]
    assert "heading" in types
    assert "paragraph" in types
    assert "list" in types


def test_parse_simple_pdf_page_numbers(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    pages = set(n.page_number for n in doc.nodes)
    assert pages == {1, 2}


def test_parse_simple_pdf_ordinal_order(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    ordinals = [n.ordinal for n in doc.nodes]
    assert ordinals == list(range(1, len(doc.nodes) + 1))


def test_parse_simple_pdf_text_not_empty(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    for node in doc.nodes:
        assert node.text.strip(), f"Node {node.id} has empty text"


def test_parse_simple_pdf_heading_detection(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    headings = [n for n in doc.nodes if n.node_type == "heading"]
    assert len(headings) >= 2
    for h in headings:
        assert h.font is not None
        assert h.font.bold is True


def test_parse_simple_pdf_list_detection(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    items = [n for n in doc.nodes if n.node_type == "list"]
    assert len(items) >= 1


def test_parse_tight_pdf_paragraph_merging(tight_pdf: Path):
    doc = parse_pdf(tight_pdf)
    paragraphs = [n for n in doc.nodes if n.node_type == "paragraph"]
    # The first paragraph should have merged two lines
    first_para = next((p for p in paragraphs if "Primera línea" in p.text), None)
    assert first_para is not None
    assert "Segunda línea" in first_para.text
    # The separate paragraph should not be merged
    second_para = next((p for p in paragraphs if "Párrafo separado" in p.text), None)
    assert second_para is not None
    assert "Segunda línea" not in second_para.text


def test_format_text_output(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    output = format_text(doc)
    assert "Document title:" in output
    assert "page=" in output
    assert "type=" in output


def test_format_json_output(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    output = format_json(doc)
    data = json.loads(output)
    assert "title" in data
    assert "nodes" in data
    assert len(data["nodes"]) == len(doc.nodes)


def test_parse_pdf_page_range(simple_pdf: Path):
    doc = parse_pdf(simple_pdf, page_range=(1, 1))
    pages = set(n.page_number for n in doc.nodes)
    assert pages == {1}
    assert len(doc.nodes) < len(parse_pdf(simple_pdf).nodes)


def test_parse_pdf_no_toc_without_bookmarks(simple_pdf: Path):
    doc = parse_pdf(simple_pdf)
    assert doc.toc == []


def test_parse_pdf_empty_pdf(tmp_path: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 10, "Solo texto", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "empty.pdf"
    pdf.output(str(path))
    doc = parse_pdf(path)
    assert doc.nodes is not None
    assert len(doc.nodes) >= 1
