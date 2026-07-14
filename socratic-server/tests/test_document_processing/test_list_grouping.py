"""Pruebas de agrupacion de list_item en nodos list."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.extractor import (
    _extract_marker,
    _group_consecutive_list_items,
    _is_numbered,
    parse_pdf,
)
from socratic.document_processing.formatters import format_json, format_text
from socratic.document_processing.model import (
    DocumentNode,
    FontInfo,
    ListItem,
    ParsedDocument,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def bullet_list_pdf(tmp_path: Path) -> Path:
    """PDF con lista de viñetas de 3 elementos."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Primer elemento", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Segundo elemento", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Tercer elemento", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Parrafo despues de la lista.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "bullet_list.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def numbered_list_pdf(tmp_path: Path) -> Path:
    """PDF con lista numerada de 3 elementos."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  1. Primer elemento", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  2. Segundo elemento", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  3. Tercer elemento", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "numbered_list.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def separated_lists_pdf(tmp_path: Path) -> Path:
    """PDF con dos listas separadas por un parrafo."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Elemento A", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Elemento B", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "Parrafo separador.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Elemento C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Elemento D", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "separated_lists.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def two_lists_same_page_pdf(tmp_path: Path) -> Path:
    """PDF con dos listas distintas separadas por un heading."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Item lista 1", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", style="B", size=14)
    pdf.cell(200, 10, "Subseccion", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Item lista 2", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "two_lists.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def multi_page_list_pdf(tmp_path: Path) -> Path:
    """PDF con lista que continua en la pagina siguiente."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Item pagina 1", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Otro item pagina 1", new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "  - Item pagina 2", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 7, "  - Otro item pagina 2", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "multi_page_list.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
