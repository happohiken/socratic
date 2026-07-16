# Orquestador conversacional

`socratic-server/src/socratic/orchestrator/` — Turn conversacional con
tool calling y **un único LLM por Turn**. Independiente del protocolo:
no importa FastAPI ni `starlette`. Recibe objetos de dominio y
devuelve la respuesta del asistente.

> Este documento describe el **estado implementado**. El plan previo
> original se conserva en el historial git (`docs/conversational-orchestrator-plan.md`
> hasta el commit anterior); aquí se refleja lo que existe en el
> código.

## Objetivo

Evolucionar Socratic desde comandos explícitos hacia un sistema
conversacional en el que el usuario habla en lenguaje natural y el LLM,
dentro del servidor, decide qué acciones invocar para satisfacer la
intención del usuario.

El usuario no debería distinguir entre "hacer una pregunta", "continuar
leyendo", "repetir un párrafo" o "volver atrás": todo se resuelve
mediante **tool calling** sobre mecanismos registrados por el servidor.

## Principios rectores

1. **Un único LLM por Turn.** No existe un segundo LLM de respuesta.
   Las tools nunca generan la respuesta al usuario; solo recuperan
   información, modifican el estado o devuelven datos estructurados.
   El LLM compone la respuesta final.
2. **Las tools representan operaciones del dominio o recuperaciones de
   información, no capacidades del LLM.** Las tools existen para
   acceder al mundo exterior o modificar el estado. El LLM ya sabe
   resumir, traducir o razonar; no hay tools para eso.
3. **El servidor es la única fuente de verdad** del estado de lectura
   y de la conversación.
4. **El LLM decide qué tool usar**; el servidor no clasifica
   intenciones con reglas, árboles ni palabras clave.
5. **El cliente no interpreta intención**: es la interfaz con el
   usuario. La ubicación de STT y TTS se decide en otro documento.
6. **Cada tool tiene un propósito concreto**, nunca un
   `execute(command)` genérico.
7. **Las tools no contienen lógica de negocio**: delegan en los
   servicios de aplicación ya existentes. Nunca acceden a la
   persistencia directamente.
8. **El orquestador es independiente del protocolo.** No conoce REST,
   HTTP ni FastAPI. Recibe objetos de dominio y devuelve una respuesta
   del asistente. Esto permite reutilizarlo desde CLI, REST, WebSocket,
   Android y tests sin tocarlo.
9. **Un único mecanismo de tool calling.** No hay categorías técnicas
   distintas de tools. Todas las tools —de dominio o de recuperación—
   utilizan exactamente el mismo registro, validación y ejecución. La
   diferencia entre categorías es únicamente **semántica**.
10. **Complejidad mínima**: no se introducen capas, módulos ni
    abstracciones sin un problema concreto que resolver.

## Concepto de Turn

Un `Turn` es la unidad de interacción completa entre el usuario y el
asistente. **No se persiste**; vive solo en memoria mientras se
ejecuta. Conceptualmente:

```
Turn
  ├── entrada del usuario (texto)
  ├── tool calls solicitados por el LLM (0..N)
  ├── resultados de esos tool calls (datos estructurados)
  └── respuesta final del asistente (texto)
```

El orquestador construye un Turn, lo ejecuta, persiste únicamente la
entrada del usuario y la respuesta final, y descarta el resto.

## Flujo de extremo a extremo

```
Entrada del usuario (texto)
  → Orquestador construye el contexto inicial del Turn:
      system prompt + estado + bloque actual + historial reciente + tools
  → LLM razona
  → ¿Solicita tools?
      Sí → orquestador valida argumentos y ejecuta
         → la tool devuelve datos estructurados
         → los datos se inyectan en el Turn
         → LLM razona de nuevo
      No → genera respuesta textual final
  → Orquestador persiste únicamente los mensajes user y assistant
  → Devuelve la respuesta final
```

## Módulos

### `registry.py`

Mecanismo único de registro de tools.

```python
@dataclass
class RegisteredTool:
    name: str
    description: str
    fn: Callable[..., Any]
    arg_model: type[BaseModel]
    schema: dict[str, Any]

    def execute(self, context: Any, arguments: dict[str, Any]) -> Any: ...

@dataclass
class ToolRegistry:
    _tools: dict[str, RegisteredTool]

    def register(self, name, description, fn) -> RegisteredTool: ...
    def get(self, name) -> RegisteredTool: ...
    def list(self) -> list[RegisteredTool]: ...
    def has(self, name) -> bool: ...
    def openai_schemas(self) -> list[dict[str, Any]]: ...
    def execute(self, name, context, arguments) -> Any: ...

class ToolError(Exception): ...

def serialize_result(result: Any) -> Any: ...

default_registry = ToolRegistry()

def register_tool(name, description, *, registry=None): ...
```

- El decorador `@register_tool(name, description)` registra la función
  en `default_registry` (o en el registro pasado).
- El esquema de argumentos se deriva de las anotaciones de tipo
  (excluyendo el parámetro `context`); validación con Pydantic en
  runtime.
