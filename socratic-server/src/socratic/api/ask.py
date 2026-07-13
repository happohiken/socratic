from __future__ import annotations

from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from socratic.domain.models import ContentBlock, Message, Study
from socratic.llm.base import LLMClient
from socratic.storage.database import (
    DB,
    get_content_block,
    get_content_blocks,
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


DBDep = Annotated[DB, Depends(get_db)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]


class AskRequest(BaseModel):
    question: str = Field(..., description="Pregunta del usuario sobre el bloque actual")


class AskResponse(BaseModel):
    answer: str = Field(..., description="Respuesta del asistente")
    study_id: str
    message_id: str


@router.post("/{study_id}/ask", response_model=AskResponse, status_code=status.HTTP_201_CREATED)
def ask(
    study_id: str,
    body: AskRequest,
    db: DBDep,
    llm: LLMDep,
) -> Any:
    """Enviar una pregunta sobre el bloque actual de lectura.

    El servidor compone un contexto mínimo con: instrucciones del sistema,
    bloque actual, dos bloques anteriores y las dos conversaciones más
    recientes. Guarda la pregunta y la respuesta en el historial del estudio.
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

    all_blocks = get_content_blocks(db.conn, study.document_id)
    block_indices = {b.id: i for i, b in enumerate(all_blocks)}
    current_index = block_indices.get(current_block.id, 0)

    previous_blocks = []
    start = max(0, current_index - 2)
    for i in range(start, current_index):
        previous_blocks.append(all_blocks[i])

    messages = get_messages_for_study(db.conn, study_id)
    recent_messages = messages[-4:]

    context_messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Texto actual:\n\n{current_block.text}"},
        {"role": "assistant", "content": "He leído el bloque. ¿En qué puedo ayudarte?"},
    ]

    for block in previous_blocks:
        context_messages.append(
            {"role": "user", "content": f"Texto anterior:\n\n{block.text}"}
        )
        context_messages.append(
            {"role": "assistant", "content": "He leído ese bloque también."}
        )

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
