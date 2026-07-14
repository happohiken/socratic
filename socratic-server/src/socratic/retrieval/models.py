"""Modelos de datos para la recuperación documental.

RetrievedBlock representa un bloque recuperado por el motor de búsqueda.
DocumentRetriever es la abstracción mínima para cualquier motor de recuperación.
Context combina bloques locales y recuperados para la construcción del prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RetrievedBlock:
    """Bloque recuperado por el motor de búsqueda vectorial."""
    block_id: str
    document_id: str
    text: str
    page_number: int
    ordinal: int
    score: float


class DocumentRetriever(Protocol):
    """Abstracción mínima para un motor de recuperación documental.

    txtai es el motor actual. Esta abstracción permite cambiarlo
    en el futuro sin modificar el endpoint de preguntas.
    """

    def index_document(
        self,
        document_id: str,
        blocks: Sequence["ContentBlock"],
    ) -> None:
        """Indexa los bloques de un documento."""

    def search(
        self,
        document_id: str,
        query: str,
        limit: int = 5,
    ) -> list[RetrievedBlock]:
        """Recupera los bloques más relevantes de un documento."""


@dataclass(frozen=True)
class Context:
    """Contexto combinado para la construcción del prompt."""
    local_blocks: list["ContentBlock"]
    retrieved_blocks: list[RetrievedBlock]
