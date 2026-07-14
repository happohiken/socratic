"""Implementación de DocumentRetriever usando txtai.

txtai es únicamente un índice de recuperación reconstruible.
SQLite es la fuente de verdad del sistema.
"""
from __future__ import annotations

import logging
import string
from pathlib import Path
from typing import Sequence

from txtai import Embeddings

from socratic.domain.models import ContentBlock
from socratic.retrieval.models import DocumentRetriever, RetrievedBlock

logger = logging.getLogger(__name__)


class TxtaiDocumentRetriever(DocumentRetriever):
    """Recuperación documental basada en txtai + sentence-transformers."""

    def __init__(self, storage_path: Path, embedding_model: str) -> None:
        self._storage_path = storage_path
        self._embedding_model = embedding_model
        self._embeddings: Embeddings | None = None

    @property
    def embeddings(self) -> Embeddings:
        if self._embeddings is None:
            config = {
                "path": self._embedding_model,
                "content": "sqlite",
                "id": "id",
            }
            self._embeddings = Embeddings(config)
        return self._embeddings

    def index_document(self, document_id: str, blocks: Sequence[ContentBlock]) -> None:
        """Indexa los bloques indexables de un documento.

        Usa upsert para que la indexación repetida sea segura:
        actualiza bloques existentes y añade nuevos sin duplicar.
        """
        indexable = [
            (
                block.id,
                {
                    "text": block.text,
                    "page_number": block.page_number,
                    "ordinal": block.ordinal,
                    "block_type": block.block_type,
                },
                document_id,
            )
            for block in blocks
            if self._is_indexable(block)
        ]
        if not indexable:
            logger.info("No indexable blocks for document %s", document_id)
            return

        try:
            self.embeddings.upsert(indexable)
            logger.info(
                "Indexed %d blocks for document %s", len(indexable), document_id
            )
        except Exception:
            logger.exception(
                "Failed to index document %s — document remains in SQLite",
                document_id,
            )

    def search(
        self,
        document_id: str,
        query: str,
        limit: int = 5,
    ) -> list[RetrievedBlock]:
        """Busca bloques relevantes filtrando por document_id en la consulta SQL.

        Usa una consulta SQL explícita para incluir page_number, ordinal
        y block_type en los resultados.
        """
        sql = (
            f"select id, text, page_number, ordinal, block_type, score "
            f"from txtai "
            f"where similar('{query}') "
            f"and tags='{document_id}' "
            f"limit {limit}"
        )
        results = self.embeddings.search(sql, limit=limit)
        return [
            RetrievedBlock(
                block_id=r["id"],
                document_id=document_id,
                text=r.get("text", ""),
                page_number=r.get("page_number", 0),
                ordinal=r.get("ordinal", 0),
                score=float(r["score"]),
            )
            for r in results
        ]

    def save(self) -> None:
        """Persiste el índice en disco."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self.embeddings.save(str(self._storage_path))

    def load(self) -> None:
        """Carga un índice persistido desde disco."""
        if not self._storage_path.exists():
            logger.info("No existing index at %s, will create on first index", self._storage_path)
            return
        try:
            if self._embeddings is None:
                self._embeddings = Embeddings()
            self._embeddings.load(str(self._storage_path))
            logger.info("Loaded index from %s", self._storage_path)
        except Exception:
            logger.exception(
                "Failed to load index from %s, will create new index",
                self._storage_path,
            )
            self._embeddings = None

    def count(self) -> int:
        """Devuelve el número total de entradas en el índice."""
        return self.embeddings.count()

    @staticmethod
    def _is_indexable(block: ContentBlock) -> bool:
        """Determinar si un bloque debe indexarse para recuperación.

        Solo se descartan bloques que realmente no contienen información útil:
        - texto vacío o solo espacios
        - texto compuesto únicamente por puntuación

        Se conservan todos los demás bloques, incluidos encabezados cortos
        como "Introducción", "Resultados", "Conclusiones", etc.
        """
        text = block.text.strip()
        if not text:
            return False
        if all(c in string.punctuation for c in text):
            return False
        return True
