# Arquitectura del servidor

`socratic-server/` — servidor FastAPI con persistencia SQLite,
siguiendo `src-layout`.

## Estructura

```
socratic-server/
├── main.py                  # Entry point: create_app(settings) + uvicorn (reload=True)
├── pyproject.toml           # Deps: fastapi, uvicorn, pdfplumber, pydantic, pydantic-settings,
│                            #       python-multipart, openai, txtai
│                            # Dev: pytest, pytest-asyncio, httpx, fpdf2
│                            # Optional: pypdf (TOC)
├── src/socratic/
│   ├── app.py               # create_app(storage_path, llm_client=None) — factory FastAPI
│   ├── domain/
│   │   ├── models.py        # Document, ContentBlock, Study, Message (dataclasses)
│   │   └── __init__.py
│   ├── storage/
│   │   ├── database.py      # DB dataclass, init_db, CRUD, CASCADE
│   │   └── __init__.py
│   ├── document_processing/
│   │   ├── model.py         # ParsedDocument, DocumentNode, FontInfo, TocEntry, ListItem
│   │   ├── extractor.py     # parse_pdf(path, page_range=None) -> ParsedDocument
│   │   ├── classifier.py    # classify_node(text, font) -> (tipo, level)
│   │   ├── adapter.py       # parsed_to_document / parsed_to_content_blocks
│   │   ├── formatters.py    # format_text / format_json (inspect-pdf)
│   │   └── __init__.py
│   ├── llm/
│   │   ├── base.py          # LLMClient (Protocol), LLMResponse, ToolCall
│   │   ├── openai_client.py # OpenAIClient (compatible con cualquier API OpenAI)
│   │   └── __init__.py
│   ├── retrieval/
│   │   ├── models.py        # RetrievedBlock, DocumentRetriever (Protocol), Context
│   │   ├── txtai_backend.py # TxtaiDocumentRetriever
│   │   ├── service.py       # RetrievalService
│   │   └── __init__.py
│   ├── services/
│   │   ├── navigation.py    # NavigationService (compartido por REST y tools)
│   │   └── __init__.py
│   ├── orchestrator/
│   │   ├── registry.py      # @register_tool + ToolRegistry + esquemas desde anotaciones
│   │   ├── tools.py         # 4 tools + TurnContext
│   │   ├── orchestrator.py  # Orchestrator + TurnResult
│   │   └── __init__.py
│   ├── api/
│   │   ├── documents.py     # POST/GET/DELETE /documents
│   │   ├── studies.py       # Estudios, mensajes, navegación
│   │   ├── ask.py           # POST /studies/{id}/ask (sin tools)
│   │   ├── interact.py      # POST /studies/{id}/interact (orquestador)
│   │   ├── retrieval.py     # POST /documents/{id}/reindex y /search
│   │   └── __init__.py
│   ├── config/
│   │   ├── settings.py      # Pydantic BaseSettings, prefijo SOCRATIC_
│   │   └── __init__.py
│   └── __init__.py
├── tests/                   # Unitarios e integración (ver getting-started.md)
├── data/                    # SQLite (socratic.db) + índice vectorial (retrieval/)
└── .gitignore
```

## Layout `src`

El paquete vive dentro de `src/` (estándar en proyectos Python
profesionales):

- Evita que tests y herramientas usen el paquete sin instalar.
- Permite múltiples versiones del mismo paquete en el mismo entorno.
- `pyproject.toml` indica `where = ["src"]` para que setuptools lo
  encuentre.

## Componentes

### `main.py`

Entry point. Crea `settings = Settings()`, `app = create_app(settings.storage_path)`
a nivel de módulo (necesario para `uvicorn.run("main:app", reload=True)`).
Arranca uvicorn con `host` y `port` de settings y `reload=True`.

### `socratic/app.py`

Factory `create_app(storage_path, llm_client=None, **kwargs) -> FastAPI`.

- Inicializa la BD al construir la app (no en lifespan startup) para
  que `app.state.db` esté disponible en tests con `ASGITransport`.
