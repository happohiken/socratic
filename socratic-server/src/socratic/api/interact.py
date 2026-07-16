"""Endpoint conversacional `/interact`.

Traduce HTTP ↔ orquestador. El orquestador es independiente del protocolo;
toda la lógica de transporte, validación HTTP y serialización vive aquí.

Decisión (ver `docs/conversational-orchestrator-plan.md` sección 6,
alternativa A): se mantiene `/ask` para compatibilidad con la CLI textual
y se añade `/interact` para el flujo conversacional con tools.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from socratic.orchestrator import Orchestrator
from socratic.storage.database import DB, get_study

router = APIRouter(prefix="/studies", tags=["interact"])


def get_db(request: Request) -> DB:
    return request.app.state.db


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


DBDep = Annotated[DB, Depends(get_db)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]


class InteractRequest(BaseModel):
    input: str = Field(..., description="Intervención del usuario en lenguaje natural")


class InteractResponse(BaseModel):
    answer: str = Field(..., description="Respuesta final del asistente")
    study_id: str
    message_id: str


@router.post(
    "/{study_id}/interact",
    response_model=InteractResponse,
    status_code=status.HTTP_201_CREATED,
)
def interact(
    study_id: str,
    body: InteractRequest,
    db: DBDep,
    orchestrator: OrchestratorDep,
) -> Any:
    """Iniciar un Turn conversacional.

    El orquestador decide qué tools invocar para satisfacer la intención
    del usuario (continuar, repetir, retroceder, preguntar) y compone la
    respuesta final. Solo se persisten los mensajes user/assistant.
    """
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )

    result = orchestrator.interact(study, body.input)
    return InteractResponse(
        answer=result.answer,
        study_id=result.study_id,
        message_id=result.message_id,
    )
