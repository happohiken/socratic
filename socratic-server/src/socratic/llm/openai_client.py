from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from socratic.llm.base import LLMClient


class OpenAIClient(LLMClient):
    """Implementación de LLMClient que usa la API de OpenAI."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        timeout: int = 120,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._timeout = timeout
        self._client: OpenAI | None = None

    @property
    def _synced_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        params: dict[str, Any] = dict(
            model=kwargs.get("model", self._model),
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
        )
        response = self._synced_client.chat.completions.create(**params)
        return response.choices[0].message.content or ""
