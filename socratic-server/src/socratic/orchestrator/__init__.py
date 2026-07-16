"""Orquestador conversacional basado en tool calling con un único LLM por Turn.

Exporta:
- ``Orchestrator``: fachada protocolo-agnóstica.
- ``TurnContext``: estado de ejecución de un Turn, inyectado en las tools.
- ``TurnResult``: respuesta final del Turn.
- ``ToolRegistry``, ``default_registry``, ``register_tool``: mecanismo
  único de registro de tools.

Importar ``socratic.orchestrator`` registra las 4 tools iniciales en
``default_registry`` como efecto lateral.
"""
from socratic.orchestrator.orchestrator import Orchestrator, TurnResult
from socratic.orchestrator.registry import (
    RegisteredTool,
    ToolError,
    ToolRegistry,
    default_registry,
    register_tool,
)
from socratic.orchestrator.tools import TurnContext

# Poblar el registro global con las 4 tools iniciales.
import socratic.orchestrator.tools as _tools  # noqa: F401, E402

__all__ = [
    "Orchestrator",
    "RegisteredTool",
    "ToolError",
    "ToolRegistry",
    "TurnContext",
    "TurnResult",
    "default_registry",
    "register_tool",
]