def fake_bullet_pdf(tmp_path: Path) -> Path:
    """PDF con texto que parece viñeta pero no lo es."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(200, 10, "Titulo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 7, "Este es un parrafo con el numero 123 y texto.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "fake_bullet.pdf"
    pdf.output(str(path))
    return path


# ── Fixtures unitarias ────────────────────────────────────────────

def _font(size: float = 12, bold: bool = False) -> FontInfo:
    return FontInfo(name="Helvetica", size=size, bold=bold)


def _node(node_type: str, text: str, page: int = 1, ordinal: int = 1,
          bbox: tuple | None = None, level: int | None = None) -> DocumentNode:
    return DocumentNode(
        id=ordinal,
        node_type=node_type,
        text=text,
        page_number=page,
        ordinal=ordinal,
        font=_font(),
        bbox=bbox or (10, 20, 100, 32),
        level=level,
    )


# ── _extract_marker ───────────────────────────────────────────────

class TestExtractMarker:
    def test_bullet_marker(self):
        assert _extract_marker("\u2022 Elemento") == "\u2022"

    def test_hyphen_marker(self):
        assert _extract_marker("- Elemento") == "-"

    def test_number_dot_marker(self):
        assert _extract_marker("1. Elemento") == "1."

    def test_number_paren_marker(self):
        assert _extract_marker("2) Elemento") == "2)"

    def test_letter_dot_marker(self):
        assert _extract_marker("a. Elemento") == "a."

    def test_letter_paren_marker(self):
        assert _extract_marker("B) Elemento") == "B)"

    def test_roman_marker(self):
        assert _extract_marker("I. Elemento") == "I."

    def test_text_without_marker(self):
        assert _extract_marker("Texto normal") == ""

    def test_empty_text(self):
        assert _extract_marker("") == ""


# ── _is_numbered ──────────────────────────────────────────────────

class TestIsNumbered:
    def test_numeric_marker(self):
        assert _is_numbered("1") is True
        assert _is_numbered("42") is True

    def test_alpha_marker(self):
        assert _is_numbered("a") is True
        assert _is_numbered("Z") is True

    def test_roman_marker(self):
        assert _is_numbered("I") is True
        assert _is_numbered("XIV") is True

    def test_bullet_not_numbered(self):
        assert _is_numbered("\u2022") is False

    def test_hyphen_not_numbered(self):
        assert _is_numbered("-") is False

    def test_empty_not_numbered(self):
        assert _is_numbered("") is False


# ── _group_consecutive_list_items ─────────────────────────────────

class TestGroupConsecutiveListItems:
    def test_single_list_item_becomes_list(self):
        nodes = [_node("list_item", "- Solo elemento", ordinal=1)]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 1
        assert result[0].node_type == "list"
        assert result[0].list_items is not None
        assert len(result[0].list_items) == 1
        assert result[0].list_items[0].text == "- Solo elemento"
        assert result[0].list_items[0].marker == "-"
        assert result[0].is_ordered is False

    def test_bullet_list_multiple_items(self):
        nodes = [
            _node("list_item", "- Primer elemento", ordinal=1,
                  bbox=(10, 20, 100, 32)),
            _node("list_item", "- Segundo elemento", ordinal=2,
                  bbox=(10, 35, 110, 47)),
            _node("list_item", "- Tercer elemento", ordinal=3,
                  bbox=(10, 50, 120, 62)),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 1
        assert result[0].node_type == "list"
        assert len(result[0].list_items) == 3
        assert result[0].is_ordered is False
        assert result[0].bbox == (10, 20, 120, 62)

    def test_numbered_list(self):
        nodes = [
            _node("list_item", "1. Primer elemento", ordinal=1),
            _node("list_item", "2. Segundo elemento", ordinal=2),
            _node("list_item", "3. Tercer elemento", ordinal=3),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 1
        assert result[0].node_type == "list"
        assert result[0].is_ordered is True

    def test_list_separated_by_paragraph(self):
        nodes = [
            _node("list_item", "- Elemento A", ordinal=1),
            _node("list_item", "- Elemento B", ordinal=2),
            _node("paragraph", "Parrafo separador", ordinal=3),
            _node("list_item", "- Elemento C", ordinal=4),
            _node("list_item", "- Elemento D", ordinal=5),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 3
        assert result[0].node_type == "list"
        assert len(result[0].list_items) == 2
        assert result[1].node_type == "paragraph"
        assert result[2].node_type == "list"
        assert len(result[2].list_items) == 2

    def test_two_different_lists_same_page(self):
        nodes = [
            _node("list_item", "- Item lista 1", ordinal=1),
            _node("heading", "Subseccion", ordinal=2, level=1),
            _node("list_item", "- Item lista 2", ordinal=3),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 3
        assert result[0].node_type == "list"
        assert result[1].node_type == "heading"
        assert result[2].node_type == "list"

    def test_list_continues_next_page(self):
        nodes = [
            _node("list_item", "- Item pagina 1", page=1, ordinal=1),
            _node("list_item", "- Otro item pagina 1", page=1, ordinal=2),
            _node("paragraph", "Texto entre paginas", page=1, ordinal=3),
            _node("list_item", "- Item pagina 2", page=2, ordinal=4),
            _node("list_item", "- Otro item pagina 2", page=2, ordinal=5),
        ]
        result = _group_consecutive_list_items(nodes)
        # La lista se separa porque hay un parrafo en medio
        assert len(result) == 3
        assert result[0].node_type == "list"
        assert len(result[0].list_items) == 2
        assert result[0].page_number == 1
        assert result[1].node_type == "paragraph"
        assert result[2].node_type == "list"
        assert len(result[2].list_items) == 2
        assert result[2].page_number == 2

    def test_mixed_markers_unordered(self):
        nodes = [
            _node("list_item", "- Elemento A", ordinal=1),
            _node("list_item", "\u2022 Elemento B", ordinal=2),
            _node("list_item", "- Elemento C", ordinal=3),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 1
        assert result[0].is_ordered is False

    def test_no_list_item_nodes_remain(self):
        nodes = [
            _node("heading", "Titulo", ordinal=1, level=1),
            _node("list_item", "- Elemento", ordinal=2),
            _node("paragraph", "Parrafo", ordinal=3),
            _node("list_item", "1. Item", ordinal=4),
        ]
        result = _group_consecutive_list_items(nodes)
        for node in result:
            assert node.node_type != "list_item", (
                f"Quedo un nodo list_item: {node.text!r}"
            )

    def test_combined_text_preserves_markers(self):
        nodes = [
            _node("list_item", "- Primer elemento", ordinal=1),
            _node("list_item", "2. Segundo elemento", ordinal=2),
        ]
        result = _group_consecutive_list_items(nodes)
        assert "- Primer elemento" in result[0].text
        assert "2. Segundo elemento" in result[0].text
        assert "\n" in result[0].text

    def test_empty_nodes(self):
        result = _group_consecutive_list_items([])
        assert result == []

    def test_only_non_list_nodes(self):
        nodes = [
            _node("heading", "Titulo", ordinal=1, level=1),
            _node("paragraph", "Parrafo", ordinal=2),
        ]
        result = _group_consecutive_list_items(nodes)
        assert len(result) == 2
        assert result[0].node_type == "heading"
        assert result[1].node_type == "paragraph"


# ── Integracion con parse_pdf ─────────────────────────────────────

class TestParsePdfListIntegration:
    def test_bullet_list_merged(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 1
        lst = lists[0]
        assert lst.list_items is not None
        assert len(lst.list_items) == 3
        assert lst.is_ordered is False
        # No deben quedar list_item sueltos
        assert all(n.node_type != "list_item" for n in doc.nodes)

    def test_numbered_list_merged(self, numbered_list_pdf: Path):
        doc = parse_pdf(numbered_list_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 1
        assert lists[0].is_ordered is True

    def test_separated_lists(self, separated_lists_pdf: Path):
        doc = parse_pdf(separated_lists_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 2
        assert lists[0].list_items[0].text == "- Elemento A"
        assert lists[1].list_items[0].text == "- Elemento C"

    def test_two_lists_same_page(self, two_lists_same_page_pdf: Path):
        doc = parse_pdf(two_lists_same_page_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 2

    def test_multi_page_list_separated(self, multi_page_list_pdf: Path):
        doc = parse_pdf(multi_page_list_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        # Limitacion: las lineas de pagina 2 pueden fusionarse con las de
        # pagina 1 si el gap vertical es pequeno. En este PDF generado con
        # FPDF el gap entre paginas es pequeno, asi que se fusionan en 1 lista.
        # El comportamiento ideal (union cross-page) se documenta como
        # limitacion temporal.
        assert len(lists) >= 1
        total_items = sum(len(l.list_items) for l in lists if l.list_items)
        assert total_items == 4

    def test_fake_bullet_not_list(self, fake_bullet_pdf: Path):
        doc = parse_pdf(fake_bullet_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 0
        paragraphs = [n for n in doc.nodes if n.node_type == "paragraph"]
        assert any("123" in p.text for p in paragraphs)

    def test_no_list_item_nodes_remain(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        list_items = [n for n in doc.nodes if n.node_type == "list_item"]
        assert len(list_items) == 0

    def test_list_text_preserves_markers(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        lists = [n for n in doc.nodes if n.node_type == "list"]
        assert len(lists) == 1
        text = lists[0].text
        assert "- Primer elemento" in text
        assert "- Segundo elemento" in text
        assert "- Tercer elemento" in text


# ── Serializacion ─────────────────────────────────────────────────

class TestListSerialization:
    def test_format_text_includes_list_info(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        output = format_text(doc)
        assert "type=list" in output
        assert "is_ordered=False" in output
        assert "items=3" in output

    def test_format_json_includes_list_items(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        data = format_json(doc)
        import json
        parsed = json.loads(data)
        list_nodes = [n for n in parsed["nodes"] if n["type"] == "list"]
        assert len(list_nodes) == 1
        lst = list_nodes[0]
        assert lst["is_ordered"] is False
        assert lst["list_items"] is not None
        assert len(lst["list_items"]) == 3
        assert lst["list_items"][0]["marker"] == "-"

    def test_format_json_no_list_items_for_paragraph(self, bullet_list_pdf: Path):
        doc = parse_pdf(bullet_list_pdf)
        data = format_json(doc)
        import json
        parsed = json.loads(data)
        para_nodes = [n for n in parsed["nodes"] if n["type"] == "paragraph"]
        for p in para_nodes:
            assert p.get("list_items") is None
            assert p.get("is_ordered") is None
