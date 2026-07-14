from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.extractor import (
    _join_hyphenated_words,
    _merge_lines_into_paragraphs,
    _sort_nodes_by_reading_order,
)
from socratic.document_processing.model import DocumentNode, FontInfo


def _font(size: float = 12, bold: bool = False) -> FontInfo:
    return FontInfo(name="Helvetica", size=size, bold=bold)


class TestMergeLines:
    def test_same_line_no_merge(self):
        lines = [
            {"text": "Línea única", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
        ]
        result = _merge_lines_into_paragraphs(lines)
        assert len(result) == 1
        assert result[0]["text"] == "Línea única"

    def test_merge_adjacent_lines_same_font(self):
        lines = [
            {"text": "Primera línea", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Segunda línea", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
        ]
        result = _merge_lines_into_paragraphs(lines)
        assert len(result) == 1
        assert "Primera línea" in result[0]["text"]
        assert "Segunda línea" in result[0]["text"]

    def test_split_different_font(self):
        lines = [
            {"text": "Encabezado", "font": FontInfo(name="Helvetica-Bold", size=16, bold=True), "x0": 0, "x1": 100, "top": 0, "bottom": 20},
            {"text": "Párrafo", "font": _font(), "x0": 0, "x1": 100, "top": 30, "bottom": 42},
        ]
        result = _merge_lines_into_paragraphs(lines)
        assert len(result) == 2
        assert result[0]["text"] == "Encabezado"
        assert result[1]["text"] == "Párrafo"

    def test_split_large_gap(self):
        lines = [
            {"text": "Párrafo uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Párrafo dos", "font": _font(), "x0": 0, "x1": 100, "top": 50, "bottom": 62},
        ]
        result = _merge_lines_into_paragraphs(lines)
        assert len(result) == 2

    def test_empty_lines(self):
        result = _merge_lines_into_paragraphs([])
        assert result == []

    def test_three_lines_merge(self):
        lines = [
            {"text": "Línea uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Línea dos", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
            {"text": "Línea tres", "font": _font(), "x0": 0, "x1": 100, "top": 26, "bottom": 38},
        ]
        result = _merge_lines_into_paragraphs(lines)
        assert len(result) == 1
        assert result[0]["text"] == "Línea uno Línea dos Línea tres"


class TestHyphenation:
    def test_join_hyphenated_word(self):
        result = _join_hyphenated_words("palabra-\nsegunda")
        assert result == "palabrasegunda"

    def test_no_hyphen(self):
        result = _join_hyphenated_words("texto normal")
        assert result == "texto normal"

    def test_hyphen_at_end_of_line(self):
        result = _join_hyphenated_words("multi-\nple")
        assert result == "multiple"

    def test_multiple_hyphens(self):
        result = _join_hyphenated_words("primera-\nsegunda-\ntercera")
        # El regex une todas las palabras partidas por guion
        assert result == "primerasegundatercera"


class TestSortNodes:
    def test_sort_by_page_then_y(self):
        nodes = [
            DocumentNode(id=1, node_type="paragraph", text="p2-top", page_number=2, ordinal=1, bbox=(0, 100, 100, 112)),
            DocumentNode(id=2, node_type="paragraph", text="p1-bottom", page_number=1, ordinal=2, bbox=(0, 200, 100, 212)),
            DocumentNode(id=3, node_type="paragraph", text="p1-top", page_number=1, ordinal=3, bbox=(0, 50, 100, 62)),
        ]
        result = _sort_nodes_by_reading_order(nodes)
        assert result[0].text == "p1-top"
        assert result[1].text == "p1-bottom"
        assert result[2].text == "p2-top"

    def test_empty_list(self):
        assert _sort_nodes_by_reading_order([]) == []

    def test_single_node(self):
        nodes = [DocumentNode(id=1, node_type="paragraph", text="solo", page_number=1, ordinal=1, bbox=(0, 0, 100, 12))]
        result = _sort_nodes_by_reading_order(nodes)
        assert len(result) == 1
