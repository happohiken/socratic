from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from socratic.document_processing.classifier import classify_node, _is_list_item
from socratic.document_processing.model import FontInfo


def _font(size: float = 12, bold: bool = False, italic: bool = False) -> FontInfo:
    return FontInfo(name="Helvetica", size=size, bold=bold, italic=italic)


def _bold_font(size: float = 14) -> FontInfo:
    return FontInfo(name="Helvetica-Bold", size=size, bold=True, italic=False)


class TestIsListItem:
    def test_bullet_point(self):
        assert _is_list_item("\u2022 Elemento") is True

    def test_hyphen_prefix(self):
        assert _is_list_item("- Elemento") is True

    def test_en_dash_prefix(self):
        assert _is_list_item("\u2013 Elemento") is True

    def test_number_prefix(self):
        assert _is_list_item("1. Elemento") is True
        assert _is_list_item("2) Elemento") is True

    def test_letter_prefix(self):
        assert _is_list_item("a. Elemento") is True
        assert _is_list_item("B) Elemento") is True

    def test_roman_prefix(self):
        assert _is_list_item("I. Elemento") is True
        assert _is_list_item("X. Elemento") is True

    def test_not_list_regular_text(self):
        assert _is_list_item("Este es un párrafo normal.") is False

    def test_not_list_just_number(self):
        assert _is_list_item("123") is False


class TestClassifyNode:
    def test_heading_bold(self):
        result, level = classify_node("Capítulo 1", _bold_font(14))
        assert result == "heading"
        assert level == 1

    def test_heading_bold_small(self):
        result, level = classify_node("Introducción", _bold_font(12))
        assert result == "heading"
        assert level == 1

    def test_list_item_bullet(self):
        result, level = classify_node("\u2022 Primer objetivo", _font(12))
        assert result == "list_item"
        assert level is None

    def test_list_item_hyphen(self):
        result, level = classify_node("- Primer objetivo", _font(12))
        assert result == "list_item"
        assert level is None

    def test_list_item_number(self):
        result, level = classify_node("1. Primer objetivo", _font(12))
        assert result == "list_item"
        assert level is None

    def test_paragraph_normal(self):
        result, level = classify_node("Este es un párrafo normal de texto.", _font(12))
        assert result == "paragraph"
        assert level is None

    def test_paragraph_empty(self):
        result, level = classify_node("", _font(12))
        assert result == "paragraph"
        assert level is None

    def test_heading_long_bold(self):
        long_text = "A" * 90
        result, level = classify_node(long_text, _bold_font(16))
        assert result == "heading"
        assert level == 1

    def test_unknown_font_size_large(self):
        result, level = classify_node("Título largo de sección", FontInfo(name="?", size=0, bold=False))
        assert result == "paragraph"

    def test_paragraph_ending_with_period(self):
        result, level = classify_node("Este es un párrafo que termina con punto.", _font(12))
        assert result == "paragraph"