- Lifespan: solo cierra la conexión en shutdown.
- Crea y registra en `app.state`:
  - `db` — instancia `DB`.
  - `llm` — `llm_client` o `OpenAIClient` con settings.
  - `retrieval` — `RetrievalService(retriever, db)` con
    `TxtaiDocumentRetriever` cargado desde disco.
  - `navigation` — `NavigationService(db)`.
  - `orchestrator` — `Orchestrator(db, llm, retrieval, navigation, ...)`
    con `max_tool_iterations` e `history_messages` de settings.
- CORS middleware con `allow_origins=["*"]`.
- Incluye routers: `documents`, `studies`, `ask`, `interact`,
  `retrieval`.

Permite a los tests simular reinicios creando apps nuevas sobre la
misma BD.

### `socratic/domain/models.py`

Modelos de dominio (dataclasses con UUID y `datetime` UTC):

- **`Document`**: `id`, `filename`, `page_count`, `block_count`,
  `format`, `metadata: dict`, `created_at`, `updated_at`. Método
  `touch()`.
- **`ContentBlock`**: `id`, `document_id`, `ordinal`, `text`,
  `page_number`, `block_type` (`paragraph` | `heading` | `list` |
  `unknown`), `metadata: dict` (bbox, font, level).
- **`Study`**: `id`, `document_id`, `current_block_id`,
  `last_completed_block_id`, `created_at`, `updated_at`. Método
  `touch()`.
- **`Message`**: `id`, `study_id`, `content_block_id` (opcional),
  `role` (`user` | `assistant`), `content`, `created_at`.

### `socratic/storage/database.py`

Conexión SQLite via stdlib `sqlite3` con `check_same_thread=False`.
`DB` es un dataclass con `conn` y `path`.

- `init_db(path) -> DB`: crea el directorio padre, activa
  `PRAGMA journal_mode=WAL` y `PRAGMA foreign_keys=ON`, crea las
  tablas si no existen.
- Tablas: `documents`, `content_blocks`, `studies`, `messages`.
- Restricciones: `content_blocks.document_id` → documents CASCADE,
  `UNIQUE(document_id, ordinal)`; `studies.document_id` → documents
  CASCADE; `messages.study_id` → studies CASCADE.
- CRUD completo por entidad. `delete_document` devuelve `bool` (vía
  CASCADE).
- `metadata` se serializa como JSON text.

### `socratic/document_processing/`

Parser documental compartido entre `socratic inspect-pdf` y
`POST /documents`.

- **`model.py`** — `ParsedDocument` (con `title`, `toc`, `nodes`),
  `DocumentNode` (con `node_type`, `text`, `page_number`, `ordinal`,
  `level`, `bbox`, `font`, `list_items`, `is_ordered`),
  `FontInfo` (name, size, bold, italic), `TocEntry`, `ListItem`.
- **`extractor.py`** — `parse_pdf(path, page_range=None) -> ParsedDocument`.
  Usa `pdfplumber` para extraer texto con info de fuentes; fusiona
  líneas en párrafos; detecta y elimina cabeceras/pies repetidos;
  clasifica nodos; construye `DocumentNode` ordenados por lectura.
  Opcionalmente carga TOC con `pypdf` si está instalado.
- **`classifier.py`** — `classify_node(text, font) -> (tipo, level)`.
  Tipos: `heading` (bold o size≥14 y texto corto), `paragraph`,
  `list_item`. `_LIST_PREFIXES` reconoce viñetas Unicode y patrones
  como `1.`, `a)`, `IV:`.
- **`adapter.py`** — `parsed_to_document(parsed, filename) -> Document`
  y `parsed_to_content_blocks(document_id, parsed) -> list[ContentBlock]`.
  Conserva `bbox`, `font` y `level` en `ContentBlock.metadata`. Fusiona
  `list_item` y `list` en `block_type="list"`.
- **`formatters.py`** — `format_text(doc)` y `format_json(doc)` para
  `inspect-pdf`.

### `socratic/llm/`

- **`base.py`** — Protocolo `LLMClient`:
  - `complete(messages, **kwargs) -> str` — sin tools (usado por `/ask`).
  - `complete_with_tools(messages, tools=None, *, tool_choice=None, **kwargs) -> LLMResponse`
    — con tools (usado por el orquestador).
  - `LLMResponse(content, tool_calls)` con `has_tool_calls`.
  - `ToolCall(id, name, arguments_json)` (frozen).
