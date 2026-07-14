from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.requests import Request
from pydantic import BaseModel

from socratic.document_processing.adapter import (
    parsed_to_content_blocks,
    parsed_to_document,
)
from socratic.document_processing.extractor import parse_pdf
from socratic.domain.models import ContentBlock, Document
from socratic.storage.database import (
    DB,
    delete_document,
    get_content_block,
    get_content_blocks,
    get_document,
    init_db,
    list_documents,
    save_content_blocks,
    save_document,
    update_document,
)


def get_db(request: Request) -> DB:
    return request.app.state.db

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentSummary(BaseModel):
    id: str
    filename: str
    page_count: int
    block_count: int
    format: str
    created_at: str
    updated_at: str


class DocumentDetail(BaseModel):
    id: str
    filename: str
    page_count: int
    block_count: int
    format: str
    created_at: str
    updated_at: str
    blocks: list[dict[str, Any]] = []


class UploadResponse(BaseModel):
    document: DocumentSummary
    blocks: list[dict[str, Any]]


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_document(file: UploadFile, db: DB = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "El archivo debe ser un PDF")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        parsed = parse_pdf(tmp_path)

        doc = parsed_to_document(parsed, file.filename)
        save_document(db.conn, doc)

        blocks = parsed_to_content_blocks(doc.id, parsed)
        save_content_blocks(db.conn, doc.id, blocks)
    except Exception:
        db.conn.rollback()
        raise
    else:
        db.conn.commit()
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        document=DocumentSummary(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            block_count=doc.block_count,
            format=doc.format,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
        ),
        blocks=[
            {
                "id": b.id,
                "ordinal": b.ordinal,
                "text": b.text,
                "page_number": b.page_number,
                "block_type": b.block_type,
            }
            for b in blocks
        ],
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document_endpoint(document_id: str, db: DB = Depends(get_db)):
    doc = get_document(db.conn, document_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    deleted = delete_document(db.conn, document_id)
    if not deleted:
        raise HTTPException(500, "Error al eliminar el documento")

    return None


@router.get("", response_model=list[DocumentSummary])
async def list_docs(db: DB = Depends(get_db)):
    docs = list_documents(db.conn)
    return [
        DocumentSummary(
            id=d.id,
            filename=d.filename,
            page_count=d.page_count,
            block_count=d.block_count,
            format=d.format,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document_detail(document_id: str, db: DB = Depends(get_db)):
    doc = get_document(db.conn, document_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    blocks = get_content_blocks(db.conn, doc.id)
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        block_count=doc.block_count,
        format=doc.format,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
        blocks=[
            {
                "id": b.id,
                "ordinal": b.ordinal,
                "text": b.text,
                "page_number": b.page_number,
                "block_type": b.block_type,
            }
            for b in blocks
        ],
    )
