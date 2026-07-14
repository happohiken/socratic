from __future__ import annotations

from socratic.document_processing.model import FontInfo


_LIST_PREFIXES = (
    "\u2022", "\u2013", "\u2014", "\u25cb", "\u25cf", "\u25a0",
    "\u25e6", "\u25b8", "\u25b9", "\u25c2", "\u25c3",
    "\u25b6", "\u25b7", "\u25d8", "\u25d9",
    "\u27a1", "\u2713", "\u2714", "\u2715", "\u2716",
    "\u2981", "\u2982", "\u2983", "\u2984", "\u2985",
    "\u2986", "\u2987", "\u2988", "\u2989",
    "-",
)


def classify_node(text: str, font: FontInfo) -> tuple[str, int | None]:
    stripped = text.strip()
    if not stripped:
        return "paragraph", None

    if font.size > 0 and font.bold:
        return "heading", 1

    if _is_list_item(stripped):
        return "list_item", None

    if _looks_like_heading(stripped, font):
        return "heading", 2

    return "paragraph", None


def _is_list_item(text: str) -> bool:
    first_char = text[0]
    if first_char in _LIST_PREFIXES:
        return True
    import re
    if re.match(r"^\d+[\.\)\:]\s", text):
        return True
    if re.match(r"^[a-zA-Z][\.\)\:]\s", text):
        return True
    if re.match(r"^[IVXLC]+[\.\)\:]\s", text.upper()):
        return True
    return False


def _looks_like_heading(text: str, font: FontInfo) -> bool:
    if font.size > 0 and font.size >= 14:
        if len(text) <= 100:
            return True
    if len(text) <= 60 and not text.endswith((".", ",", ";", ")", "]")):
        if font.size > 0 and font.bold:
            return True
    return False


def _starts_with_list_prefix(text: str) -> bool:
    """Return True if *text* begins with a character that marks a list item."""
    stripped = text.lstrip()
    if not stripped:
        return False
    first_char = stripped[0]
    if first_char in _LIST_PREFIXES:
        return True
    import re
    if re.match(r"^\d+[\.\)\:]\s", stripped):
        return True
    if re.match(r"^[a-zA-Z][\.\)\:]\s", stripped):
        return True
    if re.match(r"^[IVXLC]+[\.\)\:]\s", stripped.upper()):
        return True
    return False