- **`openai_client.py`** — `OpenAIClient` usando el SDK oficial
  `openai`. Compatible con cualquier API OpenAI-compatible (LiteLLM,
  Ollama, vLLM, etc.). Implementa ambos métodos del protocolo. El
  cliente se construye lazy (`_synced_client`). `api_key` cae a
  `OPENAI_API_KEY` si no se pasa.

### `socratic/retrieval/`

Ver [retrieval.md](retrieval.md) para detalle.

- **`models.py`** — `RetrievedBlock` (frozen), `DocumentRetriever`
  (Protocol con `index_document` y `search`), `Context` (combina
  `local_blocks` y `retrieved_blocks`).
- **`txtai_backend.py`** — `TxtaiDocumentRetriever`. Indexa con
  `upsert` (seguro para reindexación). Busca con SQL `similar()` y
  filtrado por `tags` (document_id). Solo indexa bloques con texto
  útil (descarta vacíos, solo espacios, solo puntuación).
- **`service.py`** — `RetrievalService`:
  - `retrieve_context(study, current_block, question, limit=5)`:
    combina bloques locales (actual + 2 anteriores + 2 siguientes) con
    recuperados (deduplicados por `block_id`).
  - `reindex_document(document_id) -> int`.
  - `search(document_id, query, limit) -> list[RetrievedBlock]`.

### `socratic/services/navigation.py`

`NavigationService(db)` extraído de la lógica que antes vivía inline en
`api/studies.py`. Centraliza las operaciones de navegación de lectura
(obtener, completar y retroceder bloque) para que sean reutilizadas
**tanto por los endpoints REST como por las tools del orquestador**,
evitando duplicar lógica y garantizando que las tools no toquen la
persistencia directamente. Persiste los cambios de estado del estudio
en cada llamada (con `commit`).

- `get_current_block(study) -> ContentBlock | None`
- `complete_block(study, block_id) -> ContentBlock | None`
- `complete_current_block(study)` — comodín.
- `previous_block(study) -> ContentBlock`
- `NavigationError` para operaciones inválidas.

### `socratic/orchestrator/`

Orquestador conversacional basado en tool calling con un único LLM por
Turn. Independiente del protocolo (no conoce REST, HTTP ni FastAPI);
recibe objetos de dominio y devuelve la respuesta del asistente. Tres
módulos:

- **`registry.py`** — mecanismo único de registro de tools. El
  decorador `@register_tool(name, description)` registra una función
  en un `ToolRegistry` central. El esquema de argumentos se deriva de
  las anotaciones de tipo (excluyendo el parámetro `context`); la
  validación se realiza con Pydantic en runtime; el resultado se
  serializa a JSON (`dict` tal cual, modelo Pydantic con
  `model_dump()`, `str` envuelto en `{"text": ...}`).
- **`tools.py`** — implementaciones de las 4 tools iniciales, en dos
  categorías semánticas que comparten el mismo mecanismo técnico:
  - **Tools de dominio** (delegan en `NavigationService`):
    `get_current_block()`, `complete_current_block()`, `previous_block()`.
  - **Tools de recuperación** (delegan en `RetrievalService` sin
    modificar estado): `retrieve_document_context(query)`.
  - Todas reciben un `TurnContext` (study, current_block, db,
    retrieval, navigation) inyectado por el orquestador, no visible
    para el LLM, y devuelven **datos estructurados** (nunca narrativa).
- **`orchestrator.py`** — fachada `Orchestrator`. Construye el
  contexto inicial del Turn (system prompt + estado del estudio +
  bloque actual + historial reciente + entrada del usuario), ejecuta
  el bucle de tool calling, inyecta resultados como mensajes `tool`,
  persiste únicamente los mensajes `user`/`assistant` finales (no los
  tool calls) y devuelve un `TurnResult`. Aplica límites
  configurables: máximo de iteraciones y detección de bucle infinito
  (misma tool con mismos argumentos repetida sin progreso).

Ver [orchestrator.md](orchestrator.md) para el flujo completo.

### `socratic/api/`

Endpoints REST. Ver [api.md](api.md) para referencia completa.

- **`documents.py`** — `POST /documents` (subida y extracción, usa
  `parse_pdf()` compartido con `inspect-pdf`), `DELETE /documents/{id}`
  (cascada), `GET /documents`, `GET /documents/{id}`.
