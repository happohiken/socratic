"""Endpoint de preguntas sobre el bloque actual de lectura.

Construye un contexto ampliado con:
1. System prompt
2. Bloque actual
3. Dos bloques anteriores
4. Dos bloques siguientes
5. Fragmentos relevantes recuperados (txtai)
6. Historial reciente
7. Pregunta del usuario
"""
from __future__ import annotations

from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from socratic.domain.models import ContentBlock, Message, Study
from socratic.llm.base import LLMClient
from socratic.retrieval import RetrievalService
from socratic.storage.database import (
    DB,
    get_content_block,
    get_messages_for_study,
    get_study,
    save_message,
)

router = APIRouter(prefix="/studies", tags=["ask"])

SYSTEM_PROMPT = (
    "Eres un profesor particular que guía al estudiante en la lectura "
    "secuencial de un documento. El estudiante lee bloques de texto uno "
    "a uno y puede hacer preguntas sobre el bloque actual. Responde de "
    "forma concisa y relacionada con el contenido del documento. "
    "No divagues; mantén el foco en el texto que el estudiante está leyendo."
)


def get_db(request: Request) -> DB:
    return request.app.state.db


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


def get_retrieval(request: Request) -> RetrievalService:
    return request.app.state.retrieval


DBDep = Annotated[DB, Depends(get_db)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
RetrievalDep = Annotated[RetrievalService, Depends(get_retrieval)]


class AskRequest(BaseModel):
    question: str = Field(..., description="Pregunta del usuario sobre el bloque actual")


class AskResponse(BaseModel):
    answer: str = Field(..., description="Respuesta del asistente")
    study_id: str
    message_id: str


def _build_prompt(
    context_messages: list[dict[str, str]],
    retrieved_blocks: list[ContentBlock],
    limit_chars: int = 2000,
) -> list[dict[str, str]]:
    """Añade bloques recuperados al contexto con límite de tamaño."""
    if not retrieved_blocks:
        return context_messages

    sections: list[str] = []
    total = 0
    for i, block in enumerate(retrieved_blocks, 1):
        page_info = f"p.{block.page_number}" if block.page_number else ""
        ordinal_info = f"ordinal {block.ordinal}" if block.ordinal else ""
        header_parts = [p for p in [page_info, ordinal_info] if p]
        header = ", ".join(header_parts) if header_parts else str(i)
        section = f"[{header}]\n{block.text}"
        if total + len(section) > limit_chars:
            break
        sections.append(section)
        total += len(section)

    if sections:
        context_messages.append({
            "role": "user",
            "content": "\n\n".join(sections),
        })
        context_messages.append({
            "role": "assistant",
            "content": "He revisado estos fragmentos adicionales del documento.",
        })

    return context_messages


@router.post("/{study_id}/ask", response_model=AskResponse, status_code=status.HTTP_201_CREATED)
def ask(
    study_id: str,
    body: AskRequest,
    db: DBDep,
    llm: LLMDep,
    retrieval: RetrievalDep,
) -> Any:
    """Enviar una pregunta sobre el bloque actual de lectura.

    El servidor compone un contexto ampliado con: instrucciones del sistema,
    bloque actual, bloques anteriores y siguientes, fragmentos relevantes
    recuperados mediante txtai, historial reciente y la pregunta.
    El bloque actual no cambia tras la respuesta.
    """
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )

    if not study.current_block_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estudio no tiene bloque actual",
        )

    current_block = get_content_block(db.conn, study.current_block_id)
    if not current_block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bloque {study.current_block_id} no encontrado",
        )

    # Construir contexto combinado (local + recuperado)
    context = retrieval.retrieve_context(study, current_block, body.question)

    # Construir mensajes para el LLM
    context_messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Texto actual:\n\n{current_block.text}"},
        {"role": "assistant", "content": "He leído el bloque. ¿En qué puedo ayudarte?"},
    ]

    # Bloques anteriores (excluyendo el actual)
    local_prev = [b for b in context.local_blocks if b.id != current_block.id
                  and b.ordinal < current_block.ordinal]
    for block in local_prev:
        context_messages.append(
            {"role": "user", "content": f"Texto anterior:\n\n{block.text}"}
        )
        context_messages.append(
            {"role": "assistant", "content": "He leído ese bloque también."}
        )

    # Bloques siguientes (excluyendo el actual)
    local_next = [b for b in context.local_blocks if b.id != current_block.id
                  and b.ordinal > current_block.ordinal]
    for block in local_next:
        context_messages.append(
            {"role": "user", "content": f"Texto siguiente:\n\n{block.text}"}
        )
        context_messages.append(
            {"role": "assistant", "content": "He leído ese bloque también."}
        )

    # Bloques recuperados (txtai)
    retrieved_as_blocks = [
        ContentBlock(
            id=rb.block_id,
            document_id=rb.document_id,
            ordinal=rb.ordinal,
            text=rb.text,
            page_number=rb.page_number,
        )
        for rb in context.retrieved_blocks
    ]
    context_messages = _build_prompt(context_messages, retrieved_as_blocks)

    # Historial reciente
    messages = get_messages_for_study(db.conn, study_id)
    recent_messages = messages[-4:]
    for m in recent_messages:
        context_messages.append({"role": m.role, "content": m.content})

    context_messages.append({"role": "user", "content": body.question})

    answer = llm.complete(context_messages)

    user_message = Message(
        study_id=study_id,
        content_block_id=current_block.id,
        role="user",
        content=body.question,
    )
    save_message(db.conn, user_message)

    assistant_message = Message(
        study_id=study_id,
        content_block_id=current_block.id,
        role="assistant",
        content=answer,
    )
    save_message(db.conn, assistant_message)
    db.conn.commit()

    return AskResponse(
        answer=answer,
        study_id=study_id,
        message_id=assistant_message.id,
    )
