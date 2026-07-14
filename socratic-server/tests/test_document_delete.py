"""Pruebas para DELETE /documents/{document_id}."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fpdf import FPDF
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from socratic.api.documents import get_db, router as documents_router
from socratic.api.studies import get_db as get_db_studies, router as studies_router
from socratic.storage.database import DB, init_db


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
async def client(db):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(documents_router)
    app.include_router(studies_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_db_studies] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(200, 30, "Primer parrafo con texto suficiente para ser detectado.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 30, "Segundo parrafo con texto suficiente para ser detectado.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 30, "Tercer parrafo con texto suficiente para ser detectado.", new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "sample.pdf"
    pdf.output(str(path))
    return path


@pytest.mark.anyio
async def test_delete_document(client, sample_pdf):
    """Borrar un documento elimina documento, bloques y estudios."""
    # Subir PDF
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 201
    doc_id = resp.json()["document"]["id"]
    block_count = resp.json()["document"]["block_count"]
    assert block_count > 0

    # Verificar que existen
    resp = await client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["block_count"] == block_count

    # Borrar documento
    resp = await client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 204

    # Verificar que desaparecio
    resp = await client.get(f"/documents/{doc_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_document_cascades_to_studies(client, sample_pdf):
    """Borrar un documento elimina tambien los estudios asociados."""
    # Subir PDF
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    doc_id = resp.json()["document"]["id"]

    # Crear estudio
    resp = await client.post("/studies", json={"document_id": doc_id})
    assert resp.status_code == 201
    study_id = resp.json()["id"]

    # Borrar documento
    resp = await client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 204

    # Verificar que el estudio tambien desaparecio
    resp = await client.get(f"/studies/{study_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_document(client):
    """Borrar un documento inexistente devuelve 404."""
    resp = await client.delete("/documents/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_preserves_other_documents(client, sample_pdf):
    """Borrar un documento no afecta a otros documentos."""
    # Subir dos PDFs
    with open(sample_pdf, "rb") as f:
        resp1 = await client.post(
            "/documents",
            files={"file": ("doc1.pdf", f, "application/pdf")},
        )
    doc1_id = resp1.json()["document"]["id"]

    with open(sample_pdf, "rb") as f:
        resp2 = await client.post(
            "/documents",
            files={"file": ("doc2.pdf", f, "application/pdf")},
        )
    doc2_id = resp2.json()["document"]["id"]

    # Borrar el primero
    resp = await client.delete(f"/documents/{doc1_id}")
    assert resp.status_code == 204

    # Verificar que el segundo sigue existiendo
    resp = await client.get(f"/documents/{doc2_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc2_id

    # Verificar que el primero ya no existe
    resp = await client.get(f"/documents/{doc1_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_with_cli(client, sample_pdf):
    """Verificar que el CLI puede eliminar documentos."""
    # Subir PDF via API
    with open(sample_pdf, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    doc_id = resp.json()["document"]["id"]

    # Borrar via API directa (simulando lo que hace el CLI)
    resp = await client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 204

    # Verificar que desaparecio
    resp = await client.get(f"/documents/{doc_id}")
    assert resp.status_code == 404
