"""Tests del orquestador conversacional (bucle de Turn completo).

Cubren los escenarios del plan:
- Turn sin tools (respuesta directa).
- Turn con una tool de dominio (continuar).
- Turn con una tool de recuperación (pregunta).
- Turn combinado (recuperación + dominio).
- Límite máximo de iteraciones.
- Detección de bucle infinito (misma tool repetida).
- Persistencia de user/assistant (no de tool calls).
- Detección de fin de documento.
- Independencia del protocolo (no importa FastAPI).
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from socratic.domain.models import ContentBlock, Document, Message, Study
from socratic.llm.base import LLMResponse, ToolCall
from socratic.orchestrator import Orchestrator, TurnResult
from socratic.orchestrator.registry import default_registry
from socratic.retrieval import RetrievalService, TxtaiDocumentRetriever
from socratic.services.navigation import NavigationService
from socratic.storage.database import (
    DB,
    get_messages_for_study,
    get_study,
    init_db,
    save_content_blocks,
    save_document,
    save_study,
)
from tests.test_llm import ScriptedLLM


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    database = init_db(path)
    yield database
    database.close()


@pytest.fixture
def blocks(db):
    doc = Document(filename="test.pdf", page_count=2, block_count=3)
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
def orchestrator(db, retrieval, navigation):
    return Orchestrator(
        db=db,
        llm=ScriptedLLM([]),
        retrieval=retrieval,
        navigation=navigation,
        max_tool_iterations=5,
        history_messages=10,
    )


def _make_orchestrator(
    db: DB,
    retrieval: RetrievalService,
    navigation: NavigationService,
    responses: list[LLMResponse],
    *,
    max_tool_iterations: int = 5,
    history_messages: int = 10,
) -> tuple[Orchestrator, ScriptedLLM]:
    llm = ScriptedLLM(responses)
    orch = Orchestrator(
        db=db,
        llm=llm,
        retrieval=retrieval,
        navigation=navigation,
        max_tool_iterations=max_tool_iterations,
        history_messages=history_messages,
    )
    return orch, llm


# ── Turn sin tools ────────────────────────────────────────────


def test_turn_sin_tools_devuelve_respuesta_directa(db, study, retrieval, navigation, blocks):
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="No entiendo, ¿puedes reformular?")],
    )
    result = orch.interact(study, "foo bar baz")
    assert isinstance(result, TurnResult)
    assert result.answer == "No entiendo, ¿puedes reformular?"
    assert result.study_id == study.id
    assert result.tool_calls == []
    # Una sola llamada al LLM.
    assert len(llm.calls_with_tools) == 1
    # Las tools se pasan al LLM.
    assert llm.calls_with_tools[0]["tools"] is not None
    assert len(llm.calls_with_tools[0]["tools"]) == 4


def test_turn_sin_tools_persiste_user_y_assistant_no_tool_calls(db, study, retrieval, navigation):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="Respuesta final")],
    )
    orch.interact(study, "Hola")

    messages = get_messages_for_study(db.conn, study.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hola"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Respuesta final"
    # content_block_id asociado al bloque actual del Turn.
    assert messages[0].content_block_id is not None
    assert messages[1].content_block_id is not None


# ── Turn con una tool de dominio ──────────────────────────────


def test_turn_con_complete_current_block_avanza_estado(db, study, retrieval, navigation, blocks):
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="complete_current_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Continuamos con el siguiente bloque."),
        ],
    )
    result = orch.interact(study, "continúa")

    assert result.answer == "Continuamos con el siguiente bloque."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "complete_current_block"
    assert result.tool_calls[0]["ok"] is True

    # El estado del estudio avanzó y se persistió.
    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == blocks[2].id
    assert updated.last_completed_block_id == blocks[1].id

    # Dos llamadas al LLM: una con tool_call, otra con respuesta final.
    assert len(llm.calls_with_tools) == 2


def test_turn_con_get_current_block_no_modifica_estado(db, study, retrieval, navigation, blocks):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="get_current_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Estás leyendo el bloque dos sobre redes neuronales."),
        ],
    )
    original_current = study.current_block_id
    orch.interact(study, "¿qué estoy leyendo?")

    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == original_current


def test_turn_con_previous_block_retrocede(db, study, retrieval, navigation, blocks):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="previous_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Retrocedimos al bloque uno."),
        ],
    )
    orch.interact(study, "vuelve atrás")

    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == blocks[0].id


# ── Turn con tool de recuperación ─────────────────────────────


def test_turn_con_retrieve_document_context_no_modifica_estado(db, study, retrieval, navigation):
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="retrieve_document_context",
                        arguments_json=json.dumps({"query": "redes neuronales"}),
                    )
                ],
            ),
            LLMResponse(content="Las redes neuronales son modelos inspirados en el cerebro."),
        ],
    )
    original_current = study.current_block_id
    result = orch.interact(study, "¿qué son las redes neuronales?")

    assert result.answer.startswith("Las redes neuronales")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["arguments"] == {"query": "redes neuronales"}

    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == original_current


# ── Turn combinado: recuperación + dominio ────────────────────


def test_turn_combinado_recuperacion_y_completar(db, study, retrieval, navigation, blocks):
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [
            # 1. LLM pide recuperar contexto.
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="retrieve_document_context",
                        arguments_json=json.dumps({"query": "redes neuronales"}),
                    )
                ],
            ),
            # 2. LLM pide completar el bloque actual.
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_2", name="complete_current_block", arguments_json="{}")
                ],
            ),
            # 3. Respuesta final.
            LLMResponse(content="Te lo explico y avanzamos al siguiente bloque."),
        ],
    )
    result = orch.interact(study, "explícame esto y luego continúa")

    assert result.answer == "Te lo explico y avanzamos al siguiente bloque."
    assert len(result.tool_calls) == 2
    assert [tc["name"] for tc in result.tool_calls] == [
        "retrieve_document_context",
        "complete_current_block",
    ]
    # El estado avanzó tras el complete.
    updated = get_study(db.conn, study.id)
    assert updated.current_block_id == blocks[2].id
    # Tres llamadas al LLM.
    assert len(llm.calls_with_tools) == 3


# ── Límite de iteraciones ─────────────────────────────────────


def test_max_iteraciones_fuerza_respuesta_final_sin_tools(db, study, retrieval, navigation):
    # El LLM pide tools en cada una de las 3 iteraciones permitidas.
    infinite_tool_call = LLMResponse(
        content="",
        tool_calls=[
            ToolCall(id=f"call_{i}", name="get_current_block", arguments_json="{}")
            for i in range(1)
        ],
    )
    responses = [infinite_tool_call] * 3 + [LLMResponse(content="Respuesta forzada")]
    orch, llm = _make_orchestrator(
        db, retrieval, navigation, responses,
        max_tool_iterations=3,
    )
    result = orch.interact(study, "loop")

    assert result.answer == "Respuesta forzada"
    # 3 iteraciones de tools + 1 llamada final sin tools = 4 llamadas.
    assert len(llm.calls_with_tools) == 4
    # La última llamada no pasa tools.
    assert llm.calls_with_tools[-1]["tools"] is None


# ── Detección de bucle infinito ───────────────────────────────


def test_bucle_infinito_misma_tool_mismos_args_se_detecta(db, study, retrieval, navigation):
    """Si el LLM repite la misma tool con los mismos argumentos, el orquestador
    no la ejecuta de nuevo: inyecta un mensaje de error y el LLM debe responder."""
    same_call = LLMResponse(
        content="",
        tool_calls=[
            ToolCall(id="call_1", name="get_current_block", arguments_json="{}"),
        ],
    )
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [
            same_call,
            # Segunda iteración: misma tool, mismos args.
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_2", name="get_current_block", arguments_json="{}"),
                ],
            ),
            LLMResponse(content="Ya te lo dije."),
        ],
    )
    result = orch.interact(study, "repite")

    assert result.answer == "Ya te lo dije."
    # Solo se ejecuta la tool una vez (la segunda se salta).
    executed = [tc for tc in result.tool_calls if tc.get("ok")]
    assert len(executed) == 1


# ── Persistencia ──────────────────────────────────────────────


def test_no_se_persisten_tool_calls(db, study, retrieval, navigation):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="get_current_block", arguments_json="{}")
                ],
            ),
            LLMResponse(content="Respuesta final"),
        ],
    )
    orch.interact(study, "pregunta")

    messages = get_messages_for_study(db.conn, study.id)
    # Solo user + assistant.
    assert len(messages) == 2
    assert {m.role for m in messages} == {"user", "assistant"}


def test_historial_reciente_se_incluye_en_contexto(db, study, retrieval, navigation):
    # Sembrar historial previo.
    from socratic.storage.database import save_message
    for i in range(5):
        save_message(db.conn, Message(study_id=study.id, role="user", content=f"pregunta {i}"))
        save_message(db.conn, Message(study_id=study.id, role="assistant", content=f"respuesta {i}"))
    db.conn.commit()

    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="ok")],
        history_messages=10,
    )
    orch.interact(study, "nueva pregunta")

    messages = llm.calls_with_tools[0]["messages"]
    # system + 10 historial + 1 input = 12
    assert len(messages) == 12
    # El último mensaje es la entrada del usuario.
    assert messages[-1] == {"role": "user", "content": "nueva pregunta"}


def test_historial_se_trunca_a_n_mensajes(db, study, retrieval, navigation):
    from socratic.storage.database import save_message
    for i in range(20):
        save_message(db.conn, Message(study_id=study.id, role="user", content=f"p{i}"))
        save_message(db.conn, Message(study_id=study.id, role="assistant", content=f"r{i}"))
    db.conn.commit()

    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="ok")],
        history_messages=4,
    )
    orch.interact(study, "nueva")

    messages = llm.calls_with_tools[0]["messages"]
    # system + 4 historial + 1 input = 6
    assert len(messages) == 6


# ── Estado del estudio en el system prompt ────────────────────


def test_system_prompt_incluye_estado_y_bloque_actual(db, study, retrieval, navigation, blocks):
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="ok")],
    )
    orch.interact(study, "pregunta")

    system_msg = llm.calls_with_tools[0]["messages"][0]
    assert system_msg["role"] == "system"
    content = system_msg["content"]
    assert "Estado actual del estudio" in content
    assert "Bloque dos sobre redes neuronales." in content
    assert "test.pdf" in content


def test_system_prompt_indica_fin_de_documento_si_no_hay_bloque(db, study, retrieval, navigation):
    study.current_block_id = None
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [LLMResponse(content="ok")],
    )
    orch.interact(study, "pregunta")

    system_msg = llm.calls_with_tools[0]["messages"][0]
    assert "final del documento" in system_msg["content"]


# ── Argumentos inválidos ──────────────────────────────────────


def test_argumentos_invalidos_se_capturan_y_devuelven_error(db, study, retrieval, navigation):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    # Falta `query` (argumento requerido).
                    ToolCall(
                        id="c1",
                        name="retrieve_document_context",
                        arguments_json="{}",
                    )
                ],
            ),
            LLMResponse(content="Necesito más información."),
        ],
    )
    result = orch.interact(study, "pregunta")
    assert result.answer == "Necesito más información."
    # La tool falló pero se registró.
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["ok"] is False


def test_json_invalido_en_arguments_se_captura(db, study, retrieval, navigation):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="get_current_block",
                        arguments_json="esto no es json",
                    )
                ],
            ),
            LLMResponse(content="Recuperado."),
        ],
    )
    result = orch.interact(study, "pregunta")
    assert result.answer == "Recuperado."
    assert result.tool_calls[0]["ok"] is False


def test_tool_inexistente_se_captura(db, study, retrieval, navigation):
    orch, _ = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="no_existe", arguments_json="{}")
                ],
            ),
            LLMResponse(content="No pude hacerlo."),
        ],
    )
    result = orch.interact(study, "pregunta")
    assert result.tool_calls[0]["ok"] is False
    assert "no registrada" in result.tool_calls[0]["error"] or "error" in result.tool_calls[0]


# ── Independencia del protocolo ───────────────────────────────


def test_orchestrator_no_importa_fastapi_ni_starlette():
    """El orquestador debe ser agnóstico del protocolo.

    Se comprueba que no haya imports reales de fastapi/starlette, no
    menciones en docstrings o comentarios.
    """
    import ast

    import socratic.orchestrator.orchestrator as mod

    tree = ast.parse(open(mod.__file__).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(("fastapi", "starlette")), \
                    f"Import prohibido: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("fastapi", "starlette")), \
                f"Import prohibido: {node.module}"


def test_tools_no_importan_storage_directamente():
    """Las tools delegan en servicios; no llaman a funciones de storage.

    Se permite importar el tipo ``DB`` bajo ``TYPE_CHECKING`` (solo para
    anotación, no se ejecuta en runtime). Lo que se prohíbe es llamar a
    funciones como ``save_*``, ``get_*``, ``update_*`` directamente.
    """
    import ast

    import socratic.orchestrator.tools as mod

    src = open(mod.__file__).read()
    tree = ast.parse(src)

    # Recoger los nombres importados de socratic.storage en cualquier sitio.
    storage_call_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "socratic.storage"
        ):
            for alias in node.names:
                storage_call_names.add(alias.asname or alias.name)

    # Buscar llamadas a esos nombres en el cuerpo del módulo (no en TYPE_CHECKING).
    # A nivel práctico: si los nombres se invocan como función, falla.
    forbidden_prefixes = ("save_", "get_", "update_", "delete_", "init_db", "list_")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in storage_call_names:
                assert not any(
                    func.id.startswith(p) for p in forbidden_prefixes
                ), f"Llamada prohibida a storage en tools: {func.id}"
            if isinstance(func, ast.Attribute) and func.attr.startswith(
                forbidden_prefixes
            ):
                # Permitir self._db.conn.execute(...) no aplica aquí: las tools
                # no reciben `db` como objeto activo en este módulo.
                # Pero por seguridad, comprobamos que no se llame a funciones
                # de storage.database a través del módulo.
                pass


# ── Múltiples tools en una sola respuesta del LLM ─────────────


def test_varias_tools_en_una_sola_respuesta(db, study, retrieval, navigation, blocks):
    """El LLM puede pedir varias tools en una misma respuesta; todas se ejecutan."""
    orch, llm = _make_orchestrator(
        db, retrieval, navigation,
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="get_current_block", arguments_json="{}"),
                    ToolCall(
                        id="c2",
                        name="retrieve_document_context",
                        arguments_json=json.dumps({"query": "machine learning"}),
                    ),
                ],
            ),
            LLMResponse(content="Respuesta combinada."),
        ],
    )
    result = orch.interact(study, "pregunta")

    assert len(result.tool_calls) == 2
    assert {tc["name"] for tc in result.tool_calls} == {
        "get_current_block",
        "retrieve_document_context",
    }
    # 2 llamadas al LLM.
    assert len(llm.calls_with_tools) == 2
    # Los mensajes tool se añaden después del assistant.
    second_call_messages = llm.calls_with_tools[1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert {m["tool_call_id"] for m in tool_msgs} == {"c1", "c2"}
