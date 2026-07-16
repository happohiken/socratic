from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from socratic.api.studies import router as studies_router
from socratic.storage.database import DB, init_db
from socratic.domain.models import Document, ContentBlock
from socratic.storage.database import (
    save_document,
    save_content_blocks,
    get_document,
    get_study,
    list_studies,
    get_messages_for_study,
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
    from socratic.api.studies import get_db
    from socratic.services.navigation import NavigationService

    app = FastAPI()
    app.include_router(studies_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.navigation = NavigationService(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_document(db):
    doc = Document(filename="test.pdf", page_count=1, block_count=3)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(
            document_id=doc.id, ordinal=1, text="Primer bloque", page_number=1
        ),
        ContentBlock(
            document_id=doc.id, ordinal=2, text="Segundo bloque", page_number=1
        ),
        ContentBlock(
            document_id=doc.id, ordinal=3, text="Tercer bloque", page_number=1
        ),
    ]
    save_content_blocks(db.conn, doc.id, blocks)
    return doc


@pytest.mark.anyio
async def test_create_study(client, sample_document):
    resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == sample_document.id
    assert data["current_block_id"] is not None
    assert data["last_completed_block_id"] is None


@pytest.mark.anyio
async def test_create_study_document_not_found(client):
    resp = await client.post(
        "/studies",
        json={"document_id": "nonexistent-id"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_studies(client, sample_document):
    await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    resp = await client.get("/studies")
    assert resp.status_code == 200
    studies = resp.json()
    assert len(studies) == 1


@pytest.mark.anyio
async def test_get_study(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    resp = await client.get(f"/studies/{study_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == study_id
    assert data["document_id"] == sample_document.id


@pytest.mark.anyio
async def test_get_study_not_found(client):
    resp = await client.get("/studies/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_current_block(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    resp = await client.get(f"/studies/{study_id}/current-block")
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Primer bloque"
    assert data["ordinal"] == 1


@pytest.mark.anyio
async def test_complete_block_advances_position(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    # Marcar primer bloque como completado
    resp = await client.post(f"/studies/{study_id}/blocks/1/complete")
    # El bloque 1 no es un UUID, debería fallar. Usamos el UUID real.
    
    # Obtener el bloque actual para saber su UUID
    current_resp = await client.get(f"/studies/{study_id}/current-block")
    first_block_id = current_resp.json()["id"]
    
    resp = await client.post(f"/studies/{study_id}/blocks/{first_block_id}/complete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_completed_block_id"] == first_block_id
    assert data["current_block_id"] is not None  # debería avanzar al siguiente


@pytest.mark.anyio
async def test_complete_last_block_clears_current(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    # Obtener el último bloque
    current_resp = await client.get(f"/studies/{study_id}/current-block")
    # Avanzar hasta el último bloque marcando completados los anteriores
    for _ in range(2):  # hay 3 bloques, necesitamos avanzar 2 veces
        current_resp = await client.get(f"/studies/{study_id}/current-block")
        block_id = current_resp.json()["id"]
        await client.post(f"/studies/{study_id}/blocks/{block_id}/complete")

    # Ahora estamos en el tercer bloque
    current_resp = await client.get(f"/studies/{study_id}/current-block")
    last_block_id = current_resp.json()["id"]

    # Marcar último bloque como completado
    resp = await client.post(f"/studies/{study_id}/blocks/{last_block_id}/complete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_block_id"] is None  # no hay más bloques


@pytest.mark.anyio
async def test_create_message(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    resp = await client.post(
        f"/studies/{study_id}/messages",
        json={"content": "¿Qué es Socratic?", "role": "user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "¿Qué es Socratic?"
    assert data["role"] == "user"
    assert data["study_id"] == study_id


@pytest.mark.anyio
async def test_get_messages(client, sample_document):
    create_resp = await client.post(
        "/studies",
        json={"document_id": sample_document.id},
    )
    study_id = create_resp.json()["id"]

    await client.post(
        f"/studies/{study_id}/messages",
        json={"content": "Pregunta 1", "role": "user"},
    )
    await client.post(
        f"/studies/{study_id}/messages",
        json={"content": "Respuesta 1", "role": "assistant"},
    )

    resp = await client.get(f"/studies/{study_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