- `serialize_result` convierte el resultado a JSON-serializable:
  - `None` → `None`.
  - `BaseModel` → `model_dump()`.
  - `dict`/`list`/`int`/`float`/`bool` → tal cual.
  - `str` → `{"text": ...}`.
  - Otros con `__dict__` → `vars()`.
  - Resto → `{"text": str(result)}`.
- `openai_schemas()` devuelve las tools en formato
  `{"type": "function", "function": {name, description, parameters}}`
  para el parámetro `tools` de la API.

### `tools.py`

Las 4 tools iniciales + `TurnContext`.

```python
@dataclass
class TurnContext:
    study: Study
    current_block: ContentBlock | None
    db: DB
    retrieval: RetrievalService
    navigation: NavigationService
```

Es **mutable** dentro de un Turn: las tools de dominio que avanzan la
posición actualizan `study` y `current_block` para que las siguientes
tools del mismo Turn vean el estado actualizado.

#### Tools de dominio (delegan en `NavigationService`)

- `get_current_block(context) -> dict | None` — devuelve el bloque
  actual serializado.
- `complete_current_block(context) -> dict | None` — marca completado y
  avanza; actualiza `context.current_block`; devuelve el nuevo bloque.
- `previous_block(context) -> dict` — retrocede; actualiza
  `context.current_block`; devuelve el nuevo bloque.

#### Tools de recuperación (delegan en `RetrievalService`)

- `retrieve_document_context(context, query: str) -> list[dict]` —
  invoca `retrieval.retrieve_context(study, current_block, query)`;
  devuelve los `retrieved_blocks` serializados (block_id, document_id,
  ordinal, page_number, text, score). **No** modifica estado, **no**
  persiste, **no** construye narrativa, **no** llama al LLM.

Todas las tools reciben `TurnContext` (no visible para el LLM) y
devuelven **datos estructurados**.

> Importar `socratic.orchestrator` registra las 4 tools en
> `default_registry` como efecto lateral (ver `__init__.py`).

### `orchestrator.py`

Fachada `Orchestrator` y `TurnResult`.

```python
@dataclass
class TurnResult:
    answer: str
    study_id: str
    message_id: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

class Orchestrator:
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
    ) -> None: ...

    def interact(self, study: Study, user_input: str) -> TurnResult: ...
```

#### `interact(study, user_input) -> TurnResult`

1. Cargar `current_block` y `document` del estudio (helpers
   `_load_current_block`, `_load_document`).
2. Construir `TurnContext`.
3. Construir mensajes iniciales con `_build_initial_messages`:
   - System prompt: `SYSTEM_PROMPT_TEMPLATE` + `_format_state(...)`
     (documento, bloque actual con ordinal/página/tipo/texto indentado,
     o aviso de fin de documento).
   - Historial: últimos `history_messages` mensajes del estudio (role +
     content).
   - Entrada del usuario.
4. Bucle `_run_tool_loop`:
   - `previous_calls: list[tuple[name, arguments_json]]` para detectar
     repetición sin progreso.
   - Por cada iteración (hasta `max_tool_iterations`):
     - `llm.complete_with_tools(messages, tools=openai_schemas())`.
     - Si `not response.has_tool_calls` → devolver `response.content`.
     - Añadir mensaje `assistant` con `tool_calls` (vía
       `_assistant_message_with_tools`).
     - Por cada `ToolCall`:
       - Si `(name, arguments_json)` ya está en `previous_calls` →
         inyectar `{"error": "Tool ya invocada con los mismos argumentos."}`
         como mensaje `tool` y `logger.warning`.
       - Si no, ejecutar con `_execute_tool_safe` (captura errores de
         JSON, `ToolError` y excepciones genéricas), añadir a
         `previous_calls`, loggear en `tool_calls_log` e inyectar
         resultado como mensaje `tool` (`_tool_result_message`).
   - Si se agotan iteraciones → llamada final al LLM **sin** tools
     (`tools=None`); `logger.warning` con el máximo.
5. Persistir user + assistant con `_persist_messages` (asocia
   `content_block_id` al bloque actual del Turn; commitea).
6. Devolver `TurnResult(answer, study_id, message_id, tool_calls)`.

#### System prompt (`SYSTEM_PROMPT_TEMPLATE`)

```
Eres un profesor particular que guía al estudiante en la lectura
secuencial de un documento. El estudiante lee bloques de texto uno a
uno y puede pedirte continuar, repetir, retroceder o hacer preguntas
sobre el contenido.

Reglas:
- Usa las tools disponibles para consultar o modificar el estado de
  lectura. No inventes tools.
- No repitas la misma tool con los mismos argumentos si no hubo progreso.
- Usa `retrieve_document_context` solo cuando la pregunta requiera
  contexto más allá del bloque actual. Para navegar (continuar,
  repetir, retroceder) no la necesitas.
- Responde de forma concisa y relacionada con el contenido del documento.
- No divagues; mantén el foco en el texto que el estudiante está leyendo.
```

