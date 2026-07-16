"""Implementaciones de las tools del orquestador.

Dos categorías semánticas que comparten el mismo mecanismo técnico:

- **Tools de dominio**: consultan o modifican el estado del estudio.
  Delegan en ``NavigationService``; no tocan la persistencia.
- **Tools de recuperación**: devuelven información sin modificar el
  estado. ``retrieve_document_context`` delega en ``RetrievalService``
  tal cual, sin construir narrativa ni llamar al LLM.

Todas las tools reciben un ``TurnContext`` inyectado por el orquestador
(no visible para el LLM) y devuelven **datos estructurados**. El LLM
compone la respuesta final a partir de esos datos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from socratic.domain.models import ContentBlock, Study
from socratic.orchestrator.registry import register_tool
from socratic.retrieval import RetrievalService
from socratic.services.navigation import NavigationError, NavigationService

if TYPE_CHECKING:
    # Solo para anotación de tipos; las tools no acceden a la persistencia
    # directamente (delegan en NavigationService / RetrievalService).
    from socratic.storage.database import DB


@dataclass
class TurnContext:
    """Estado de ejecución de un Turn, inyectado en cada tool.

    Es mutable: las tools de dominio que avanzan la posición actualizan
    ``study`` y ``current_block`` para que las siguientes tools del mismo
    Turn vean el estado actualizado.
    """

    study: Study
    current_block: ContentBlock | None
    db: DB
    retrieval: RetrievalService
    navigation: NavigationService


def _block_to_dict(block: ContentBlock | None) -> dict[str, Any] | None:
    """Serializa un ``ContentBlock`` a datos estructurados."""
    if block is None:
        return None
    return {
        "id": block.id,
        "document_id": block.document_id,
        "ordinal": block.ordinal,
        "text": block.text,
        "page_number": block.page_number,
        "block_type": block.block_type,
    }


@register_tool(
    name="get_current_block",
    description=(
        "Devuelve el bloque de lectura actual (texto, página, ordinal, tipo). "
        "No modifica el estado. Útil para repetir el bloque o referenciarlo."
    ),
)
def get_current_block(context: TurnContext) -> dict[str, Any] | None:
    """Devuelve el bloque actual del estudio."""
    return _block_to_dict(context.current_block)


@register_tool(
    name="complete_current_block",
    description=(
        "Marca el bloque actual como completado y avanza al siguiente. "
        "Devuelve el nuevo bloque actual, o null si se alcanzó el final "
        "del documento. Útil cuando el usuario pide continuar."
    ),
)
def complete_current_block(context: TurnContext) -> dict[str, Any] | None:
    """Completa el bloque actual y devuelve el nuevo bloque actual."""
    try:
        new_block = context.navigation.complete_current_block(context.study)
    except NavigationError as exc:
        return {"error": str(exc)}
    context.current_block = new_block
    return _block_to_dict(new_block)


@register_tool(
    name="previous_block",
    description=(
        "Retrocede al bloque anterior y lo devuelve como nuevo bloque "
        "actual. Devuelve error si ya se está en el primer bloque. "
        "Útil cuando el usuario pide volver atrás."
    ),
)
def previous_block(context: TurnContext) -> dict[str, Any]:
    """Retrocede un bloque y lo devuelve como nuevo bloque actual."""
    try:
        new_block = context.navigation.previous_block(context.study)
    except NavigationError as exc:
        return {"error": str(exc)}
    context.current_block = new_block
    return _block_to_dict(new_block) or {"error": "No hay bloque actual"}


@register_tool(
    name="retrieve_document_context",
    description=(
        "Recupera fragmentos del documento relevantes para una consulta. "
        "Úsalo solo cuando la pregunta requiera contexto más allá del "
        "bloque actual. No modifica el estado. No lo uses para navegar "
        "(continuar, repetir, retroceder)."
    ),
)
def retrieve_document_context(
    context: TurnContext,
    query: str,
) -> list[dict[str, Any]]:
    """Recupera fragmentos documentales relevantes para la consulta.

    Reutiliza ``RetrievalService.retrieve_context`` tal cual: combina
    bloques locales (actual + 2 anteriores + 2 siguientes) con bloques
    recuperados por similitud vectorial, deduplicados por ``block_id``.
    """
    if context.current_block is None:
        return []
    result = context.retrieval.retrieve_context(
        context.study,
        context.current_block,
        query,
    )
    return [
        {
            "block_id": rb.block_id,
            "document_id": rb.document_id,
            "ordinal": rb.ordinal,
            "page_number": rb.page_number,
            "text": rb.text,
            "score": rb.score,
        }
        for rb in result.retrieved_blocks
    ]
