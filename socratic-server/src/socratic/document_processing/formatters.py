from __future__ import annotations

import json
from typing import Any

from socratic.document_processing.model import ParsedDocument


def format_text(doc: ParsedDocument) -> str:
    parts: list[str] = []

    if doc.title:
        parts.append(f"Document title: {doc.title}")

    if doc.toc:
        parts.append("TOC:")
        for i, entry in enumerate(doc.toc, 1):
            page_str = f"page {entry.page_number}" if entry.page_number else "no page"
            parts.append(f"  [{i}] {entry.title} ............................ {page_str}")

    parts.append("")
    for node in doc.nodes:
        parts.append(_format_node_text(node))
        parts.append("")

    return "\n".join(parts)


def _format_node_text(node: Any) -> str:
    parts = [f"[{node.id:04d}] page={node.page_number} type={node.node_type}"]
    if node.level is not None:
        parts.append(f" level={node.level}")
    if node.font:
        parts.append(f" font={node.font.name} size={node.font.size:.1f}")
    if node.bbox:
        parts.append(f" bbox=({node.bbox[0]:.1f},{node.bbox[1]:.1f},{node.bbox[2]:.1f},{node.bbox[3]:.1f})")
    if node.node_type == "list" and node.list_items:
        parts.append(f" is_ordered={node.is_ordered}")
        parts.append(f" items={len(node.list_items)}")
    return "".join(parts) + "\n" + node.text


def format_json(doc: ParsedDocument) -> str:
    data: dict[str, Any] = {}
    if doc.title:
        data["title"] = doc.title
    if doc.toc:
        data["toc"] = [
            {
                "title": e.title,
                "level": e.level,
                "page_number": e.page_number,
            }
            for e in doc.toc
        ]
    data["nodes"] = [
        {
            "id": n.id,
            "type": n.node_type,
            "level": n.level,
            "text": n.text,
            "page": n.page_number,
            "ordinal": n.ordinal,
            "parent_id": n.parent_id,
            "bbox": n.bbox,
            "font": {
                "name": n.font.name,
                "size": n.font.size,
                "bold": n.font.bold,
                "italic": n.font.italic,
            } if n.font else None,
            "list_items": (
                [{"text": it.text, "marker": it.marker} for it in n.list_items]
                if n.list_items
                else None
            ),
            "is_ordered": n.is_ordered if n.node_type == "list" else None,
        }
        for n in doc.nodes
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)
