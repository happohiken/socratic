"""Fachada del orquestador conversacional.

Independiente del protocolo (no conoce REST, HTTP ni FastAPI). Recibe
objetos de dominio (el ``Study``, la entrada del usuario como texto) y
devuelve una respuesta del asistente.

La lógica gira en torno al concepto de **Turn**: unidad transitoria de
interacción que modela la entrada del usuario, los tool calls solicitados
por el LLM, sus resultados y la respuesta final. Solo se persisten los
mensajes ``user`` y ``assistant`` finales; los tool calls viven en
memoria durante el Turn y se registran para depuración.

Bucle por Turn::

    construir contexto inicial (system + estado + historial + entrada)
    repetir hasta max_iteraciones:
        llamar al LLM con tools
        si no hay tool_calls -> respuesta final, salir
        si hay tool_calls:
            validar y ejecutar cada una
            inyectar resultados como mensajes `tool`
            detectar repetición sin progreso
    si se agotan las iteraciones, forzar respuesta final sin tools
    persistir user/assistant
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from socratic.domain.models import ContentBlock, Document, Message, Study
from socratic.llm.base import LLMClient
from socratic.orchestrator.registry import (
    ToolError,
    ToolRegistry,
    default_registry,
    serialize_result,
)
from socratic.orchestrator.tools import TurnContext
from socratic.retrieval import RetrievalService
from socratic.services.navigation import NavigationService
from socratic.storage.database import (
    DB,
    get_content_block,
    get_document,
    get_messages_for_study,
    save_message,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """\
Eres un profesor particular que guía al estudiante en la lectura \
secuencial de un documento. El estudiante lee bloques de texto uno a uno \
y puede pedirte continuar, repetir, retroceder o hacer preguntas sobre \
el contenido.

