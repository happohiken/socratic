from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from socratic.llm.base import LLMClient, LLMResponse, ToolCall


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

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = dict(
            model=kwargs.get("model", self._model),
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
        )
        if tools:
            params["tools"] = tools
            if tool_choice is not None:
                params["tool_choice"] = tool_choice

        response = self._synced_client.chat.completions.create(**params)
        message = response.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            arguments = tc.function.arguments or "{}"
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments_json=arguments,
                )
            )

        return LLMResponse(content=message.content or "", tool_calls=tool_calls)
