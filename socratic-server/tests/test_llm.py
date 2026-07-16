from __future__ import annotations

from typing import Any

from socratic.llm.base import LLMClient, LLMResponse, ToolCall


class StubLLM(LLMClient):
    """Implementación stub de LLMClient para pruebas.

    Devuelve respuestas predecibles sin llamar a ningún proveedor real.
    """

    def __init__(self, response: str = "Respuesta de prueba") -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        self.calls.append(messages)
        return self.response


class ScriptedLLM(LLMClient):
    """LLM stub que devuelve una secuencia programada de respuestas.

    Útil para tests del orquestador: cada llamada a `complete_with_tools`
    consume la siguiente respuesta de la cola. `complete` delega en la
    primera respuesta textual.

    Ejemplo::

        llm = ScriptedLLM([
            LLMResponse(content="", tool_calls=[ToolCall(id="1", name="get_current_block", arguments_json="{}")]),
            LLMResponse(content="Respuesta final"),
        ])
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._index = 0
        # Histórico de llamadas para aserciones.
        self.tool_calls_messages: list[list[dict[str, Any]]] = []
        self.complete_calls: list[list[dict[str, str]]] = []
        self.calls_with_tools: list[dict[str, Any]] = []

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        self.complete_calls.append(messages)
        if not self._responses:
            return ""
        return self._responses[min(self._index, len(self._responses) - 1)].content

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls_with_tools.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        if self._index >= len(self._responses):
            raise AssertionError(
                f"ScriptedLLM: más llamadas de las programadas ({self._index + 1})"
            )
        response = self._responses[self._index]
        self._index += 1
        return response