`_format_state` añade un bloque "Estado actual del estudio" con
documento y bloque actual (texto indentado), o aviso de fin de
documento con sugerencia de `previous_block`.

## Casos representativos

- **Pregunta sobre el bloque actual o sobre el documento**: el LLM
  llama a `retrieve_document_context(query)` y responde con los
  fragmentos recuperados. El estado no cambia.
- **Petición de continuar**: el LLM llama a
  `complete_current_block()`. La tool avanza la posición y devuelve el
  nuevo bloque. El LLM puede relatar su texto en la respuesta final.
  Sin RAG.
- **Petición de repetir**: el LLM llama a `get_current_block()` y
  devuelve su texto. La posición no cambia. Sin RAG.
- **Petición de volver atrás**: el LLM llama a `previous_block()`. La
  tool retrocede y devuelve el nuevo bloque actual. Sin RAG.
- **Petición combinada ("explica esto y luego continúa")**: el LLM
  llama a `retrieve_document_context(...)` y responde la pregunta; a
  continuación llama a `complete_current_block()` para avanzar. Todo
  en el mismo Turn.
- **Intervención no comprensible**: el LLM no solicita tools y pide
  reformulación. El estado no se altera.

## Límites del Turn

- Máximo de iteraciones del bucle: `orchestrator_max_tool_iterations`
  (default `5`).
- Detección de bucle infinito: misma `(name, arguments_json)` repetida
  sin progreso → se inyecta error y se continúa el bucle (no se aborta
  inmediatamente).
- Timeout global heredado del LLM (`llm_timeout_seconds`, default
  `120`).
- Historial: `orchestrator_history_messages` (default `10`).

## Persistencia

**No se modifica el modelo de persistencia en esta versión.** Solo se
persisten los mensajes `user` y `assistant` finales del Turn, igual que
`/ask`. Los `tool_calls`, sus argumentos y sus resultados viven solo
en memoria durante el Turn y se registran en `TurnResult.tool_calls`
para depuración.

`_persist_messages` asocia los dos mensajes al `current_block` que
estaba activo al **inicio** del Turn (no al final, que puede haber
cambiado por una tool de dominio).

## Relación con el sistema

### Componentes reutilizados sin cambios

- `domain/models.py`, `storage/database.py`,
  `retrieval/service.py`, `retrieval/txtai_backend.py`,
  `document_processing/`, `api/documents.py`, `api/retrieval.py`,
  `config/settings.py`.

### Componentes nuevos

- `orchestrator/registry.py`, `orchestrator/tools.py`,
  `orchestrator/orchestrator.py`, `services/navigation.py`,
  `api/interact.py`.

### Componentes refactorizados

- `llm/base.py` y `llm/openai_client.py` amplían la interfaz para
  aceptar `tools` y devolver `tool_calls`.
- `api/studies.py` delega en `NavigationService` (lógica extraída).
- `api/ask.py` se mantiene durante la transición con su composición
  imperativa del prompt.

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_ORCHESTRATOR_MAX_TOOL_ITERATIONS` | `5` | Máx. iteraciones del bucle por Turn |
| `SOCRATIC_ORCHESTRATOR_HISTORY_MESSAGES` | `10` | Mensajes de historial reciente en el contexto |

## Criterios de aceptación (verificados)

- Un usuario puede hacer una pregunta sobre el bloque actual y recibir
  respuesta sin invocar ningún comando explícito. ✓ (`/interact`)
- Un usuario puede pedir continuar, repetir o retroceder con lenguaje
  natural; el LLM invoca la tool adecuada. ✓
- Un usuario puede encadenar dos acciones en un único Turn. ✓
- El estado del estudio se actualiza exclusivamente a través de tools
  de dominio, y nunca de forma inconsistente con el flujo REST. ✓
- El historial de mensajes user/assistant persiste tras reiniciar el
  servidor. ✓ (test_persistence)
- El orquestador respeta el límite máximo de iteraciones y detecta
  bucles infinitos. ✓
- Las tools se registran mediante decorador, sin escribir esquemas
  JSON a mano. ✓
- Las tools no importan de `storage/`: delegan en servicios. ✓
- Todas las tools utilizan el mismo mecanismo de registro, validación y
  ejecución. ✓
- El orquestador no importa de FastAPI ni de `starlette`. ✓
- `retrieve_document_context` no modifica el estado, no persiste, no
  construye narrativa y no llama al LLM. ✓
- Solo se persisten mensajes user y assistant; los tool calls no se
  persisten. ✓

## Decisiones pendientes / fuera de alcance

- **CLI textual**: la CLI no expone `/interact` todavía (solo `/ask`).
- **Streaming**: aplazado según `AGENTS.md`.
- **Persistencia detallada de tool calls**: aplazada.
- **Arquitectura de audio y ubicación de STT/TTS**: aplazada a otro
  documento.
- **Operaciones multidocumento** (`list_documents`, `switch_study`):
  aplazadas hasta versión multidocumento.
