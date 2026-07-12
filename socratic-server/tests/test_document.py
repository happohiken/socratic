from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from socratic.api.documents import router as documents_router
from socratic.storage.database import DB, init_db
from socratic.domain.models import Document, ContentBlock
from socratic.storage.database import (
    save_document,
    save_content_blocks,
    get_document,
    list_documents,
    get_content_blocks,
)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
async def client(db):
    from fastapi import FastAPI
    from socratic.api.documents import get_db

    app = FastAPI()
    app.include_router(documents_router)
    app.dependency_overrides[get_db] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_pdf(tmp_path):
    """Crea un PDF mínimo de prueba."""
    from fpdf import FPDF

    pdf_path = tmp_path / "sample.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, "Título del documento de prueba", ln=True)
    pdf.cell(200, 10, "Primer párrafo de contenido.", ln=True)
    pdf.cell(200, 10, "Segundo párrafo con más texto para probar la extracción.")
    pdf.add_page()
    pdf.cell(200, 10, "Tercer párrafo en la segunda página.", ln=True)
    pdf.cell(
        200,
        10,
        "Cuarto párrafo que cierra el documento de prueba.",
        ln=True,
    )
    pdf.output(str(pdf_path))
    return pdf_path


@pytest.mark.anyio
async def test_upload_document(client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["document"]["filename"] == "sample.pdf"
    assert data["document"]["block_count"] > 0
    assert len(data["blocks"]) == data["document"]["block_count"]


@pytest.mark.anyio
async def test_list_documents(client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    doc_id = resp.json()["document"]["id"]

    resp = await client.get("/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id


@pytest.mark.anyio
async def test_get_document_detail(client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    doc_id = resp.json()["document"]["id"]

    resp = await client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == doc_id
    assert len(data["blocks"]) > 0
    assert data["blocks"][0]["text"]  # primer bloque tiene texto


@pytest.mark.anyio
async def test_get_document_not_found(client):
    resp = await client.get("/documents/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_upload_non_pdf(client):
    resp = await client.post(
        "/documents",
        files={"file": ("test.txt", b"contenido", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_upload_empty_filename(client):
    resp = await client.post(
        "/documents",
        files={"file": ("", b"contenido", "application/octet-stream")},
    )
    assert resp.status_code in (400, 422)


def test_save_and_retrieve_document(db):
    doc = Document(filename="test.pdf", page_count=10, block_count=0)
    save_document(db.conn, doc)

    retrieved = get_document(db.conn, doc.id)
    assert retrieved is not None
    assert retrieved.filename == "test.pdf"
    assert retrieved.page_count == 10


def test_save_and_retrieve_blocks(db):
    doc = Document(filename="test.pdf", page_count=1)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(
            document_id=doc.id, ordinal=1, text="Bloque uno", page_number=1
        ),
        ContentBlock(
            document_id=doc.id, ordinal=2, text="Bloque dos", page_number=1
        ),
    ]
    save_content_blocks(db.conn, doc.id, blocks)

    retrieved = get_content_blocks(db.conn, doc.id)
    assert len(retrieved) == 2
    assert retrieved[0].text == "Bloque uno"
    assert retrieved[1].text == "Bloque dos"


def test_list_documents(db):
    doc1 = Document(filename="doc1.pdf", page_count=1)
    doc2 = Document(filename="doc2.pdf", page_count=2)
    save_document(db.conn, doc1)
    save_document(db.conn, doc2)

    docs = list_documents(db.conn)
    assert len(docs) == 2
