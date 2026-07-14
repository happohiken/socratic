"""Adaptador: ParsedDocument -> modelos de dominio persistentes.

El parser documental (parse_pdf) produce un ParsedDocument con
DocumentNode que contiene la informacion estructural extraida del PDF.
Los modelos de dominio (Document, ContentBlock) son los que se
persisten en SQLite.

Este modulo expone una unica funcion publica que realiza la conversion.

Identificadores
---------------
DocumentNode.id es el ordinal de aparicion durante el parsing
(1, 2, 3, ...). NO se reutiliza como ContentBlock.id porque:

  * Es un entero secuencial, no un identificador unico global.
  * Cambia si se re-parsea el documento con parametros distintos
    (rango de paginas, umbral de fusion).
  * No es estable frente a cambios en el orden de lectura
    (reordenacion por coordenadas).
  * ContentBlock.id es un UUID que garantiza unicidad global y
    estabilidad a lo largo del ciclo de vida del documento.

Los metadatos (bbox, font, level) se conservan en el campo
ContentBlock.metadata aunque la primera version no los consulte.
"""
from __future__ import annotations

from dataclasses import asdict

from socratic.document_processing.model import ParsedDocument, TocEntry
from socratic.domain.models import ContentBlock, Document


def _toc_to_dict(toc: list[TocEntry]) -> list[dict]:
    return [
        {"title": e.title, "level": e.level, "page_number": e.page_number}
        for e in toc
    ]


def parsed_to_document(parsed: ParsedDocument, filename: str) -> Document:
    """Convertir un ParsedDocument en un Document persistente."""
    pages = {n.page_number for n in parsed.nodes}
    return Document(
        filename=filename,
        page_count=len(pages) if pages else 0,
        block_count=len(parsed.nodes),
        metadata={
            "title": parsed.title,
            "toc": _toc_to_dict(parsed.toc),
        },
    )


def parsed_to_content_blocks(
    document_id: str,
    parsed: ParsedDocument,
) -> list[ContentBlock]:
    """Convertir los nodos de un ParsedDocument en ContentBlock."""
    blocks: list[ContentBlock] = []
    for node in parsed.nodes:
        meta: dict = {}
        if node.bbox is not None:
            meta["bbox"] = list(node.bbox)
        if node.font is not None:
            meta["font"] = asdict(node.font)
        if node.level is not None:
            meta["level"] = node.level

        block_type = node.node_type
        if block_type in ("list_item", "list"):
            block_type = "list"

        blocks.append(
            ContentBlock(
                document_id=document_id,
                ordinal=node.ordinal,
                text=node.text,
                page_number=node.page_number,
                block_type=block_type,
                metadata=meta,
            )
        )
    return blocks
