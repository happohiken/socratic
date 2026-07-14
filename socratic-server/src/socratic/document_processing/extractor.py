from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from socratic.document_processing.classifier import classify_node, _starts_with_list_prefix
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
        title = ""
        page_number: int | None = None

        if hasattr(entry, "get_title"):
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


def _is_true_bold(fontname: str) -> bool:
    """Return True if *fontname* denotes a true bold font family.

    pdfplumber sometimes appends ``',Bold'`` to the font name when a
    character is rendered in bold but the base family is not bold
    (e.g. ``ITCStoneSerifStdMedium,Bold``).  We only want to detect
    fonts whose *family* name contains "Bold" (e.g. ``ITCStoneSerifStdBold``).
    """
    if "Bold" not in fontname:
        return False
    if ",Bold" in fontname:
        return False
    return True


def _get_font_info(chars: list[dict]) -> FontInfo:
    if not chars:
        return FontInfo(name="?", size=0, bold=False, italic=False)
    fontname = chars[0].get("fontname", "?") or "?"
    size = chars[0].get("size", 0) or 0
    bold = any(_is_true_bold(c.get("fontname", "") or "") for c in chars)
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


# ── Umbral de fusión de líneas ──────────────────────────────────────
MEDIAN_MULTIPLIER = 1.5
DEFAULT_Y_THRESHOLD = 6.0


