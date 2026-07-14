from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.extractor import (
    _compute_page_median_gap,
    _join_hyphenated_words,
    _merge_lines_into_paragraphs,
    _normalize_text,
    _sort_nodes_by_reading_order,
    HEADER_BAND,
    FOOTER_BAND,
    MIN_PATTERN_COVERAGE,
    MIN_PAGES_NO_DETECT,
)
from socratic.document_processing.model import DocumentNode, FontInfo


def _font(size: float = 12, bold: bool = False) -> FontInfo:
    return FontInfo(name="Helvetica", size=size, bold=bold)


class TestMergeLines:
    def test_same_line_no_merge(self):
        lines = [
            {"text": "Línea única", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=6.0)
        assert len(result) == 1
        assert result[0]["text"] == "Línea única"

    def test_merge_adjacent_lines_same_font(self):
        lines = [
            {"text": "Primera línea", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Segunda línea", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=6.0)
        assert len(result) == 1
        assert "Primera línea" in result[0]["text"]
        assert "Segunda línea" in result[0]["text"]

    def test_split_different_font(self):
        lines = [
            {"text": "Encabezado", "font": FontInfo(name="Helvetica-Bold", size=16, bold=True), "x0": 0, "x1": 100, "top": 0, "bottom": 20},
            {"text": "Párrafo", "font": _font(), "x0": 0, "x1": 100, "top": 30, "bottom": 42},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=6.0)
        assert len(result) == 2
        assert result[0]["text"] == "Encabezado"
        assert result[1]["text"] == "Párrafo"

    def test_split_large_gap(self):
        lines = [
            {"text": "Párrafo uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Párrafo dos", "font": _font(), "x0": 0, "x1": 100, "top": 50, "bottom": 62},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=6.0)
        assert len(result) == 2

    def test_merge_dynamic_threshold(self):
        """Reproduce el caso del PDF que falla: gaps de ~5.85 intra-párrafo,
        ~30.80 inter-párrafo. Con threshold=8.78 (1.5×5.85) deben fusionarse
        las líneas del mismo párrafo y separarse los párrafos distintos."""
        lines = [
            {"text": "Los modelos de regresión son modelos estadísticos", "font": _font(), "x0": 70, "x1": 382, "top": 157, "bottom": 167},
            {"text": "en los que se desea conocer la relación", "font": _font(), "x0": 70, "x1": 382, "top": 173, "bottom": 182},
            {"text": "entre una variable dependiente y explicativas", "font": _font(), "x0": 70, "x1": 382, "top": 188, "bottom": 198},
            {"text": "o covariables, ya sean cualitativas.", "font": _font(), "x0": 70, "x1": 289, "top": 203, "bottom": 213},
            {"text": "De entre las diferentes opciones que existen", "font": _font(), "x0": 56, "x1": 396, "top": 244, "bottom": 253},
            {"text": "sión destacan el modelo lineal y el logística.", "font": _font(), "x0": 56, "x1": 396, "top": 259, "bottom": 269},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=8.78)
        assert len(result) == 2
        assert "Los modelos" in result[0]["text"]
        assert "covariables" in result[0]["text"]
        assert "Dentro de las diferentes opciones" not in result[0]["text"]
        assert "De entre" in result[1]["text"]
        assert "sión destacan" in result[1]["text"]

    def test_empty_lines(self):
        result = _merge_lines_into_paragraphs([], y_threshold=6.0)
        assert result == []

    def test_three_lines_merge(self):
        lines = [
            {"text": "Línea uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Línea dos", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
            {"text": "Línea tres", "font": _font(), "x0": 0, "x1": 100, "top": 26, "bottom": 38},
        ]
        result = _merge_lines_into_paragraphs(lines, y_threshold=6.0)
        assert len(result) == 1
        assert result[0]["text"] == "Línea uno Línea dos Línea tres"


class TestComputePageMedianGap:
    def test_empty_lines(self):
        assert _compute_page_median_gap([]) is None

    def test_single_line(self):
        lines = [
            {"text": "Solo", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
        ]
        assert _compute_page_median_gap(lines) is None

    def test_two_lines_same_font(self):
        lines = [
            {"text": "Línea uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Línea dos", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
        ]
        assert _compute_page_median_gap(lines) is None

    def test_three_lines_same_font(self):
        lines = [
            {"text": "Primera", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Segunda", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
            {"text": "Tercera", "font": _font(), "x0": 0, "x1": 100, "top": 26, "bottom": 38},
        ]
        result = _compute_page_median_gap(lines)
        assert result is not None
        assert result == 1.0

    def test_filters_large_gaps(self):
        """Gaps estructurales (>1.5× line_height) deben excluirse."""
        lines = [
            {"text": "Párrafo uno línea uno", "font": _font(), "x0": 0, "x1": 100, "top": 0, "bottom": 12},
            {"text": "Párrafo uno línea dos", "font": _font(), "x0": 0, "x1": 100, "top": 13, "bottom": 25},
            {"text": "Párrafo uno línea tres", "font": _font(), "x0": 0, "x1": 100, "top": 26, "bottom": 38},
            {"text": "Párrafo dos línea uno", "font": _font(), "x0": 0, "x1": 100, "top": 80, "bottom": 92},
            {"text": "Párrafo dos línea dos", "font": _font(), "x0": 0, "x1": 100, "top": 93, "bottom": 105},
            {"text": "Párrafo dos línea tres", "font": _font(), "x0": 0, "x1": 100, "top": 106, "bottom": 118},
        ]
        result = _compute_page_median_gap(lines)
        assert result is not None
        assert result == 1.0  # Solo los gaps de 1.0 se consideran

    def test_filters_different_font(self):
        """Líneas con fuente diferente no deben considerarse."""
        lines = [
            {"text": "Título", "font": FontInfo(name="Helvetica-Bold", size=16, bold=True), "x0": 0, "x1": 100, "top": 0, "bottom": 20},
            {"text": "Párrafo uno", "font": _font(), "x0": 0, "x1": 100, "top": 30, "bottom": 42},
            {"text": "Párrafo dos", "font": _font(), "x0": 0, "x1": 100, "top": 53, "bottom": 65},
        ]
        result = _compute_page_median_gap(lines)
        assert result is None  # Solo un gap de misma fuente

    def test_realistic_page_5_scenario(self):
        """Reproduce la geometría de la página 5 del PDF que falla."""
        lines = [
            {"text": "Los modelos de regresión son modelos estadísticos", "font": _font(), "x0": 70, "x1": 382, "top": 157.0, "bottom": 167.0},
            {"text": "en los que se desea conocer la relación", "font": _font(), "x0": 70, "x1": 382, "top": 172.85, "bottom": 182.85},
            {"text": "entre una variable dependiente y explicativas", "font": _font(), "x0": 70, "x1": 382, "top": 188.7, "bottom": 198.7},
            {"text": "o covariables, ya sean cualitativas.", "font": _font(), "x0": 70, "x1": 289, "top": 204.55, "bottom": 214.55},
            {"text": "De entre las diferentes opciones que existen", "font": _font(), "x0": 56, "x1": 396, "top": 245.35, "bottom": 255.35},
            {"text": "sión destacan el modelo lineal y el logística.", "font": _font(), "x0": 56, "x1": 396, "top": 261.2, "bottom": 271.2},
        ]
        result = _compute_page_median_gap(lines)
        assert result is not None
        # Los gaps de 5.85 son los únicos aceptados (los de ~30.8 se filtran)
        assert abs(result - 5.85) < 0.01


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


class TestNormalization:
    def test_pid_replaced(self):
        assert _normalize_text("PID_00276229") == "__ID__"

    def test_copyright_replaced(self):
        assert _normalize_text("© FUOC") == "__COPY__"

    def test_year_range_replaced(self):
        assert _normalize_text("2023-2024") == "__YEAR__"

    def test_page_number_replaced(self):
        assert _normalize_text("5") == "__PAGE__"

    def test_header_pattern_normalized(self):
        text = "© FUOC • PID_00276229 5 Modelos de regresión logística"
        normalized = _normalize_text(text)
        assert "__COPY__" in normalized
        assert "__ID__" in normalized
        assert "__PAGE__" in normalized
        assert "Modelos de regresión logística" in normalized

    def test_section_reference_not_altered(self):
        """Referencias como '2.4.1' no deben alterarse (no son tokens independientes)."""
        # "2.4.1" tiene puntos, así que \b\d+\b no lo coincide completamente
        result = _normalize_text("2.4.1 Recolección")
        assert "2.4.1" in result

    def test_multiple_spaces_collapsed(self):
        assert _normalize_text("texto   con   espacios") == "texto con espacios"


class TestHeaderFooterConstants:
    def test_header_band_value(self):
        assert HEADER_BAND == 0.08

    def test_footer_band_value(self):
        assert FOOTER_BAND == 0.10

    def test_min_pattern_coverage_value(self):
        assert MIN_PATTERN_COVERAGE == 0.6

    def test_min_pages_no_detect_value(self):
        assert MIN_PAGES_NO_DETECT == 5