- **`studies.py`** — `POST /studies`, `GET /studies`, `GET /studies/{id}`,
  `GET /studies/{id}/current-block`, `POST /studies/{id}/blocks/{blockId}/complete`,
  `POST /studies/{id}/previous-block`, `GET /studies/{id}/messages`,
  `POST /studies/{id}/messages`. Los de navegación delegan en
  `NavigationService`.
- **`ask.py`** — `POST /studies/{id}/ask` que envía una pregunta al
  LLM sin tools. Construye un contexto ampliado: system → bloque
  actual → 2 anteriores → 2 siguientes → RAG → historial (últimos 4)
  → pregunta. Inserta mensajes `assistant` ficticios para forzar
  alternancia. La respuesta se guarda en historial sin avanzar la
  posición. Se mantiene durante la transición al orquestador
  conversacional para no romper la CLI textual existente.
- **`interact.py`** — `POST /studies/{id}/interact` que inicia un Turn
  conversacional. Capa fina HTTP ↔ orquestador: valida la entrada,
  obtiene el estudio y delega en
  `app.state.orchestrator.interact(study, user_input)`. Toda la lógica
  de tool calling, composición de contexto y persistencia vive en el
  orquestador (independiente del protocolo).
- **`retrieval.py`** — `POST /documents/{id}/reindex` (202 Accepted) y
  `POST /documents/{id}/search` (diagnóstico con score).

### `socratic/config/settings.py`

Configuración externalizada mediante variables de entorno con prefijo
`SOCRATIC_` (Pydantic BaseSettings). Lee `.env` si existe. Ver
[config.md](config.md) para la tabla completa.

## Recuperación documental

El servidor indexa el documento completo para responder preguntas sobre
cualquier parte del texto, no solo el bloque actual.

```
SQLite (fuente de verdad) ←→ txtai (índice reconstruible)
```

- **Modelo de embeddings**: `sentence-transformers/all-MiniLM-L6-v2`
  (multilingüe, ~23 MB, Apache 2.0, default de txtai).
- **Persistencia del índice**: `data/retrieval/` (excluido de Git).
  `embeddings.save(path)` / `embeddings.load(path)`.
- **Indexación**: `socratic reindex` (todos) o `socratic reindex <id>`
  (uno). Usa `upsert` para ser segura ante reindexaciones.
- **Búsqueda**: SQL con `similar()` y filtrado por `tags`
  (document_id).

Ver [retrieval.md](retrieval.md) para más detalle.

## Cliente CLI

`socratic-cli/` — cliente Python que consume la API pública REST.
Thin view: solo envía comandos y muestra respuestas. El servidor es la
fuente de verdad.

```
socratic-cli/
├── socratic_cli/
│   ├── __init__.py
│   ├── __main__.py          # python -m socratic_cli
│   ├── client.py            # SocraticClient (httpx sync) + SocraticAPIError
│   ├── main.py              # argparse + comandos + cmd_config_import_opencode
│   └── inspect_pdf.py       # socratic inspect-pdf (usa parse_pdf del server)
├── tests/                   # Integración con servidor real
├── pyproject.toml           # Entry point: socratic = socratic_cli.main:main
└── README.md
```

Comandos: `upload`, `documents`, `document`, `delete`, `create-study`,
`studies`, `study`, `current-block`, `complete-block`, `next-block`,
`previous-block`, `messages`, `message`, `ask`, `reindex`,
`search-document`, `inspect-pdf`, `config import-opencode`.

> **Pendiente**: la CLI no expone `/interact` todavía.

URL configurable con `--url` o `SOCRATIC_URL`
(default `http://127.0.0.1:8885`).

## Despliegue

```bash
cd socratic-server
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m main
```

- Puerto por defecto: `8885`.
- Base de datos por defecto: `socratic-server/data/socratic.db`.
- Índice vectorial: `socratic-server/data/retrieval/`.

```bash
cd socratic-cli
.venv/bin/pip install -e .
.venv/bin/socratic --help
```

Para producción systemd, generar variables con
`socratic config import-opencode --print-env` (ver
[config.md](config.md)). **Atención**: la salida puede contener
secretos.
