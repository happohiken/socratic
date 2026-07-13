from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from socratic.api.ask import get_db, router as ask_router
from socratic.domain.models import ContentBlock, Document, Study
from socratic.llm.base import LLMClient
from socratic.storage.database import (
    init_db,
    get_messages_for_study,
    save_content_blocks,
    save_document,
    save_study,
)
from tests.test_llm import StubLLM


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
def llm_client():
    return StubLLM(response="Esta es la respuesta del LLM")


@pytest.fixture
def sample_study(db):
    doc = Document(filename="test.pdf", page_count=1, block_count=5)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(document_id=doc.id, ordinal=1, text="Bloque uno", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=2, text="Bloque dos", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=3, text="Bloque tres", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=4, text="Bloque cuatro", page_number=2),
        ContentBlock(document_id=doc.id, ordinal=5, text="Bloque cinco", page_number=2),
    ]
    save_content_blocks(db.conn, doc.id, blocks)

    study = Study(
        document_id=doc.id,
        current_block_id=blocks[2].id,
        last_completed_block_id=blocks[1].id,
    )
    save_study(db.conn, study)
    db.conn.commit()

    return study, blocks


@pytest.mark.anyio
async def test_ask_stores_messages_in_db(db, llm_client):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(ask_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.llm = llm_client

    doc = Document(filename="test.pdf", page_count=1, block_count=3)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(document_id=doc.id, ordinal=1, text="Texto A", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=2, text="Texto B", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=3, text="Texto C", page_number=1),
    ]
    save_content_blocks(db.conn, doc.id, blocks)

    study = Study(
        document_id=doc.id,
        current_block_id=blocks[1].id,
        last_completed_block_id=blocks[0].id,
    )
    save_study(db.conn, study)
    db.conn.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/ask",
            json={"question": "¿Qué significa X?"},
        )
        assert resp.status_code == 201

    messages = get_messages_for_study(db.conn, study.id)
    assert len(messages) == 2

    user_msg = messages[0]
    assert user_msg.role == "user"
    assert user_msg.content == "¿Qué significa X?"
    assert user_msg.content_block_id == blocks[1].id

    assistant_msg = messages[1]
    assert assistant_msg.role == "assistant"
    assert assistant_msg.content == "Esta es la respuesta del LLM"
    assert assistant_msg.content_block_id == blocks[1].id


@pytest.mark.anyio
async def test_ask_context_includes_current_block(db, llm_client):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(ask_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.llm = llm_client

    doc = Document(filename="test.pdf", page_count=1, block_count=3)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(document_id=doc.id, ordinal=1, text="Texto A", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=2, text="Texto B", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=3, text="Texto C", page_number=1),
    ]
    save_content_blocks(db.conn, doc.id, blocks)

    study = Study(
        document_id=doc.id,
        current_block_id=blocks[2].id,
        last_completed_block_id=blocks[1].id,
    )
    save_study(db.conn, study)
    db.conn.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/ask",
            json={"question": "¿De qué trata este bloque?"},
        )
        assert resp.status_code == 201

    messages = llm_client.calls[0]
    current_text = blocks[2].text
    assert any(current_text in m.get("content", "") for m in messages)
    assert messages[-1]["role"] == "user"
    assert "¿De qué trata este bloque?" in messages[-1]["content"]


@pytest.mark.anyio
async def test_ask_context_includes_previous_blocks(db, llm_client):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(ask_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.llm = llm_client

    doc = Document(filename="test.pdf", page_count=1, block_count=3)
    save_document(db.conn, doc)

    blocks = [
        ContentBlock(document_id=doc.id, ordinal=1, text="Primer texto", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=2, text="Segundo texto", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=3, text="Tercer texto", page_number=1),
    ]
    save_content_blocks(db.conn, doc.id, blocks)

    study = Study(
        document_id=doc.id,
        current_block_id=blocks[2].id,
        last_completed_block_id=blocks[1].id,
    )
    save_study(db.conn, study)
    db.conn.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post(
            f"/studies/{study.id}/ask",
            json={"question": "¿Qué dice el texto?"},
        )

    messages = llm_client.calls[0]
    previous_texts = [blocks[0].text, blocks[1].text]
    found = sum(
        1 for t in previous_texts if any(t in m.get("content", "") for m in messages)
    )
    assert found >= 1


@pytest.mark.anyio
async def test_ask_study_not_found(db, llm_client):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(ask_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.llm = llm_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/studies/nonexistent/ask",
            json={"question": "¿Qué pasa?"},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_ask_no_current_block(db, llm_client):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(ask_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.llm = llm_client

    doc = Document(filename="test.pdf", page_count=1, block_count=1)
    save_document(db.conn, doc)

    study = Study(
        document_id=doc.id,
        current_block_id=None,
        last_completed_block_id=None,
    )
    save_study(db.conn, study)
    db.conn.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/ask",
            json={"question": "¿Qué pasa?"},
        )
        assert resp.status_code == 400
