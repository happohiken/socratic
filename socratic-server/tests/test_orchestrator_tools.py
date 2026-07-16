"""Tests de las 4 tools del orquestador."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from socratic.domain.models import ContentBlock, Document, Study
from socratic.orchestrator.tools import TurnContext, retrieve_document_context
from socratic.retrieval import RetrievalService, TxtaiDocumentRetriever
from socratic.services.navigation import NavigationError, NavigationService
from socratic.storage.database import (
    DB,
    get_content_block,
    init_db,
    save_content_blocks,
    save_document,
    save_study,
)


# ── Fixtures ──────────────────────────────────────────────────


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
        ContentBlock(
            document_id=doc.id,
            ordinal=1,
            text="Bloque uno sobre machine learning.",
            page_number=1,
            block_type="paragraph",
        ),
        ContentBlock(
            document_id=doc.id,
            ordinal=2,
            text="Bloque dos sobre redes neuronales.",
            page_number=1,
            block_type="paragraph",
        ),
        ContentBlock(
            document_id=doc.id,
            ordinal=3,
            text="Bloque tres sobre backpropagation.",
            page_number=2,
            block_type="paragraph",
        ),
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


@pytest.fixture
def navigation(db):
    return NavigationService(db)


@pytest.fixture
def context(study, blocks, db, retrieval, navigation):
    return TurnContext(
        study=study,
        current_block=blocks[1],
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )


# ── get_current_block ─────────────────────────────────────────


def test_get_current_block_devuelve_bloque_actual(context, blocks):
    from socratic.orchestrator.tools import get_current_block

    result = get_current_block(context=context)
    assert result == {
        "id": blocks[1].id,
        "document_id": blocks[1].document_id,
        "ordinal": 2,
        "text": "Bloque dos sobre redes neuronales.",
        "page_number": 1,
        "block_type": "paragraph",
    }


def test_get_current_block_no_modifica_estado(context, study):
    from socratic.orchestrator.tools import get_current_block

    original_current = study.current_block_id
    get_current_block(context=context)
    assert study.current_block_id == original_current


def test_get_current_block_devuelve_none_si_no_hay_actual(db, blocks, study, retrieval, navigation):
    from socratic.orchestrator.tools import get_current_block

    study.current_block_id = None
    ctx = TurnContext(
        study=study,
        current_block=None,
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    assert get_current_block(context=ctx) is None


# ── complete_current_block ────────────────────────────────────


def test_complete_current_block_avanza_y_devuelve_nuevo(context, study, blocks):
    from socratic.orchestrator.tools import complete_current_block

    result = complete_current_block(context=context)
    assert result is not None
    assert result["id"] == blocks[2].id
    assert result["ordinal"] == 3
    assert study.current_block_id == blocks[2].id
    assert study.last_completed_block_id == blocks[1].id
    # El contexto se actualiza para siguientes tools.
    assert context.current_block.id == blocks[2].id


def test_complete_current_block_devuelve_none_al_final(db, blocks, study, retrieval, navigation):
    from socratic.orchestrator.tools import complete_current_block

    # Posicionar al final.
    study.current_block_id = blocks[2].id
    study.last_completed_block_id = blocks[1].id
    ctx = TurnContext(
        study=study,
        current_block=blocks[2],
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    result = complete_current_block(context=ctx)
    assert result is None
    assert study.current_block_id is None
    assert ctx.current_block is None


def test_complete_current_block_sin_bloque_actual_devuelve_error(db, study, retrieval, navigation):
    from socratic.orchestrator.tools import complete_current_block

    study.current_block_id = None
    ctx = TurnContext(
        study=study,
        current_block=None,
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    result = complete_current_block(context=ctx)
    assert "error" in result


# ── previous_block ────────────────────────────────────────────


def test_previous_block_retrocede_y_devuelve_nuevo(context, study, blocks):
    from socratic.orchestrator.tools import previous_block

    result = previous_block(context=context)
    assert result["id"] == blocks[0].id
    assert study.current_block_id == blocks[0].id
    assert context.current_block.id == blocks[0].id


def test_previous_block_en_primer_bloque_devuelve_error(db, blocks, study, retrieval, navigation):
    from socratic.orchestrator.tools import previous_block

    study.current_block_id = blocks[0].id
    ctx = TurnContext(
        study=study,
        current_block=blocks[0],
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    result = previous_block(context=ctx)
    assert "error" in result


def test_previous_block_desde_final_vuelve_a_ultimo_completado(
    db, blocks, study, retrieval, navigation
):
    from socratic.orchestrator.tools import previous_block

    study.current_block_id = None
    study.last_completed_block_id = blocks[2].id
    ctx = TurnContext(
        study=study,
        current_block=None,
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    result = previous_block(context=ctx)
    assert result["id"] == blocks[2].id
    assert study.current_block_id == blocks[2].id


# ── retrieve_document_context ─────────────────────────────────


def test_retrieve_document_context_devuelve_fragmentos_estructurados(context):
    result = retrieve_document_context(context=context, query="redes neuronales")
    assert isinstance(result, list)
    # El resultado son dicts con las claves acordadas.
    if result:
        item = result[0]
        assert set(item.keys()) == {
            "block_id",
            "document_id",
            "ordinal",
            "page_number",
            "text",
            "score",
        }
        assert isinstance(item["score"], float)


def test_retrieve_document_context_no_modifica_estado(context, study):
    original_current = study.current_block_id
    retrieve_document_context(context=context, query="machine learning")
    assert study.current_block_id == original_current


def test_retrieve_document_context_sin_bloque_actual_devuelve_lista_vacia(
    db, study, retrieval, navigation
):
    study.current_block_id = None
    ctx = TurnContext(
        study=study,
        current_block=None,
        db=db,
        retrieval=retrieval,
        navigation=navigation,
    )
    assert retrieve_document_context(context=ctx, query="cualquier cosa") == []


# ── Registro global ───────────────────────────────────────────


def test_las_4_tools_estan_registradas_en_registro_global():
    from socratic.orchestrator.registry import default_registry

    names = {t.name for t in default_registry.list()}
    assert names == {
        "get_current_block",
        "complete_current_block",
        "previous_block",
        "retrieve_document_context",
    }


def test_esquema_de_retrieve_document_context_exige_query():
    from socratic.orchestrator.registry import default_registry

    tool = default_registry.get("retrieve_document_context")
    assert "query" in tool.schema["properties"]
    assert tool.schema["required"] == ["query"]


def test_tools_de_dominio_no_tienen_argumentos_visibles():
    from socratic.orchestrator.registry import default_registry

    for name in ("get_current_block", "complete_current_block", "previous_block"):
        schema = default_registry.get(name).schema
        assert schema["properties"] == {}
        assert "required" not in schema
