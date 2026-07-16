# Recuperación documental (agentes)

`socratic-server/src/socratic/retrieval/` — RAG con txtai +
sentence-transformers.

## Arquitectura

```
SQLite (fuente de verdad) ←→ txtai (índice reconstruible)
```

El índice txtai **no** es persistencia canónica; se puede borrar y
reconstruir desde SQLite con `reindex`.

## Módulos

- **`models.py`** — `RetrievedBlock` (frozen), `DocumentRetriever`
  (Protocol con `index_document` y `search`), `Context` (combina
  `local_blocks` y `retrieved_blocks`).
- **`txtai_backend.py`** — `TxtaiDocumentRetriever`. Config:
  `{"path": embedding_model, "content": "sqlite", "id": "id"}`.
  - `index_document`: usa `embeddings.upsert(...)` (seguro ante
    reindexaciones). Filtra bloques no indexables (vacíos, solo
    puntuación).
  - `search`: consulta SQL con `similar('{query}')` y
    `tags='{document_id}'` para filtrar por documento. `limit`
    resultados.
  - `save()` / `load()` persisten el índice en disco.
- **`service.py`** — `RetrievalService(retriever, db)`.
  - `retrieve_context(study, current_block, question, limit=5) -> Context`:
    bloques locales (actual + 2 anteriores + 2 siguientes) + bloques
    recuperados por similitud, **deduplicados por `block_id`** respecto
    a los locales.
  - `reindex_document(document_id) -> int`: reconstruye índice del doc.
  - `search(document_id, query, limit) -> list[RetrievedBlock]`:
    diagnóstico.

## Uso desde otros componentes

- **`api/ask.py`** llama a `retrieve_context()` y compone el prompt con
  `_build_prompt()` (limita `retrieval_context_limit_chars=2000`).
- **`orchestrator/tools.py::retrieve_document_context`** llama a
  `retrieve_context()` y devuelve `retrieved_blocks` como datos
  estructurados al LLM (sin construir narrativa).
- **`api/retrieval.py`** expone `/reindex` y `/search` para diagnóstico
  y administración.

## Modelo de embeddings

`sentence-transformers/all-MiniLM-L6-v2` — multilingüe (incluye
español), ~23 MB, licencia Apache 2.0, default de txtai. Se descarga
la primera vez y se cachea.

## Persistencia del índice

- Ruta: `data/retrieval/` (excluida de Git).
- Carga automática al construir la app (`retriever.load()` en
  `create_app`); si no existe, se crea vacío y se llena al indexar.
- `TxtaiDocumentRetriever.embeddings` es lazy: se construye en el
  primer uso.

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_RETRIEVAL_STORAGE` | `data/retrieval/` | Ruta del índice |
| `SOCRATIC_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo |
| `SOCRATIC_RETRIEVAL_LIMIT` | `5` | Máx. resultados por búsqueda |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | `2000` | Límite chars en `_build_prompt` |

## Invariantes

- SQLite siempre fuente de verdad; borrar `data/retrieval/` es seguro
  (se reconstruye con `reindex`).
- Reindexar es idempotente (usa `upsert`).
- Solo se descartan bloques vacíos o solo puntuación; headings cortos
  como "Introducción" se conservan.

## Endpoints relacionados

- `POST /documents/{id}/reindex` → 202 `{status, blocks}`
- `POST /documents/{id}/search` → lista de `RetrievedBlockSummary`
- `POST /studies/{id}/ask` (usa `retrieve_context` internamente)
- `POST /studies/{id}/interact` (lo usa vía tool
  `retrieve_document_context` si el LLM lo pide)