Reglas:
- Usa las tools disponibles para consultar o modificar el estado de \
lectura. No inventes tools.
- No repitas la misma tool con los mismos argumentos si no hubo progreso.
- Usa `retrieve_document_context` solo cuando la pregunta requiera \
contexto más allá del bloque actual. Para navegar (continuar, repetir, \
retroceder) no la necesitas.
- Responde de forma concisa y relacionada con el contenido del documento.
- No divagues; mantén el foco en el texto que el estudiante está leyendo.
"""


@dataclass
class TurnResult:
    """Resultado de ejecutar un Turn."""

    answer: str
    study_id: str
    message_id: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class Orchestrator:
    """Fachada del orquestador conversacional.

    Construye el contexto del Turn, ejecuta el bucle de tool calling,
    persiste los mensajes user/assistant y devuelve la respuesta final.
    """

    def __init__(
        self,
        db: DB,
        llm: LLMClient,
        retrieval: RetrievalService,
        navigation: NavigationService,
        registry: ToolRegistry | None = None,
        *,
        max_tool_iterations: int = 5,
        history_messages: int = 10,
    ) -> None:
        self._db = db
        self._llm = llm
        self._retrieval = retrieval
        self._navigation = navigation
        self._registry = registry or default_registry
        self._max_tool_iterations = max_tool_iterations
        self._history_messages = history_messages

    def interact(self, study: Study, user_input: str) -> TurnResult:
        """Ejecuta un Turn completo para ``user_input`` sobre ``study``.

        Persiste los mensajes user/assistant (no los tool calls) y
        devuelve la respuesta final.
        """
        current_block = _load_current_block(self._db, study)
        document = _load_document(self._db, study)

        context = TurnContext(
            study=study,
            current_block=current_block,
            db=self._db,
            retrieval=self._retrieval,
            navigation=self._navigation,
        )

        messages = self._build_initial_messages(
            study=study,
            current_block=current_block,
            document=document,
            user_input=user_input,
        )

        tool_calls_log: list[dict[str, Any]] = []
        answer = self._run_tool_loop(
            context=context,
            messages=messages,
            tool_calls_log=tool_calls_log,
        )

        message_id = self._persist_messages(
            study=study,
            current_block=current_block,
            user_input=user_input,
            answer=answer,
        )

        return TurnResult(
            answer=answer,
            study_id=study.id,
            message_id=message_id,
            tool_calls=tool_calls_log,
        )

    # ── Construcción del contexto inicial ─────────────────────────

    def _build_initial_messages(
        self,
        *,
        study: Study,
        current_block: ContentBlock | None,
        document: Document | None,
        user_input: str,
    ) -> list[dict[str, Any]]:
        system_content = SYSTEM_PROMPT_TEMPLATE + _format_state(
            study=study,
            current_block=current_block,
            document=document,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]

        history = get_messages_for_study(self._db.conn, study.id)
        recent = history[-self._history_messages :] if self._history_messages > 0 else []
        for m in recent:
            messages.append({"role": m.role, "content": m.content})

        messages.append({"role": "user", "content": user_input})
        return messages

    # ── Bucle de tool calling ─────────────────────────────────────

    def _run_tool_loop(
        self,
        *,
        context: TurnContext,
        messages: list[dict[str, Any]],
        tool_calls_log: list[dict[str, Any]],
    ) -> str:
        """Ejecuta el bucle de tool calling y devuelve la respuesta final."""
        previous_calls: list[tuple[str, str]] = []
        tools_schema = self._registry.openai_schemas()

        for _ in range(self._max_tool_iterations):
            response = self._llm.complete_with_tools(
                messages=messages,
                tools=tools_schema,
            )

            if not response.has_tool_calls:
                return response.content

            messages.append(
                _assistant_message_with_tools(response.content, response.tool_calls)
            )

            for tc in response.tool_calls:
                call_key = (tc.name, tc.arguments_json)
                if call_key in previous_calls:
                    messages.append(
                        _tool_result_message(
                            tool_call_id=tc.id,
                            result={"error": "Tool ya invocada con los mismos argumentos."},
                        )
                    )
                    logger.warning(
                        "Bucle detectado: tool=%s repetida sin progreso", tc.name
                    )
                    continue
                previous_calls.append(call_key)

                result, executed = self._execute_tool_safe(
                    name=tc.name,
                    arguments_json=tc.arguments_json,
                    context=context,
                )
                tool_calls_log.append(executed)
                messages.append(_tool_result_message(tool_call_id=tc.id, result=result))

        # Se agotaron las iteraciones: forzar respuesta final sin tools.
        logger.warning(
            "Máximo de iteraciones (%d) alcanzado; forzando respuesta final",
            self._max_tool_iterations,
        )
        response = self._llm.complete_with_tools(messages=messages, tools=None)
        return response.content

    def _execute_tool_safe(
        self,
        *,
        name: str,
        arguments_json: str,
        context: TurnContext,
    ) -> tuple[Any, dict[str, Any]]:
        """Ejecuta una tool capturando cualquier error.

        Devuelve (resultado_serializable, log_entry).
        """
        log_entry: dict[str, Any] = {"name": name, "arguments": None}
        try:
            arguments = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as exc:
            logger.exception("JSON inválido en arguments de tool %s", name)
            log_entry["ok"] = False
            log_entry["error"] = f"JSON inválido en arguments: {exc}"
            return (
                {"error": f"JSON inválido en arguments: {exc}"},
                log_entry,
            )
        log_entry["arguments"] = arguments

        try:
            result = self._registry.execute(name, context, arguments)
            serialized = serialize_result(result)
            log_entry["ok"] = True
            return serialized, log_entry
        except ToolError as exc:
            logger.warning("Tool %s falló: %s", name, exc)
            log_entry["ok"] = False
            log_entry["error"] = str(exc)
            return {"error": str(exc)}, log_entry
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s lanzó excepción no controlada", name)
            log_entry["ok"] = False
            log_entry["error"] = str(exc)
            return {"error": f"Error interno ejecutando '{name}'"}, log_entry

    # ── Persistencia ──────────────────────────────────────────────

    def _persist_messages(
        self,
        *,
        study: Study,
        current_block: ContentBlock | None,
        user_input: str,
        answer: str,
    ) -> str:
        """Persiste los mensajes user y assistant. Devuelve el id del assistant."""
        block_id = current_block.id if current_block else None

        user_message = Message(
            study_id=study.id,
            content_block_id=block_id,
            role="user",
            content=user_input,
        )
        save_message(self._db.conn, user_message)

        assistant_message = Message(
            study_id=study.id,
            content_block_id=block_id,
            role="assistant",
            content=answer,
        )
        save_message(self._db.conn, assistant_message)
        self._db.conn.commit()
        return assistant_message.id


# ── Helpers ──────────────────────────────────────────────────────


def _load_current_block(db: DB, study: Study) -> ContentBlock | None:
    if not study.current_block_id:
        return None
    return get_content_block(db.conn, study.current_block_id)


def _load_document(db: DB, study: Study) -> Document | None:
    return get_document(db.conn, study.document_id)


def _format_state(
    *,
    study: Study,
    current_block: ContentBlock | None,
    document: Document | None,
) -> str:
    """Construye el bloque de estado del estudio para el system prompt."""
    lines: list[str] = ["\nEstado actual del estudio:"]
    if document is not None:
        lines.append(f"- Documento: {document.filename}")
    if current_block is None:
        lines.append("- Has alcanzado el final del documento.")
        lines.append(
            "- Si el usuario quiere seguir, sugiere retroceder con "
            "`previous_block` o explicar que el documento ha terminado."
        )
        return "\n".join(lines)

    lines.append(
        f"- Bloque actual (ordinal {current_block.ordinal}, "
        f"página {current_block.page_number}, tipo {current_block.block_type}):"
    )
    lines.append(_indent(current_block.text, prefix="  "))
    return "\n".join(lines)


def _indent(text: str, *, prefix: str) -> str:
    if not text:
        return f"{prefix}(bloque vacío)"
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _assistant_message_with_tools(
    content: str,
    tool_calls: list[Any],
) -> dict[str, Any]:
    """Construye el mensaje `assistant` con tool_calls para el LLM."""
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments_json,
                },
            }
            for tc in tool_calls
        ],
    }


def _tool_result_message(*, tool_call_id: str, result: Any) -> dict[str, Any]:
    """Construye el mensaje `tool` con el resultado serializado."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }
