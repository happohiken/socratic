from __future__ import annotations

from typing import Any

from socratic.llm.base import LLMClient


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
