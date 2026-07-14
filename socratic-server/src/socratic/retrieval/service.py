"""Servicio de aplicación para recuperación documental.

Centraliza toda la lógica de recuperación:
- retrieve_context: combina bloques locales y recuperados
- reindex_document: reconstruye el índice de un documento
- search: búsqueda de diagnóstico

El endpoint de preguntas solo llama a retrieve_context()
y construye el prompt final.
"""
from __future__ import annotations

from socratic.domain.models import ContentBlock, Document, Study
from socratic.retrieval.models import Context, RetrievedBlock
from socratic.retrieval.txtai_backend import TxtaiDocumentRetriever
from socratic.storage.database import (
    DB,
    get_content_block,
    get_content_blocks,
    get_document,
)


class RetrievalService:
    """Servicio de recuperación documental sobre SQLite + txtai."""

    def __init__(
        self,
        retriever: TxtaiDocumentRetriever,
        db: DB,
    ) -> None:
        self._retriever = retriever
        self._db = db

    def retrieve_context(
        self,
        study: Study,
        current_block: ContentBlock,
        question: str,
        limit: int = 5,
    ) -> Context:
        """Construye el contexto combinado para la pregunta.

        Orden:
        1. Bloque actual
        2. 2 bloques anteriores
        3. 2 bloques siguientes
        4. Bloques recuperados txtai (deduplicados)
        """
        all_blocks = get_content_blocks(self._db.conn, study.document_id)
        block_map = {b.id: b for b in all_blocks}
        block_indices = {b.id: i for i, b in enumerate(all_blocks)}

        current_index = block_indices.get(current_block.id, 0)

        # Bloques locales: actual + 2 anteriores + 2 siguientes
        local_blocks = [current_block]

        start_prev = max(0, current_index - 2)
        for i in range(start_prev, current_index):
            local_blocks.append(all_blocks[i])

        end_next = min(len(all_blocks), current_index + 3)
        for i in range(current_index + 1, end_next):
            local_blocks.append(all_blocks[i])

        # Recuperación documental
        retrieved = self._retriever.search(
            study.document_id, question, limit=limit
        )

        # Excluir bloques que ya están en el contexto local (por block_id)
        local_ids = {b.id for b in local_blocks}
        deduplicated = [r for r in retrieved if r.block_id not in local_ids]

        return Context(
            local_blocks=local_blocks,
            retrieved_blocks=deduplicated,
        )

    def reindex_document(self, document_id: str) -> int:
        """Reindexa todos los bloques de un documento.

        Devuelve el número de bloques indexados.
        """
        doc = get_document(self._db.conn, document_id)
        if not doc:
            return 0

        blocks = get_content_blocks(self._db.conn, document_id)
        self._retriever.index_document(document_id, blocks)
        return len(blocks)

    def search(
        self,
        document_id: str,
        query: str,
        limit: int = 5,
    ) -> list[RetrievedBlock]:
        """Búsqueda de diagnóstico sobre un documento indexado."""
        return self._retriever.search(document_id, query, limit=limit)