def _compute_page_median_gap(lines: list[dict]) -> float | None:
    """Return the median gap between consecutive same-font lines.

    Only considers gaps that are plausible line-height candidates:
    positive, same font family, and at most 1.5× the line height.
    Returns None if fewer than 2 candidates are found.
    """
    if len(lines) < 3:
        return None

    candidates: list[float] = []
    prev_font = None
    prev_bottom = None

    for line in lines:
        font = line["font"]
        top = line["top"]
        bottom = line["bottom"]
        line_height = bottom - top

        if prev_font is not None and font.name == prev_font:
            gap = top - prev_bottom
            if gap > 0 and gap <= 1.5 * line_height:
                candidates.append(gap)

        prev_font = font.name
        prev_bottom = bottom

    if len(candidates) < 2:
        return None

    candidates.sort()
    n = len(candidates)
    if n % 2 == 1:
        return candidates[n // 2]
    return (candidates[n // 2 - 1] + candidates[n // 2]) / 2.0


def _merge_lines_into_paragraphs(
    lines: list[dict],
    y_threshold: float,
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

        if y_gap <= y_threshold and same_font and not _starts_with_list_prefix(line["text"]):
            current["text"] += " " + line["text"]
            current["x1"] = line["x1"]
            current["bottom"] = line["bottom"]
        else:
            merged.append(current)
            current = dict(line)

    if current is not None:
        merged.append(current)

    return merged


# ── Detección de cabeceras y pies repetidos ─────────────────────────
# Calibrados empíricamente sobre documentos académicos y técnicos.
# Los PDFs reales muestran cabeceras en el 6-8% superior y pies
# en el 90-95% inferior. Se usan márgenes de seguridad para capturar
# variaciones entre documentos.
HEADER_BAND = 0.08
FOOTER_BAND = 0.10

# Variación de renderizado observada en documentos reales: ≤ 5 pt.
POSITION_TOLERANCE = 5

# 3 apariciones en ≥10 páginas es evidencia suficiente de un patrón
# de cabecera/pie. Para documentos cortos se exige más para evitar
# falsos positivos (ej. tabla con encabezado repetido dos veces).
MIN_FREQ_LONG_DOC = 3
MIN_FREQ_SHORT_DOC = 4
MIN_PAGES_NO_DETECT = 5

# Un patrón debe aparecer en ≥60% de las páginas para ser eliminado.
# El 60% (no 50%) es conservador: una cabecera editorial puede faltar
# en portada, índice o páginas de secciones.
MIN_PATTERN_COVERAGE = 0.6

# ── Patrones de normalización ───────────────────────────────────────
# Orden importa: PID y copyright se reemplazan primero para que
# el regex de número de página no toque los números dentro de
# PID_00276229. El patrón de número de página excluye números que
# forman parte de referencias con puntos (ej. "2.4.1") usando
# lookbehind/lookahead para puntos.
_NORMALIZATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"PID_\d+", re.IGNORECASE), "__ID__"),
    (re.compile(r"©\s*\w+"), "__COPY__"),
    (re.compile(r"\b\d{4}-\d{4}\b"), "__YEAR__"),
    # (?<!\.) excluye números precedidos por punto;
    # (?!\.) excluye números seguidos por punto.
    # Así "2.4.1" no se altera pero "5" sí.
    (re.compile(r"(?<!\.)\b\d+\b(?!\.)"), "__PAGE__"),
]


@dataclass
class _HeaderFooterPattern:
    """Representa un patrón de cabecera o pie detectado."""
    label: str  # "HEADER" o "FOOTER"
    normalized_text: str
    font_key: str  # "name:size"
    y_min: float
    y_max: float
    total_pages: int
    appearing_pages: list[int]

    @property
    def frequency(self) -> int:
        return len(self.appearing_pages)

    @property
    def coverage(self) -> float:
        return self.frequency / self.total_pages if self.total_pages > 0 else 0.0

    @property
    def decision(self) -> str:
        return "REMOVE" if self.coverage >= MIN_PATTERN_COVERAGE else "KEEP"

    @property
    def y_percentage(self) -> str:
        mid = (self.y_min + self.y_max) / 2
        return f"{mid:.1f}"


def _normalize_text(text: str) -> str:
    """Replace page numbers, PIDs, copyright, and years with placeholders."""
    for pattern, replacement in _NORMALIZATION_PATTERNS:
        text = pattern.sub(replacement, text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _font_key(font: FontInfo) -> str:
    return f"{font.name}:{font.size}"


def _extract_candidates(page) -> list[dict]:
    """Extract candidate lines from the header and footer bands of a page."""
    page_height = page.height
    header_top = 0
    header_bottom = page_height * HEADER_BAND
    footer_top = page_height * (1 - FOOTER_BAND)
    footer_bottom = page_height

    text_lines = page.extract_text_lines()
    candidates: list[dict] = []

    for tl in text_lines:
        top = tl.get("top", 0)
        bottom = tl.get("bottom", 0)
        text = tl.get("text", "").strip()
        if not text:
            continue

        chars = tl.get("chars", [])
        font = _get_font_info(chars)

        # Header band
        if bottom <= header_bottom + POSITION_TOLERANCE:
            candidates.append({
                "text": text,
                "normalized": _normalize_text(text),
                "font": font,
                "font_key": _font_key(font),
                "y_mid": (top + bottom) / 2,
                "top": top,
                "bottom": bottom,
                "band": "header",
            })
        # Footer band
        elif top >= footer_top - POSITION_TOLERANCE:
            candidates.append({
                "text": text,
                "normalized": _normalize_text(text),
                "font": font,
                "font_key": _font_key(font),
                "y_mid": (top + bottom) / 2,
                "top": top,
                "bottom": bottom,
                "band": "footer",
            })

    return candidates


def _group_candidates(
    all_candidates: list[tuple[int, dict]],
) -> dict[tuple[str, str], dict]:
    """Group candidates by (normalized_text, font_key)."""
    groups: dict[tuple[str, str], dict] = {}
    for page_num, cand in all_candidates:
        key = (cand["normalized"], cand["font_key"])
        if key not in groups:
            groups[key] = {
                "normalized": cand["normalized"],
                "font_key": cand["font_key"],
                "pages": [],
                "y_mins": [],
                "y_maxs": [],
            }
        groups[key]["pages"].append(page_num)
        groups[key]["y_mins"].append(cand["y_mid"])
        groups[key]["y_maxs"].append(cand["y_mid"])
    return groups


def _classify_patterns(
    groups: dict[tuple[str, str], dict],
    total_pages: int,
    page_heights: dict[int, float],
) -> list[_HeaderFooterPattern]:
    """Classify groups as header/footer patterns and compute confidence."""
    patterns: list[_HeaderFooterPattern] = []

    for (normalized, font_key), info in groups.items():
        pages = info["pages"]
        freq = len(pages)
        y_mins = info["y_mins"]
        y_maxs = info["y_maxs"]

        # Determine frequency threshold
        if total_pages >= 10:
            min_freq = MIN_FREQ_LONG_DOC
        elif total_pages >= MIN_PAGES_NO_DETECT:
            min_freq = MIN_FREQ_SHORT_DOC
        else:
            continue  # Too few pages

        if freq < min_freq:
            continue

        y_min = min(y_mins)
        y_max = max(y_maxs)

        # Determine band from vertical position (relative to page height)
        # Use the average page height of the pages where this pattern appears
        avg_height = sum(page_heights.get(p, 792) for p in pages) / len(pages)
        y_mid_rel = ((y_min + y_max) / 2) / avg_height

        if y_mid_rel < 0.25:
            label = "HEADER"
        elif y_mid_rel > 0.75:
            label = "FOOTER"
        else:
            continue  # Ambiguous position — conserve

        patterns.append(
            _HeaderFooterPattern(
                label=label,
                normalized_text=normalized,
                font_key=font_key,
                y_min=y_min,
                y_max=y_max,
                total_pages=total_pages,
                appearing_pages=pages,
            )
        )

    return patterns


def _pages_to_remove(patterns: list[_HeaderFooterPattern]) -> dict[int, set[int]]:
    """Return {page_num: {line_index}} for lines to remove."""
    to_remove: dict[int, set[int]] = defaultdict(set)

    for pattern in patterns:
        if pattern.decision != "REMOVE":
            continue

        for page_num in pattern.appearing_pages:
            # We'll match by normalized text + font + position later
            pass

    return to_remove


def _remove_patterns_from_lines(
    lines: list[dict],
    patterns: list[_HeaderFooterPattern],
    page_number: int,
) -> list[dict]:
    """Remove lines that match any REMOVE pattern for this page."""
    result: list[dict] = []

    for line in lines:
        text = line["text"]
        font = line["font"]
        top = line["top"]
        bottom = line["bottom"]
        page_height = bottom - top

        # Quick check: is this line in the header/footer band?
        in_band = False
        for pattern in patterns:
            if pattern.decision != "REMOVE":
                continue
            if (
                pattern.label == "HEADER"
                and bottom <= pattern.y_max + POSITION_TOLERANCE
            ) or (
                pattern.label == "FOOTER"
                and top >= pattern.y_min - POSITION_TOLERANCE
            ):
                in_band = True
                if _normalize_text(text) == pattern.normalized_text and _font_key(font) == pattern.font_key:
                    break

        if in_band:
            continue

        result.append(line)

    return result


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

        # Detectar patrones en TODAS las páginas (no solo las del rango),
        # para que la detección tenga suficiente evidencia.
        all_candidates_all: list[tuple[int, dict]] = []
        page_heights_all: dict[int, float] = {}
        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1
            candidates = _extract_candidates(page)
            for cand in candidates:
                all_candidates_all.append((page_number, cand))
            page_heights_all[page_number] = page.height

        total_pages_all = len(pdf.pages)
        groups_all = _group_candidates(all_candidates_all)
        all_patterns = _classify_patterns(groups_all, total_pages_all, page_heights_all)

        nodes: list[DocumentNode] = []
        ordinal = 0

        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1

            if page_range:
                if page_number < start_page or page_number > end_page:
                    continue

            lines = _extract_lines_from_page(page)
            lines = _remove_patterns_from_lines(lines, all_patterns, page_number)

            page_median = _compute_page_median_gap(lines)
            y_threshold = (
                MEDIAN_MULTIPLIER * page_median
                if page_median is not None
                else DEFAULT_Y_THRESHOLD
            )
            paragraphs = _merge_lines_into_paragraphs(lines, y_threshold)

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


def _join_hyphenated_words(text: str) -> str:
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def inspect_header_footer_patterns(
    pdf_path: Path,
    page_range: tuple[int, int] | None = None,
) -> list[_HeaderFooterPattern]:
    """Public API for diagnostic output in inspect-pdf.

    Returns the list of detected header/footer patterns with metadata.
    """
    with pdfplumber.open(pdf_path) as pdf:
        start_page = page_range[0] if page_range else 1
        end_page = page_range[1] if page_range else len(pdf.pages)

        all_candidates: list[tuple[int, dict]] = []
        page_heights: dict[int, float] = {}
        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1
            if page_range:
                if page_number < start_page or page_number > end_page:
                    continue
            candidates = _extract_candidates(page)
            for cand in candidates:
                all_candidates.append((page_number, cand))
            page_heights[page_number] = page.height

        total_pages = end_page - start_page + 1 if page_range else len(pdf.pages)
        groups = _group_candidates(all_candidates)
        return _classify_patterns(groups, total_pages, page_heights)
