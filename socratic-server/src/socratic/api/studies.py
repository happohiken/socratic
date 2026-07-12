from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from socratic.domain.models import ContentBlock, Document, Message, Study
from socratic.storage.database import (
    DB,
    get_content_block,
    get_document,
    get_messages_for_study,
    get_study,
    list_studies,
    save_message,
    save_study,
    update_study,
)

router = APIRouter(prefix="/studies", tags=["studies"])


def get_db(request: Request) -> DB:
    return request.app.state.db


DBDep = Annotated[DB, Depends(get_db)]


class StudyCreate(BaseModel):
    document_id: str = Field(..., description="ID del documento para crear el estudio")


class StudyResponse(BaseModel):
    id: str
    document_id: str
    current_block_id: Optional[str] = None
    last_completed_block_id: Optional[str] = None
    created_at: str
    updated_at: str


class BlockResponse(BaseModel):
    id: str
    document_id: str
    ordinal: int
    text: str
    page_number: int
    block_type: str


class MessageResponse(BaseModel):
    id: str
    study_id: str
    content_block_id: Optional[str] = None
    role: str
    content: str
    created_at: str


class MessageCreate(BaseModel):
    content: str
    role: str = "user"
    content_block_id: Optional[str] = None


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
def create_study(body: StudyCreate, db: DBDep) -> StudyResponse:
    """Crear un estudio para un documento.

    El estudio inicializa la posición de lectura en el primer bloque del documento.
    """
    doc = get_document(db.conn, body.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {body.document_id} no encontrado",
        )

    from socratic.storage.database import get_content_blocks

    content_blocks = get_content_blocks(db.conn, body.document_id)
    if not content_blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento no tiene bloques extraídos",
        )

    study = Study(
        document_id=body.document_id,
        current_block_id=content_blocks[0].id,
        last_completed_block_id=None,
    )
    save_study(db.conn, study)
    db.conn.commit()

    return StudyResponse(
        id=study.id,
        document_id=study.document_id,
        current_block_id=study.current_block_id,
        last_completed_block_id=study.last_completed_block_id,
        created_at=study.created_at.isoformat(),
        updated_at=study.updated_at.isoformat(),
    )


@router.get("", response_model=List[StudyResponse])
def list_studies_endpoint(db: DBDep) -> List[Study]:
    """Listar todos los estudios."""
    studies = list_studies(db.conn)
    return [
        StudyResponse(
            id=s.id,
            document_id=s.document_id,
            current_block_id=s.current_block_id,
            last_completed_block_id=s.last_completed_block_id,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in studies
    ]


@router.get("/{study_id}", response_model=StudyResponse)
def get_study_endpoint(study_id: str, db: DBDep) -> Study:
    """Consultar el estado de un estudio."""
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )
    return StudyResponse(
        id=study.id,
        document_id=study.document_id,
        current_block_id=study.current_block_id,
        last_completed_block_id=study.last_completed_block_id,
        created_at=study.created_at.isoformat(),
        updated_at=study.updated_at.isoformat(),
    )


@router.get("/{study_id}/current-block", response_model=BlockResponse)
def get_current_block(study_id: str, db: DBDep) -> ContentBlock:
    """Obtener el bloque actual de lectura.

    No avanza la posición. Permite repetir el bloque si es necesario.
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
    block = get_content_block(db.conn, study.current_block_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bloque {study.current_block_id} no encontrado",
        )
    return BlockResponse(
        id=block.id,
        document_id=block.document_id,
        ordinal=block.ordinal,
        text=block.text,
        page_number=block.page_number,
        block_type=block.block_type,
    )


@router.post(
    "/{study_id}/blocks/{block_id}/complete",
    response_model=StudyResponse,
)
def complete_block(
    study_id: str,
    block_id: str,
    db: DBDep,
) -> Study:
    """Marcar un bloque como completado.

    Avanza la posición al siguiente bloque del documento.
    """
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )

    doc = get_document(db.conn, study.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {study.document_id} no encontrado",
        )

    from socratic.storage.database import get_content_blocks

    blocks = get_content_blocks(db.conn, study.document_id)
    block_ids = [b.id for b in blocks]

    if block_id not in block_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bloque {block_id} no pertenece al documento",
        )

    current_index = block_ids.index(block_id)
    if current_index < len(block_ids) - 1:
        next_block_id = block_ids[current_index + 1]
        study.current_block_id = next_block_id
    else:
        study.current_block_id = None

    study.last_completed_block_id = block_id
    study.touch()
    update_study(db.conn, study)
    db.conn.commit()

    return StudyResponse(
        id=study.id,
        document_id=study.document_id,
        current_block_id=study.current_block_id,
        last_completed_block_id=study.last_completed_block_id,
        created_at=study.created_at.isoformat(),
        updated_at=study.updated_at.isoformat(),
    )


@router.get("/{study_id}/messages", response_model=List[MessageResponse])
def get_messages(study_id: str, db: DBDep) -> List[Message]:
    """Obtener el historial de mensajes de un estudio."""
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )
    messages = get_messages_for_study(db.conn, study_id)
    return [
        MessageResponse(
            id=m.id,
            study_id=m.study_id,
            content_block_id=m.content_block_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/{study_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    db: DBDep,
    study_id: str,
    body: MessageCreate,
) -> Message:
    """Crear un mensaje en el estudio.

    Se usa para guardar preguntas del usuario y respuestas del asistente.
    """
    study = get_study(db.conn, study_id)
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estudio {study_id} no encontrado",
        )

    message = Message(
        study_id=study_id,
        content_block_id=body.content_block_id,
        role=body.role,
        content=body.content,
    )
    save_message(db.conn, message)
    db.conn.commit()

    return MessageResponse(
        id=message.id,
        study_id=message.study_id,
        content_block_id=message.content_block_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
    )
