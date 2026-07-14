# Arquitectura del Servidor

`socratic-server/` — servidor FastAPI con persistencia SQLite, siguiendo `src-layout`.

## Estructura

```
socratic-server/
├── src/socratic/            # Paquete principal (src-layout)
│   ├── domain/              # Modelos de dominio
│   │   ├── models.py        # Document, ContentBlock, Study, Message
│   │   └── __init__.py
│   ├── storage/             # Capa de persistencia
│   │   ├── database.py      # Conexión SQLite, CRUD
│   │   └── __init__.py
│   ├── pdf/                 # Procesamiento legacy (pendiente de eliminar)
│   │   ├── parser.py        # Extracción antigua por líneas -- ya no usada por la API
│   │   └── __init__.py
│   ├── document_processing/ # Parser documental compartido
│   │   ├── extractor.py     # parse_pdf() -- fusión de líneas, detección cabeceras/pies
│   │   ├── adapter.py       # ParsedDocument -> Document + ContentBlock
│   │   ├── classifier.py    # Clasificación de nodos (heading, paragraph, list_item)
│   │   ├── formatters.py    # Formato texto/JSON para inspect-pdf
│   │   └── __init__.py
│   ├── llm/                 # Interfaz y cliente LLM
│   │   ├── base.py          # LLMClient (Protocol)
│   │   ├── openai_client.py # OpenAIClient (implementación OpenAI-compatible)
│   │   └── __init__.py
│   ├── retrieval/           # Indexación y recuperación documental (txtai)
│   │   ├── models.py        # RetrievedBlock, DocumentRetriever (Protocol), Context
│   │   ├── txtai_backend.py # TxtaiDocumentRetriever
│   │   ├── service.py       # RetrievalService
│   │   └── __init__.py
│   ├── api/                 # Endpoints REST
│   │   ├── documents.py     # POST/GET/DELETE /documents
│   │   ├── studies.py       # Endpoints de estudios y mensajes
│   │   ├── ask.py           # POST /studies/{id}/ask (pregunta contextual)
│   │   ├── retrieval.py     # POST /documents/{id}/reindex y /search
│   │   └── __init__.py
│   ├── config/              # Configuración
│   │   ├── settings.py      # Pydantic BaseSettings
│   │   └── __init__.py
│   ├── app.py               # create_app(storage_path) — factory de FastAPI
│   └── __init__.py
├── main.py                  # Entry point: crea app con settings y arranca uvicorn
├── tests/                   # Tests unitarios e integración
│   ├── test_document.py     # Tests de documentos
│   ├── test_study.py        # Tests de estudios y mensajes
│   ├── test_ask.py          # Tests del endpoint ask
│   ├── test_retrieval.py    # Tests de indexación y recuperación
│   ├── test_persistence.py  # Tests de reinicio y recuperación persistente
│   ├── test_llm.py          # Tests del cliente LLM (stub)
│   └── __init__.py
├── data/                    # Base de datos SQLite (socratic.db) + índice vectorial
├── pyproject.toml           # Dependencias y configuración de paquete
└── .gitignore
```

## Layout `src`

El paquete vive dentro de `src/` (estándar en proyectos Python profesionales):

- Evita que tests y herramientas usen el paquete sin instalar.
- Permite múltiples versiones del mismo paquete en el mismo entorno.
- `pyproject.toml` indica `where = ["src"]` para que setuptools lo encuentre.

## Componentes

### `main.py`
Entry point. Crea la app global con `create_app(settings.storage_path)` y arranca uvicorn. No contiene lógica; delega en `socratic.app.create_app`.

### `socratic/app.py`
Factory `create_app(storage_path) -> FastAPI`. Inicializa la BD al construir la app (para que `app.state.db` esté disponible sin depender del lifespan startup, útil en tests con ASGITransport) y la cierra en el shutdown. Crea `TxtaiDocumentRetriever` y `RetrievalService` en `app.state.retrieval`. Permite a los tests simular reinicios creando apps nuevas sobre la misma BD.

### `socratic/domain/models.py`
Modelos de dominio:
- `Document`: id, filename, page_count, block_count, format, created_at, updated_at
- `ContentBlock`: id, document_id, ordinal, text, page_number, block_type, metadata
- `Study`: id, document_id, current_block_id, last_completed_block_id, created_at, updated_at
- `Message`: id, study_id, content_block_id, role, content, created_at

### `socratic/storage/database.py`
Conexión SQLite via stdlib `sqlite3` con `check_same_thread=False` para soporte multi-hilo. CRUD para Document, ContentBlock, Study y Message. Tablas: documents, content_blocks, studies, messages. Eliminación en cascada mediante `ON DELETE CASCADE` en las restricciones foreign key.

