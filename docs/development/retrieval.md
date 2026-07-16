# Recuperación documental (RAG)

`socratic-server/src/socratic/retrieval/` — indexación vectorial y
recuperación de bloques relevantes de cualquier parte del documento.

## Arquitectura

```
SQLite (fuente de verdad) ←→ txtai (índice reconstruible)
```

El índice txtai **no** es persistencia canónica; se puede borrar y
reconstruir desde SQLite con `reindex`. SQLite siempre es la fuente de
la verdad.

```
CLI → REST → FastAPI → RetrievalService → DocumentRetriever (Protocol) → TxtaiDocumentRetriever → txtai
```

## Módulos

### `models.py`

```python
@dataclass(frozen=True)
class RetrievedBlock:
    block_id: str
    document_id: str
    text: str
    page_number: int
    ordinal: int
    score: float

class DocumentRetriever(Protocol):
    def index_document(self, document_id: str, blocks: Sequence[ContentBlock]) -> None: ...
    def search(self, document_id: str, query: str, limit: int = 5) -> list[RetrievedBlock]: ...

@dataclass(frozen=True)
class Context:
    local_blocks: list[ContentBlock]
    retrieved_blocks: list[RetrievedBlock]
```

`DocumentRetriever` es la abstracción mínima que permite cambiar el
motor de búsqueda en el futuro sin modificar `RetrievalService` ni los
endpoints.

### `txtai_backend.py`

`TxtaiDocumentRetriever(storage_path, embedding_model)`.

- Config del `Embeddings` (lazy en `embeddings` property):
  ```python
  {"path": embedding_model, "content": "sqlite", "id": "id"}
  ```
- `index_document(document_id, blocks)`:
  - Filtra bloques no indexables (`_is_indexable`).
  - Construye tuplas `(block.id, {text, page_number, ordinal, block_type}, document_id)`.
  - `embeddings.upsert(indexable)` — seguro para reindexaciones (no
    duplica).
  - Captura excepciones y loggea; el documento permanece en SQLite.
- `search(document_id, query, limit=5)`:
  ```python
  sql = (
      f"select id, text, page_number, ordinal, block_type, score "
      f"from txtai "
      f"where similar('{query}') "
      f"and tags='{document_id}' "
      f"limit {limit}"
  )
  ```
  Devuelve `list[RetrievedBlock]`.
- `save()` / `load()`: persisten el índice en
  `storage_path`. `load()` es seguro si no existe (crea vacío).
- `count()`: número de entradas en el índice.
- `_is_indexable(block)`: descarta bloques vacíos, solo espacios o
  solo puntuación. Conserva headings cortos como "Introducción".

### `service.py`

`RetrievalService(retriever, db)`.

#### `retrieve_context(study, current_block, question, limit=5) -> Context`

1. Obtiene todos los bloques del documento (`get_content_blocks`).
2. Construye `local_blocks`:
   - Bloque actual.
   - 2 anteriores (desde `max(0, current_index - 2)`).
   - 2 siguientes (hasta `min(len, current_index + 3)`).
3. Recuperación vectorial: `retriever.search(document_id, question, limit)`.
4. **Deduplicación**: excluye `RetrievedBlock` cuyo `block_id` ya está
   en `local_blocks`.
5. Devuelve `Context(local_blocks, retrieved_blocks)`.

#### `reindex_document(document_id) -> int`

- Obtiene el documento; si no existe, devuelve 0.
- Obtiene los bloques.
- `retriever.index_document(document_id, blocks)`.
- Devuelve `len(blocks)`.

#### `search(document_id, query, limit=5) -> list[RetrievedBlock]`

Diagnóstico directo sobre el índice.

## Uso desde otros componentes

### `api/ask.py` (`POST /studies/{id}/ask`)

```python
context = retrieval.retrieve_context(study, current_block, body.question)
# construye prompt con local_blocks (actual + anteriores + siguientes)
# y retrieved_blocks (vía _build_prompt con límite retrieval_context_limit_chars)
answer = llm.complete(context_messages)
```

### `orchestrator/tools.py::retrieve_document_context`

```python
result = context.retrieval.retrieve_context(
    context.study, context.current_block, query,
)
return [serializado(rb) for rb in result.retrieved_blocks]
```

La tool **solo** devuelve `retrieved_blocks` (no `local_blocks`), como
datos estructurados al LLM. No construye narrativa.

### `api/retrieval.py`

- `POST /documents/{id}/reindex` → `retrieval.reindex_document(id)`.
- `POST /documents/{id}/search` → `retrieval.search(id, query, limit)`.

## Modelo de embeddings

`sentence-transformers/all-MiniLM-L6-v2`:

- Multilingüe (incluye español).
- ~23 MB, ligero para ejecución local.
- Licencia Apache 2.0.
- Default de txtai, sin configuración especial.
- Se descarga la primera vez y se cachea en `~/.cache/huggingface/`
  (o equivalente).

## Persistencia del índice

- Ruta: `data/retrieval/` (excluida de Git).
- `create_app` invoca `retriever.load()` al construir la app.
- Si no existe el índice, se crea vacío y se llena al indexar.
- `TxtaiDocumentRetriever.embeddings` es lazy: se construye en el
  primer uso (index o search).
- Borrar `data/retrieval/` es seguro: se reconstruye con `reindex`.

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_RETRIEVAL_STORAGE` | `data/retrieval/` | Ruta del índice vectorial |
| `SOCRATIC_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo de embeddings |
| `SOCRATIC_RETRIEVAL_LIMIT` | `5` | Máx. resultados por búsqueda |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | `2000` | Límite de contexto recuperado en `_build_prompt` (`/ask`) |

> **Nota**: `SOCRATIC_RETRIEVAL_LIMIT` se pasa como `limit` a
> `retrieve_context`, pero el default hardcoded en la firma de
> `RetrievalService.retrieve_context` es `5`; el endpoint `/ask` no lo
> lee de settings. Pendiente de unificar.

## Invariantes

- SQLite siempre fuente de verdad; borrar `data/retrieval/` es seguro.
- Reindexar es idempotente (usa `upsert`).
- Solo se descartan bloques vacíos o solo puntuación; headings cortos
  se conservan.
- La deduplicación por `block_id` evita fragmentos duplicados en el
  contexto.
- `retrieve_document_context` (tool del orquestador) no modifica
  estado, no persiste, no construye narrativa, no llama al LLM.

## Endpoints relacionados

- `POST /documents/{id}/reindex` → 202 `{status, blocks}`
- `POST /documents/{id}/search` → lista de `RetrievedBlockSummary`
- `POST /studies/{id}/ask` (usa `retrieve_context` internamente)
- `POST /studies/{id}/interact` (lo usa vía tool
  `retrieve_document_context` si el LLM lo pide)
