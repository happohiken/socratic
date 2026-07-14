"""Hito 3 — Reinicio y recuperacion persistente.

Verifica que cerrar y reabrir el servidor sobre la misma base de datos conserva
documento, bloques, estudio (bloque actual y ultimo completado) e historial
de mensajes. Se simula el reinicio creando dos apps FastAPI independientes que
apuntan al mismo archivo SQLite.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from socratic.app import create_app


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    from fpdf import FPDF

    pdf_path = tmp_path / "sample.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, "Titulo del documento de prueba.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 30, "Primer parrafo de contenido con texto largo para evitar fusion.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 30, "Segundo parrafo con mas texto para probar la extraccion.", new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 30, "Tercer parrafo en la segunda pagina.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 30, "Cuarto parrafo que cierra el documento de prueba.", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(pdf_path))
    return pdf_path


async def _upload_and_progress(db_path: Path, pdf_path: Path) -> dict:
    """Primera 'sesion' del servidor: carga PDF, crea estudio, avanza y pregunta."""
    app = create_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(pdf_path, "rb") as f:
            resp = await client.post(
                "/documents",
                files={"file": ("sample.pdf", f, "application/pdf")},
            )
        assert resp.status_code == 201
        document_id = resp.json()["document"]["id"]
        block_count = resp.json()["document"]["block_count"]
        assert block_count >= 3

        resp = await client.post("/studies", json={"document_id": document_id})
        assert resp.status_code == 201
        study_id = resp.json()["id"]
        first_block_id = resp.json()["current_block_id"]

        resp = await client.post(
            f"/studies/{study_id}/messages",
            json={"content": "De que trata el titulo?", "role": "user"},
        )
        assert resp.status_code == 201

        resp = await client.post(
            f"/studies/{study_id}/messages",
            json={"content": "Trata de una prueba.", "role": "assistant"},
        )
        assert resp.status_code == 201

        resp = await client.post(
            f"/studies/{study_id}/blocks/{first_block_id}/complete"
        )
        assert resp.status_code == 200
        second_block_id = resp.json()["current_block_id"]

        return {
            "document_id": document_id,
            "study_id": study_id,
            "first_block_id": first_block_id,
            "second_block_id": second_block_id,
            "block_count": block_count,
        }


async def _verify_after_restart(db_path: Path, ids: dict) -> None:
    """Segunda 'sesion' del servidor: verifica que todo se conservo."""
    app = create_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["id"] == ids["document_id"]
        assert docs[0]["block_count"] == ids["block_count"]

        resp = await client.get(f"/documents/{ids['document_id']}")
        assert resp.status_code == 200
        assert len(resp.json()["blocks"]) == ids["block_count"]

        resp = await client.get("/studies")
        assert resp.status_code == 200
        studies = resp.json()
        assert len(studies) == 1
        assert studies[0]["id"] == ids["study_id"]

        resp = await client.get(f"/studies/{ids['study_id']}")
        assert resp.status_code == 200
        study = resp.json()
        assert study["last_completed_block_id"] == ids["first_block_id"]
        assert study["current_block_id"] == ids["second_block_id"]

        resp = await client.get(f"/studies/{ids['study_id']}/current-block")
        assert resp.status_code == 200
        assert resp.json()["id"] == ids["second_block_id"]

        resp = await client.get(f"/studies/{ids['study_id']}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[0]["content"] == "De que trata el titulo?"


@pytest.mark.anyio
async def test_state_survives_server_restart(tmp_path: Path, sample_pdf: Path):
    db_path = tmp_path / "socratic.db"

    ids = await _upload_and_progress(db_path, sample_pdf)
    await _verify_after_restart(db_path, ids)


@pytest.mark.anyio
async def test_completed_blocks_survive_multiple_restarts(
    tmp_path: Path, sample_pdf: Path
):
    """Avanza un bloque por sesion y reinicia dos veces: el progreso acumulado se conserva."""
    db_path = tmp_path / "socratic.db"

    app = create_app(db_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with open(sample_pdf, "rb") as f:
            resp = await client.post(
                "/documents",
                files={"file": ("sample.pdf", f, "application/pdf")},
            )
        document_id = resp.json()["document"]["id"]
        resp = await client.post("/studies", json={"document_id": document_id})
        study_id = resp.json()["id"]

    # Sesion 2: completar primer bloque
    app = create_app(db_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/studies/{study_id}/current-block")
        first_block_id = resp.json()["id"]
        resp = await client.post(
            f"/studies/{study_id}/blocks/{first_block_id}/complete"
        )
        second_block_id = resp.json()["current_block_id"]

    # Sesion 3: verificar y completar segundo bloque
    app = create_app(db_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/studies/{study_id}")
        assert resp.json()["last_completed_block_id"] == first_block_id
        assert resp.json()["current_block_id"] == second_block_id

        resp = await client.post(
            f"/studies/{study_id}/blocks/{second_block_id}/complete"
        )
        assert resp.status_code == 200
        third_block_id = resp.json()["current_block_id"]

    # Sesion 4: verificar progreso acumulado
    app = create_app(db_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/studies/{study_id}")
        assert resp.json()["last_completed_block_id"] == second_block_id
        assert resp.json()["current_block_id"] == third_block_id
