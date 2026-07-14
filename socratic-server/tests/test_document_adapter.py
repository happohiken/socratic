"""Pruebas del adaptador: ParsedDocument -> modelos persistentes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from socratic.document_processing.adapter import (
    parsed_to_content_blocks,
    parsed_to_document,
)
from socratic.document_processing.extractor import parse_pdf
from socratic.document_processing.model import (
    DocumentNode,
    FontInfo,
    ParsedDocument,
    TocEntry,
)
from socratic.domain.models import ContentBlock, Document
from socratic.storage.database import (
    DB,
    init_db,
    get_content_blocks,
    get_document,
    save_content_blocks,
    save_document,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
def simple_pdf(tmp_path: Path) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo del documento", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "Primer parrafo con texto.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Segunda linea del mismo parrafo.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Primer elemento de lista", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Segundo elemento de lista", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Parrafo despues de la lista.", new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=14)
    pdf.cell(200, 10, "Segunda seccion", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "Contenido de la segunda seccion.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "simple.pdf"
    pdf.output(str(path))
    return path


# ── parsed_to_document ────────────────────────────────────────────

class TestParsedToDocument:
    def test_basic_fields(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        doc = parsed_to_document(parsed, "test.pdf")
        assert doc.filename == "test.pdf"
        assert doc.format == "pdf"
        assert doc.block_count == len(parsed.nodes)
        assert doc.page_count > 0

    def test_pages_counted(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        doc = parsed_to_document(parsed, "test.pdf")
        expected_pages = len({n.page_number for n in parsed.nodes})
        assert doc.page_count == expected_pages

    def test_metadata_contains_title(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        doc = parsed_to_document(parsed, "test.pdf")
        assert "title" in doc.metadata
        assert doc.metadata["title"] == parsed.title

    def test_metadata_contains_toc(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        doc = parsed_to_document(parsed, "test.pdf")
        assert "toc" in doc.metadata

    def test_empty_parsed_document(self):
        parsed = ParsedDocument(title="Vacio", nodes=[])
        doc = parsed_to_document(parsed, "empty.pdf")
        assert doc.block_count == 0
        assert doc.page_count == 0
        assert doc.metadata["title"] == "Vacio"


# ── parsed_to_content_blocks ─────────────────────────────────────

class TestParsedToContentBlocks:
    def test_block_count_matches(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        assert len(blocks) == len(parsed.nodes)

    def test_ordinal_preserved(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for i, (node, block) in enumerate(zip(parsed.nodes, blocks)):
            assert block.ordinal == node.ordinal

    def test_text_preserved(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for node, block in zip(parsed.nodes, blocks):
            assert block.text == node.text

    def test_page_number_preserved(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for node, block in zip(parsed.nodes, blocks):
            assert block.page_number == node.page_number

    def test_block_type_mapping(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for node, block in zip(parsed.nodes, blocks):
            expected_type = "list" if node.node_type == "list_item" else node.node_type
            assert block.block_type == expected_type

    def test_heading_type_preserved(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        headings = [b for b in blocks if b.block_type == "heading"]
        assert len(headings) >= 2

    def test_paragraph_type_preserved(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        paragraphs = [b for b in blocks if b.block_type == "paragraph"]
        assert len(paragraphs) > 0

    def test_list_type_from_list_item(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        lists = [b for b in blocks if b.block_type == "list"]
        assert len(lists) >= 1

    def test_document_id_set(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("my-doc-id", parsed)
        for block in blocks:
            assert block.document_id == "my-doc-id"

    def test_uuids_generated(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        ids = [b.id for b in blocks]
        assert len(ids) == len(set(ids)), "Cada bloque debe tener UUID unico"

    def test_metadata_contains_level_for_headings(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for block in blocks:
            if block.block_type == "heading":
                assert "level" in block.metadata

    def test_metadata_contains_bbox(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for block in blocks:
            if block.page_number > 0:
                assert "bbox" in block.metadata

    def test_metadata_contains_font(self, simple_pdf: Path):
        parsed = parse_pdf(simple_pdf)
        blocks = parsed_to_content_blocks("doc-1", parsed)
        for block in blocks:
            assert "font" in block.metadata

    def test_empty_parsed_document(self):
        parsed = ParsedDocument(nodes=[])
        blocks = parsed_to_content_blocks("doc-1", parsed)
        assert blocks == []


# ── Pruebas unitarias directas ────────────────────────────────────

class TestAdapterUnit:
    def test_list_item_to_list(self):
        node = DocumentNode(
            id=1, node_type="list_item", text="- Elemento",
            page_number=1, ordinal=1, font=FontInfo(name="Helvetica", size=12),
        )
        parsed = ParsedDocument(nodes=[node])
        blocks = parsed_to_content_blocks("doc-1", parsed)
        assert len(blocks) == 1
        assert blocks[0].block_type == "list"

    def test_heading_preserves_level(self):
        node = DocumentNode(
            id=1, node_type="heading", text="Capitulo 1",
            page_number=1, ordinal=1, level=1,
            font=FontInfo(name="Helvetica-Bold", size=16, bold=True),
            bbox=(10, 20, 100, 40),
        )
        parsed = ParsedDocument(nodes=[node])
        blocks = parsed_to_content_blocks("doc-1", parsed)
        assert blocks[0].block_type == "heading"
        assert blocks[0].metadata["level"] == 1
        assert blocks[0].metadata["bbox"] == [10, 20, 100, 40]
        assert blocks[0].metadata["font"]["name"] == "Helvetica-Bold"

    def test_paragraph_no_level(self):
        node = DocumentNode(
            id=1, node_type="paragraph", text="Texto normal",
            page_number=1, ordinal=1,
            font=FontInfo(name="Helvetica", size=12),
        )
        parsed = ParsedDocument(nodes=[node])
        blocks = parsed_to_content_blocks("doc-1", parsed)
        assert blocks[0].block_type == "paragraph"
        assert "level" not in blocks[0].metadata
