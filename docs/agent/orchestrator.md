# Orquestador conversacional (agentes)

`socratic-server/src/socratic/orchestrator/` — Turn conversacional con
tool calling y **un único LLM por Turn**. Independiente del protocolo:
no importa FastAPI ni `starlette`.

## Concepto de Turn

Unidad transitoria de interacción. **No se persiste**. Contiene:

```
Turn
  ├── entrada del usuario (texto)
  ├── tool calls solicitados por el LLM (0..N)
  ├── resultados de esos tool calls (datos estructurados)
  └── respuesta final del asistente (texto)
```

Solo se persisten los mensajes `user` y `assistant` finales. Los tool
calls viven en memoria y se registran en `TurnResult.tool_calls` para
depuración.

## Módulos

- **`registry.py`** — `ToolRegistry` (diccionario central), decorador
  `@register_tool(name, description)`, `RegisteredTool`,
  `serialize_result()`, `ToolError`. El esquema de argumentos se deriva
  de las anotaciones de tipo; validación con Pydantic en runtime. El
  primer parámetro debe llamarse `context` y no es visible para el LLM.
- **`tools.py`** — las 4 tools + `TurnContext`. Importar el paquete
  `socratic.orchestrator` registra las tools como efecto lateral.
- **`orchestrator.py`** — fachada `Orchestrator` + `TurnResult`.

## `TurnContext` (inmutable dentro de un Turn salvo `study`/`current_block`)

```python
@dataclass
class TurnContext:
    study: Study
    current_block: ContentBlock | None
    db: DB
    retrieval: RetrievalService
    navigation: NavigationService
```

Las tools de dominio que avanzan la posición actualizan `study` y
`current_block` para que las siguientes tools del mismo Turn vean el
estado actualizado.

## Tools registradas (mismo mecanismo técnico)

| Tool | Categoría semántica | Delega en | Modifica estado |
|---|---|---|---|
| `get_current_block()` | Dominio | `TurnContext.current_block` | No |
| `complete_current_block()` | Dominio | `NavigationService.complete_current_block` | Sí |
| `previous_block()` | Dominio | `NavigationService.previous_block` | Sí |
| `retrieve_document_context(query: str)` | Recuperación | `RetrievalService.retrieve_context` | No |

Todas devuelven **datos estructurados** (dict/list/None). El LLM
compone la respuesta final.

## Bucle (`Orchestrator.interact`)

1. Cargar `current_block` y `document` del estudio.
2. Construir `TurnContext`.
3. Construir mensajes iniciales: system prompt (con estado del estudio
   inline) + historial reciente (últimos N mensajes) + entrada del
   usuario.
4. Bucle hasta `max_tool_iterations`:
   - `llm.complete_with_tools(messages, tools)`.
   - Si `response.has_tool_calls` es False → respuesta final, salir.
   - Si hay tool calls: añadir mensaje `assistant` con `tool_calls`;
     ejecutar cada tool; añadir mensaje `tool` con resultado
     serializado.
   - Detección de bucle: misma `(name, arguments_json)` repetida sin
     progreso → se inyecta `{"error": "Tool ya invocada..."}` y se
     continúa.
5. Si se agotan iteraciones → llamada final al LLM **sin** tools.
6. Persistir user + assistant (no tool calls) y commitear.
7. Devolver `TurnResult(answer, study_id, message_id, tool_calls)`.

## Restricciones de las tools

- No contienen lógica de negocio: delegan en servicios.
- No acceden a `storage/` directo.
- No llaman al LLM.
- No construyen narrativa al usuario.
- `retrieve_document_context` no persiste, no modifica estado, no
  responde; solo devuelve fragmentos.

## Serialización de resultados

`serialize_result(result)`:
- `None` → `None`
- Pydantic BaseModel → `model_dump()`
- `dict`/`list`/`int`/`float`/`bool` → tal cual
- `str` → `{"text": ...}`
- Otros con `__dict__` → `vars()`
- Resto → `{"text": str(result)}`

## Esquema OpenAI

`ToolRegistry.openai_schemas()` devuelve las tools en formato
`{"type": "function", "function": {name, description, parameters}}`
para el parámetro `tools` de la API.

## Configuración

- `orchestrator_max_tool_iterations` (default `5`) — límite del bucle.
- `orchestrator_history_messages` (default `10`) — histórico reciente
  incluido en el contexto inicial.

## System prompt

Definido en `orchestrator.py:SYSTEM_PROMPT_TEMPLATE`. Describe el rol
(profesor particular), reglas (no inventar tools, no repetir tool sin
progreso, usar `retrieve_document_context` solo cuando haga falta) y se
concatena con `_format_state()` que añade documento, bloque actual
(ordinal, página, tipo, texto indentado) o aviso de fin de documento.