### `socratic/document_processing/extractor.py`
Parser documental principal. Compartido entre `socratic inspect-pdf` y `POST /documents`. Usa `pdfplumber` para extraer texto con información de fuentes, fusiona líneas en párrafos, detecta y elimina cabeceras/pies repetidos, clasifica nodos (heading, paragraph, list_item) y devuelve un `ParsedDocument` con nodos ordenados por lectura.

### `socratic/document_processing/adapter.py`
Adaptador que convierte `ParsedDocument` en modelos de dominio persistentes (`Document` + `list[ContentBlock]`). Conserva metadatos (bbox, font, level) en `ContentBlock.metadata`.

### `socratic/document_processing/classifier.py`
Clasificación de nodos basada en fuente y texto: headings (bold), list items (prefijos), párrafos.

### `socratic/document_processing/formatters.py`
Formateo de `ParsedDocument` a texto legible o JSON para `inspect-pdf`.

### `socratic/pdf/parser.py` (legacy)
Extracción antigua por líneas con tolerancia Y de 5px. Ya no es usada por la API. Pendiente de eliminación.

### `socratic/llm/base.py`
Protocolo `LLMClient` con un método `complete(messages) -> str`. Abstracción mínima que permite cambiar de proveedor sin tocar la lógica de dominio.

### `socratic/llm/openai_client.py`
Implementación `OpenAIClient` usando el SDK oficial de OpenAI. Compatible con cualquier API OpenAI-compatible (LiteLLM, Ollama, vLLM, etc.).

### `socratic/retrieval/models.py`
Modelos de recuperación:
- `RetrievedBlock`: bloque recuperado por el motor vectorial (block_id, document_id, text, page_number, ordinal, score)
- `DocumentRetriever`: Protocol que define `index_document()` y `search()`
- `Context`: contexto combinado (bloques locales + recuperados) para la construcción del prompt

### `socratic/retrieval/txtai_backend.py`
Implementación `TxtaiDocumentRetriever` usando txtai + sentence-transformers. Indexa bloques con `upsert` (seguro para reindexación). Busca con consulta SQL filtrando por `tags` (document_id). Solo indexa bloques con texto útil (descarta vacíos, solo espacios, solo puntuación).

### `socratic/retrieval/service.py`
Servicio de aplicación `RetrievalService` que centraliza la lógica de recuperación:
- `retrieve_context(study, current_block, question)`: combina bloques locales (actual + 2 anteriores + 2 siguientes) con recuperados (deduplicados)
- `reindex_document(document_id)`: reconstruye el índice de un documento
- `search(document_id, query, limit)`: búsqueda de diagnóstico

### `socratic/api/documents.py`
Endpoints REST:
- `POST /documents` — Subida y extracción (usa `parse_pdf()` compartido con `inspect-pdf`)
- `DELETE /documents/{id}` — Eliminación en cascada (documentos, bloques, estudios, mensajes)
- `GET /documents` — Listado
- `GET /documents/{id}` — Detalle con bloques

### `socratic/api/studies.py`
Endpoints REST para estudios y mensajes:
- `POST /studies` — Crear estudio para un documento
- `GET /studies` — Listar estudios
- `GET /studies/{id}` — Consultar estado
- `GET /studies/{id}/current-block` — Obtener bloque actual (no avanza)
- `POST /studies/{id}/blocks/{blockId}/complete` — Marcar completado y avanzar
- `POST /studies/{id}/previous-block` — Retroceder al bloque anterior
- `GET /studies/{id}/messages` — Obtener historial
- `POST /studies/{id}/messages` — Crear mensaje

### `socratic/api/ask.py`
Endpoint `POST /studies/{id}/ask` que envía una pregunta al LLM. Construye un contexto ampliado:
1. System prompt
2. Bloque actual
3. 2 bloques anteriores
4. 2 bloques siguientes
5. Fragmentos recuperados (txtai, deduplicados por block_id)
6. Historial reciente (últimas 4 mensagens)
7. Pregunta del usuario

La respuesta se guarda en el historial sin avanzar la posición de lectura.

### `socratic/api/retrieval.py`
Endpoints de recuperación documental:
- `POST /documents/{id}/reindex` — Indexa bloques para recuperación vectorial (202 Accepted)
- `POST /documents/{id}/search` — Búsqueda de diagnóstico (lista bloques relevantes con score)

