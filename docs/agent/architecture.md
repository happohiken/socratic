# Arquitectura del servidor (agentes)

`socratic-server/` — FastAPI + SQLite, `src-layout`.

## Estructura

```
socratic-server/
├── main.py                  # Entry point: create_app(settings) + uvicorn (reload=True)
├── pyproject.toml           # Deps: fastapi, uvicorn, pdfplumber, pydantic-settings,
│                            #       openai, txtai; dev: pytest, httpx, fpdf2; opt: pypdf
├── src/socratic/
│   ├── app.py               # create_app(storage_path, llm_client=None) -> FastAPI
│   ├── domain/models.py     # Document, ContentBlock, Study, Message (dataclasses)
│   ├── storage/database.py  # SQLite stdlib; DB dataclass; CRUD; init_db(); CASCADE
│   ├── document_processing/
│   │   ├── model.py         # ParsedDocument, DocumentNode, FontInfo, TocEntry, ListItem
│   │   ├── extractor.py     # parse_pdf(path, page_range=None) -> ParsedDocument
│   │   ├── classifier.py    # classify_node() -> (tipo, level)
│   │   ├── adapter.py       # parsed_to_document / parsed_to_content_blocks
│   │   └── formatters.py    # format_text / format_json (para inspect-pdf)
│   ├── llm/
│   │   ├── base.py          # LLMClient (Protocol), LLMResponse, ToolCall
│   │   └── openai_client.py # OpenAIClient (compatible con cualquier API OpenAI)
│   ├── retrieval/
│   │   ├── models.py        # RetrievedBlock, DocumentRetriever (Protocol), Context
│   │   ├── txtai_backend.py # TxtaiDocumentRetriever
│   │   └── service.py       # RetrievalService
│   ├── services/
│   │   └── navigation.py    # NavigationService (obtener/completar/retroceder bloque)
│   ├── orchestrator/
│   │   ├── registry.py      # @register_tool + ToolRegistry + esquemas desde anotaciones
│   │   ├── tools.py         # 4 tools + TurnContext
│   │   └── orchestrator.py  # Orchestrator + TurnResult
│   ├── config/settings.py   # Settings (Pydantic, prefijo SOCRATIC_)
│   └── api/
│       ├── documents.py     # POST/GET/DELETE /documents
│       ├── studies.py       # Estudios, mensajes, navegación
│       ├── ask.py           # POST /studies/{id}/ask (sin tools)
│       ├── interact.py      # POST /studies/{id}/interact (orquestador)
│       └── retrieval.py     # POST /documents/{id}/reindex y /search
├── tests/                   # test_document, test_study, test_ask, test_interact,
│                            # test_orchestrator, test_orchestrator_tools, test_registry,
│                            # test_retrieval, test_persistence, test_llm
└── data/                    # SQLite (socratic.db) + índice vectorial (retrieval/)
```

## Capas

1. **API** (`api/`) — REST, validación HTTP, serialización. Sin lógica de dominio.
2. **Servicios de aplicación** (`services/`, `retrieval/service.py`) — coordinan dominio, persistencia, parser, LLM. Reutilizables por REST y tools.
3. **Orquestador** (`orchestrator/`) — Turn conversacional, protocolo-agnóstico.
4. **Dominio** (`domain/`) — modelos puros. No sabe de persistencia ni LLM.
5. **Storage** (`storage/`) — SQLite stdlib, CRUD.
6. **PDF** (`document_processing/`) — `parse_pdf()` y adaptador a dominio.
7. **LLM** (`llm/`) — Protocol + implementación OpenAI-compatible.
8. **Config** (`config/`) — `Settings` con prefijo `SOCRATIC_`.

## `create_app`

`socratic/app.py:27`. Construye FastAPI y registra en `app.state`:
- `db` — `DB` (sqlite3.Connection envuelta).
- `llm` — `LLMClient` (por defecto `OpenAIClient` con settings).
- `retrieval` — `RetrievalService`.
- `navigation` — `NavigationService(db)`.
- `orchestrator` — `Orchestrator(db, llm, retrieval, navigation, ...)`.

La BD se inicializa al construir la app (no en lifespan) para que los
tests con `ASGITransport` tengan `app.state.db` sin disparar startup.

## Invariantes

- `Study.current_block_id` referencia `ContentBlock.id` (UUID), no ordinal.
- La posición avanza **solo** al confirmar completado.
- Toda mutación de estudio desde una tool pasa por `NavigationService`,
  nunca por `storage/` directo.
- SQLite es fuente de verdad; el índice txtai es reconstruible.
- Los tool calls **no** se persisten; solo mensajes user/assistant.

## Decisión: `check_same_thread=False`

Permite usar la misma conexión SQLite en hilos asíncronos de FastAPI.
Activado `PRAGMA journal_mode=WAL` y `PRAGMA foreign_keys=ON`.

## Detalles

- Dominio y persistencia: [persistence.md](persistence.md)
- Endpoints: [api.md](api.md)
- Orquestador: [orchestrator.md](orchestrator.md)
- RAG: [retrieval.md](retrieval.md)
- Configuración: [config.md](config.md)
