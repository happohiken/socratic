"""Registro central de tools del orquestador.

Mecanismo único para todas las tools (dominio y recuperación): un decorador
registra la función, el esquema de argumentos se deriva de las anotaciones
de tipo, la validación se realiza con Pydantic en runtime y el resultado
se serializa a JSON.

Las tools son funciones Python con esta convención de firma::

    def tool(context: TurnContext, ...) -> ResultType:
        ...

El primer parámetro debe llamarse ``context`` y es inyectado por el
orquestador (no es visible para el LLM). El resto de parámetros son los
argumentos que el LLM puede rellenar, y se validan con Pydantic.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError, create_model

# Nombre reservado del parámetro que recibe el contexto de ejecución.
CONTEXT_PARAM = "context"


class ToolError(Exception):
    """Error durante el registro o ejecución de una tool."""


@dataclass
class RegisteredTool:
    """Una tool registrada: función + esquema + modelo de validación."""

    name: str
    description: str
    fn: Callable[..., Any]
    arg_model: type[BaseModel]
    schema: dict[str, Any]

    def execute(self, context: Any, arguments: dict[str, Any]) -> Any:
        """Valida ``arguments`` con Pydantic y ejecuta la tool.

        El ``context`` se inyecta como argumento nominal; el resto de
        argumentos se validan con el modelo derivado de la firma.
        """
        try:
            validated = self.arg_model(**arguments)
        except ValidationError as exc:
            raise ToolError(
                f"Argumentos inválidos para '{self.name}': {exc.errors()}"
            ) from exc
        return self.fn(
            context=context,
            **validated.model_dump(),
        )


@dataclass
class ToolRegistry:
    """Diccionario central de tools."""

    _tools: dict[str, RegisteredTool] = field(default_factory=dict)

    def register(
        self,
        name: str,
        description: str,
        fn: Callable[..., Any],
    ) -> RegisteredTool:
        """Registra una función como tool.

        Introspecciona la firma para construir el modelo Pydantic de los
        argumentos visibles para el LLM (todos menos ``context``).
        """
        if name in self._tools:
            raise ToolError(f"Tool '{name}' ya registrada")
        arg_model, schema = _build_arg_model(name, fn)
        tool = RegisteredTool(
            name=name,
            description=description,
            fn=fn,
            arg_model=arg_model,
            schema=schema,
        )
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError(f"Tool '{name}' no registrada") from exc

    def list(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools

    def openai_schemas(self) -> list[dict[str, Any]]:
        """Devuelve las tools en formato OpenAI para el parámetro ``tools``."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.schema,
                },
            }
            for t in self._tools.values()
        ]

    def execute(
        self,
        name: str,
        context: Any,
        arguments: dict[str, Any],
    ) -> Any:
        """Ejecuta una tool por nombre."""
        return self.get(name).execute(context, arguments)


def _build_arg_model(
    name: str,
    fn: Callable[..., Any],
) -> tuple[type[BaseModel], dict[str, Any]]:
    """Construye un modelo Pydantic con los argumentos visibles al LLM."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    if not params or params[0].name != CONTEXT_PARAM:
        raise ToolError(
            f"Tool '{name}' debe tomar '{CONTEXT_PARAM}' como primer parámetro"
        )

    fields: dict[str, Any] = {}
    for p in params[1:]:
        annotation = p.annotation if p.annotation is not inspect.Parameter.empty else Any
        if p.default is inspect.Parameter.empty:
            fields[p.name] = (annotation, ...)
        else:
            fields[p.name] = (annotation, p.default)

    model = create_model(f"{name}_args", **fields)
    schema = model.model_json_schema()
    return model, schema


def serialize_result(result: Any) -> Any:
    """Serializa el resultado de una tool a algo JSON-serializable.

    - ``dict`` / ``list`` / ``None``: tal cual.
    - Modelo Pydantic: ``model_dump()``.
    - ``str``: envuelto en ``{"text": ...}``.
    - Otros: se intenta ``__dict__`` y, si no, ``str()``.
    """
    if result is None:
        return None
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, (dict, list, int, float, bool, str)):
        if isinstance(result, str):
            return {"text": result}
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "__dict__"):
        return vars(result)
    return {"text": str(result)}


# Registro global poblado al importar `orchestrator.tools`.
default_registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    *,
    registry: ToolRegistry | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador que registra una función como tool.

    Por defecto registra en ``default_registry``; pasar ``registry`` para
    registrar en un registro distinto (útil en tests).
    """
    target = registry or default_registry

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        target.register(name, description, fn)
        return fn

    return decorator
