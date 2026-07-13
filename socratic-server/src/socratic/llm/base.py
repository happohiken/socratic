from __future__ import annotations

from typing import Any, Protocol


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
