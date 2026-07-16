"""Tests del endpoint POST /studies/{id}/interact."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from socratic.api.interact import get_db, router as interact_router
from socratic.domain.models import ContentBlock, Document, Study
from socratic.llm.base import LLMResponse, ToolCall
from socratic.orchestrator import Orchestrator
from socratic.retrieval import RetrievalService, TxtaiDocumentRetriever
from socratic.services.navigation import NavigationService
from socratic.storage.database import (
    DB,
    get_messages_for_study,
    init_db,
    save_content_blocks,
    save_document,
    save_study,
)
from tests.test_llm import ScriptedLLM


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
def blocks(db):
    doc = Document(filename="test.pdf", page_count=1, block_count=3)
    save_document(db.conn, doc)
    items = [
        ContentBlock(document_id=doc.id, ordinal=1, text="Bloque uno sobre machine learning.", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=2, text="Bloque dos sobre redes neuronales.", page_number=1),
        ContentBlock(document_id=doc.id, ordinal=3, text="Bloque tres sobre backpropagation.", page_number=2),
    ]
    save_content_blocks(db.conn, doc.id, items)
    db.conn.commit()
    return items


@pytest.fixture
def study(db, blocks):
    s = Study(
        document_id=blocks[0].document_id,
        current_block_id=blocks[1].id,
        last_completed_block_id=blocks[0].id,
    )
    save_study(db.conn, s)
    db.conn.commit()
    return s


@pytest.fixture
def retrieval(db, tmp_path, blocks):
    retriever = TxtaiDocumentRetriever(
        storage_path=tmp_path / "retrieval",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    retriever.index_document(blocks[0].document_id, blocks)
    return RetrievalService(retriever=retriever, db=db)


def _build_app(db: DB, retrieval: RetrievalService, llm: ScriptedLLM):
    from fastapi import FastAPI

    navigation = NavigationService(db)
    orchestrator = Orchestrator(
        db=db,
        llm=llm,
        retrieval=retrieval,
        navigation=navigation,
    )
    app = FastAPI()
    app.include_router(interact_router)
    app.dependency_overrides[get_db] = lambda: db
    app.state.orchestrator = orchestrator
    return app


# ── Tests ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_interact_devuelve_respuesta_y_persiste_mensajes(db, study, retrieval, blocks):
    llm = ScriptedLLM([LLMResponse(content="Respuesta del asistente.")])
    app = _build_app(db, retrieval, llm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/interact",
            json={"input": "Hola"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["answer"] == "Respuesta del asistente."
    assert data["study_id"] == study.id
    assert "message_id" in data

    messages = get_messages_for_study(db.conn, study.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hola"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Respuesta del asistente."


@pytest.mark.anyio
async def test_interact_con_tool_de_dominio_avanza_estado(db, study, retrieval, blocks):
    llm = ScriptedLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="complete_current_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Avanzamos al siguiente bloque."),
        ]
    )
    app = _build_app(db, retrieval, llm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/interact",
            json={"input": "continúa"},
        )

    assert resp.status_code == 201
    assert resp.json()["answer"] == "Avanzamos al siguiente bloque."

    # El estudio avanzó.
    from socratic.storage.database import get_study
    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == blocks[2].id


@pytest.mark.anyio
async def test_interact_study_no_encontrado(db, retrieval):
    llm = ScriptedLLM([LLMResponse(content="ok")])
    app = _build_app(db, retrieval, llm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/studies/no-existe/interact",
            json={"input": "Hola"},
        )

    assert resp.status_code == 404


@pytest.mark.anyio
async def test_interact_con_retrieve_document_context_no_modifica_estado(
    db, study, retrieval, blocks
):
    llm = ScriptedLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="retrieve_document_context",
                        arguments_json=json.dumps({"query": "redes neuronales"}),
                    )
                ],
            ),
            LLMResponse(content="Las redes neuronales son modelos inspirados en el cerebro."),
        ]
    )
    app = _build_app(db, retrieval, llm)

    original_current = study.current_block_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/interact",
            json={"input": "¿qué son las redes neuronales?"},
        )

    assert resp.status_code == 201
    from socratic.storage.database import get_study
    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == original_current


@pytest.mark.anyio
async def test_interact_turn_combinado_encadena_dos_tools(db, study, retrieval, blocks):
    llm = ScriptedLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="retrieve_document_context",
                        arguments_json=json.dumps({"query": "redes neuronales"}),
                    )
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c2", name="complete_current_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Te lo explico y avanzamos."),
        ]
    )
    app = _build_app(db, retrieval, llm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/studies/{study.id}/interact",
            json={"input": "explícame esto y luego continúa"},
        )

    assert resp.status_code == 201
    assert resp.json()["answer"] == "Te lo explico y avanzamos."

    from socratic.storage.database import get_study
    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == blocks[2].id