### `socratic/config/settings.py`
Configuración de la aplicación, externalizada mediante variables de entorno con prefijo `SOCRATIC_`:

**Persistencia:**
- `storage_path`: ruta a la base de datos SQLite (default: `data/socratic.db`)

**Red:**
- `host`: interfaz de escucha (default: `0.0.0.0`)
- `port`: puerto (default: `8885`)

**LLM:**
- `llm_provider`: proveedor LLM (default: `openai-compatible`)
- `llm_base_url`: URL base del endpoint de completado
- `llm_model`: nombre del modelo (default: `gpt-4o-mini`)
- `llm_temperature`: temperatura (default: `0.0`)
- `llm_api_key`: clave API del proveedor
- `llm_timeout_seconds`: timeout en segundos (default: `120`)

**Recuperación:**
- `retrieval_storage`: ruta del índice vectorial (default: `data/retrieval/`)
- `embedding_model`: modelo de embeddings (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `retrieval_limit`: máx. resultados por búsqueda (default: `5`)
- `retrieval_context_limit_chars`: límite de contexto recuperado en caracteres (default: `2000`)

Se puede importar la configuración de OpenCode con:
` socratic config import-opencode --provider <nombre> --model <nombre> --export-shell`

## Recuperación documental

El servidor indexa el documento completo para responder preguntas sobre cualquier parte del texto, no solo el bloque actual.

**Arquitectura:**
```
SQLite (fuente de verdad) ←→ txtai (índice reconstruible)
```

**Modelo de embeddings:** `sentence-transformers/all-MiniLM-L6-v2`
- Multilingüe (incluye español)
- ~23MB, ligero para ejecución local
- Licencia Apache 2.0
- Default de txtai, sin configuración especial

**Persistencia del índice:** `data/retrieval/` (excluido de Git). Se guarda con `embeddings.save(path)` / `embeddings.load(path)`.

**Indexación:** Se invoca con `socratic reindex` (todos) o `socratic reindex <id>` (uno). Usa `upsert` para ser segura ante reindexaciones.

**Búsqueda:** Consulta SQL con `similar()` y filtrado por `tags` (document_id).

## Decisiones

- **sqlite3 stdlib** en vez de SQLAlchemy: simplicidad para Hito 1.
- **pdfplumber** en vez de PyMuPDF: licencia MIT, bueno para PDFs de una columna.
- **UUID** para identificadores: compatible con API pública y distribuido.
- **Pydantic Settings**: configuración externalizada via variables de entorno.
- **check_same_thread=False**: permite usar la misma conexión SQLite en hilos asíncronos de FastAPI.
- **src-layout**: estándar en proyectos Python profesionales, evita problemas de importación en tests.
- **Factory `create_app`**: separa la construcción de la app del entry point, permitiendo tests de reinicio sobre la misma BD sin efectos secundarios al importar.
- **CLI con argparse + httpx (sync)**: sin frameworks de CLI para minimizar dependencias; el servidor es la fuente de verdad y la CLI es un thin view.
- **txtai** para recuperación: índice vectorial ligero, persistencia en disco, filtrado SQL por tags.
- **Protocol** para `DocumentRetriever`: abstracción mínima que permite cambiar el motor de búsqueda en el futuro.

## Cliente CLI

`socratic-cli/` — cliente Python que consume la API pública REST.

```
socratic-cli/
├── socratic_cli/
│   ├── __init__.py
│   ├── __main__.py          # python -m socratic_cli
│   ├── client.py            # SocraticClient (httpx sync)
│   └── main.py              # argparse + comandos
├── tests/
│   ├── test_cli_persistence.py  # Integración real con reinicio del servidor
│   ├── test_full_flow.py        # Flujo completo con servidor real
│   ├── test_next_block.py       # Avance de bloques
│   ├── test_previous_block.py   # Retroceso de bloques
│   └── test_config_import_opencode.py  # Importación de configuración
├── pyproject.toml
└── README.md
```

Comandos: `upload`, `documents`, `document`, `delete`, `create-study`, `studies`,
`study`, `current-block`, `complete-block`, `next-block`, `previous-block`,
`messages`, `message`, `ask`, `reindex`, `search-document`, `inspect-pdf`, `config`.

URL configurable con `--url` o `SOCRATIC_URL` (default `http://127.0.0.1:8885`).

## Despliegue

```bash
cd socratic-server
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m main
```

Puerto por defecto: `8885`.
Base de datos por defecto: `socratic-server/data/socratic.db`.

```bash
cd socratic-cli
.venv/bin/pip install -e .
.venv/bin/socratic --help
```
