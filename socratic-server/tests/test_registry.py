"""Tests del registro de tools del orquestador."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from socratic.orchestrator.registry import (
    RegisteredTool,
    ToolError,
    ToolRegistry,
    default_registry,
    register_tool,
    serialize_result,
)


def _fresh_registry() -> ToolRegistry:
    return ToolRegistry()


def test_registra_tool_y_construye_esquema_desde_anotaciones():
    registry = _fresh_registry()

    @register_tool(name="sumar", description="Suma dos enteros", registry=registry)
    def sumar(context: Any, a: int, b: int) -> int:
        return a + b

    tool = registry.get("sumar")
    assert tool.name == "sumar"
    assert tool.description == "Suma dos enteros"
    schema = tool.schema
    assert schema["type"] == "object"
    assert set(schema["properties"].keys()) == {"a", "b"}
    assert set(schema["required"]) == {"a", "b"}


def test_esquema_openai_tiene_estructura_function():
    registry = _fresh_registry()

    @register_tool(name="t", description="desc", registry=registry)
    def t(context: Any) -> None:
        return None

    schemas = registry.openai_schemas()
    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "t",
                "description": "desc",
                "parameters": schemas[0]["function"]["parameters"],
            },
        }
    ]


def test_tool_sin_parametros_ademas_de_context():
    registry = _fresh_registry()

    @register_tool(name="noop", description="no op", registry=registry)
    def noop(context: Any) -> str:
        return "ok"

    tool = registry.get("noop")
    assert tool.schema["properties"] == {}
    assert "required" not in tool.schema


def test_parametros_con_default_no_son_required():
    registry = _fresh_registry()

    @register_tool(name="greet", description="greet", registry=registry)
    def greet(context: Any, name: str, polite: bool = True) -> str:
        return name

    schema = registry.get("greet").schema
    assert "name" in schema["required"]
    assert "polite" not in schema.get("required", [])


def test_falla_si_no_tiene_parametro_context():
    registry = _fresh_registry()
    with pytest.raises(ToolError, match="context"):

        @register_tool(name="bad", description="bad", registry=registry)
        def bad(a: int) -> int:
            return a


def test_falla_si_nombre_duplicado():
    registry = _fresh_registry()

    @register_tool(name="dup", description="d1", registry=registry)
    def dup(context: Any) -> None:
        return None

    with pytest.raises(ToolError, match="ya registrada"):

        @register_tool(name="dup", description="d2", registry=registry)
        def dup2(context: Any) -> None:
            return None


def test_get_falla_si_no_existe():
    registry = _fresh_registry()
    with pytest.raises(ToolError, match="no registrada"):
        registry.get("missing")


def test_execute_valida_argumentos_con_pydantic():
    registry = _fresh_registry()

    @register_tool(name="echo", description="echo", registry=registry)
    def echo(context: Any, text: str, times: int = 1) -> list[str]:
        return [text] * times

    result = registry.execute("echo", context=None, arguments={"text": "hi", "times": 3})
    assert result == ["hi", "hi", "hi"]


def test_execute_falla_si_argumentos_invalidos():
    registry = _fresh_registry()

    @register_tool(name="echo", description="echo", registry=registry)
    def echo(context: Any, text: str) -> str:
        return text

    with pytest.raises(ToolError, match="Argumentos inválidos"):
        registry.execute("echo", context=None, arguments={"text": 123})


def test_execute_falla_si_falta_argumento_required():
    registry = _fresh_registry()

    @register_tool(name="echo", description="echo", registry=registry)
    def echo(context: Any, text: str) -> str:
        return text

    with pytest.raises(ToolError):
        registry.execute("echo", context=None, arguments={})


def test_execute_propaga_excepciones_de_la_tool():
    registry = _fresh_registry()

    @register_tool(name="boom", description="boom", registry=registry)
    def boom(context: Any) -> None:
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        registry.execute("boom", context=None, arguments={})


def test_list_y_has():
    registry = _fresh_registry()

    @register_tool(name="a", description="da", registry=registry)
    def a(context: Any) -> None:
        return None

    @register_tool(name="b", description="db", registry=registry)
    def b(context: Any) -> None:
        return None

    assert {t.name for t in registry.list()} == {"a", "b"}
    assert registry.has("a")
    assert not registry.has("c")


# ── serialize_result ──────────────────────────────────────────


def test_serialize_dict_devuelve_tal_cual():
    assert serialize_result({"a": 1}) == {"a": 1}


def test_serialize_list_devuelve_tal_cual():
    assert serialize_result([1, 2, 3]) == [1, 2, 3]


def test_serialize_none_devuelve_none():
    assert serialize_result(None) is None


def test_serialize_str_envuelve_en_text():
    assert serialize_result("hola") == {"text": "hola"}


def test_serialize_int_devuelve_tal_cual():
    # Solo str se envuelve en {"text": ...}; el resto de escalares
    # JSON-serializables se devuelven tal cual.
    assert serialize_result(42) == 42
    assert serialize_result(3.14) == 3.14
    assert serialize_result(True) is True


def test_serialize_pydantic_model_usa_model_dump():
    from pydantic import BaseModel

    class M(BaseModel):
        x: int
        y: str

    assert serialize_result(M(x=1, y="a")) == {"x": 1, "y": "a"}


# ── Registro global ──────────────────────────────────────────


def test_registro_global_tiene_las_4_tools_iniciales():
    names = {t.name for t in default_registry.list()}
    assert names == {
        "get_current_block",
        "complete_current_block",
        "previous_block",
        "retrieve_document_context",
    }


def test_decorador_registro_global_sin_argumento_opcional():
    # El decorador sin `registry=` debe registrar en `default_registry`.
    @register_tool(name="_test_global", description="tmp")
    def _test_global(context: Any) -> str:
        return "global"

    try:
        assert default_registry.has("_test_global")
    finally:
        # Limpieza para no contaminar otras pruebas.
        default_registry._tools.pop("_test_global", None)
