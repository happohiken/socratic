"""Endpoints de recuperación documental (diagnóstico y administración).

- POST /documents/{id}/reindex — indexa un documento para recuperación
- POST /documents/{id}/search — búsqueda de diagnóstico
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from socratic.retrieval import RetrievalService
from socratic.retrieval.models import RetrievedBlock
from socratic.storage.database import DB, get_document

router = APIRouter(prefix="/documents", tags=["retrieval"])


def get_db(request: Request) -> DB:
    return request.app.state.db


def get_retrieval(request: Request) -> RetrievalService:
    return request.app.state.retrieval


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class RetrievedBlockSummary(BaseModel):
    block_id: str
    page_number: int
    ordinal: int
    block_type: str
    score: float
    text: str

    @classmethod
    def from_retrieved(cls, rb: RetrievedBlock) -> "RetrievedBlockSummary":
        return cls(
            block_id=rb.block_id,
            page_number=rb.page_number,
            ordinal=rb.ordinal,
            block_type="",
            score=rb.score,
            text=rb.text,
        )


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document(
    document_id: str,
    db: DB = Depends(get_db),
    retrieval: RetrievalService = Depends(get_retrieval),
):
    """Indexar todos los bloques de un documento para recuperación."""
    doc = get_document(db.conn, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} no encontrado",
        )

    count = retrieval.reindex_document(document_id)
    return {"status": "indexed", "blocks": count}


@router.post("/{document_id}/search", response_model=list[RetrievedBlockSummary])
async def search_document(
    document_id: str,
    body: SearchRequest,
    db: DB = Depends(get_db),
    retrieval: RetrievalService = Depends(get_retrieval),
):
    """Buscar bloques relevantes en un documento indexado (diagnóstico)."""
    doc = get_document(db.conn, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} no encontrado",
        )

    results = retrieval.search(document_id, body.query, limit=body.limit)
    return [RetrievedBlockSummary.from_retrieved(r) for r in results]
