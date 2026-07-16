from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """Solicitud de ejecución de una tool devuelta por el LLM.

    `arguments_json` conserva el JSON en bruto devuelto por el proveedor;
    el orquestador lo parsea y valida al ejecutar la tool.
    """

    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class LLMResponse:
    """Respuesta estructurada de un LLM con soporte de tools.

    Si `tool_calls` está vacío, `content` es la respuesta textual final.
    Si `tool_calls` no está vacío, el LLM solicita ejecutar tools; `content`
    puede ser vacío o contener razonamiento intermedio.
    """

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(Protocol):
    """Interfaz mínima para un cliente de modelo de lenguaje.

    Cualquier implementación concreta debe cumplir este protocolo.
    """

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Enviar un conjunto de mensajes al modelo y devolver la respuesta.

        Parameters
        ----------
        messages:
            Lista de dicts con claves "role" y "content".
        **kwargs:
            Parámetros específicos del proveedor (temperature, model, etc.).

        Returns
        -------
        str
            El texto de la respuesta del modelo.
        """
        ...

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Como `complete` pero admite tools y devuelve una respuesta estructurada.

        Parameters
        ----------
        messages:
            Mensajes con roles "system"/"user"/"assistant"/"tool". Los
            mensajes `assistant` con tool_calls y los `tool` con resultados
            pueden aparecer durante el bucle de tool calling.
        tools:
            Lista de tools en formato OpenAI
            (``{"type": "function", "function": {...}}``). Si es ``None`` o
            vacía, el LLM responde sin llamar tools.
        tool_choice:
            Control de selección de tools del proveedor
            (``"auto"``, ``"none"``, ``"required"``…). Si es ``None`` no se
            envía.
        **kwargs:
            Parámetros específicos del proveedor.

        Returns
        -------
        LLMResponse
            Respuesta con `content` y, opcionalmente, `tool_calls`.
        """
        ...
