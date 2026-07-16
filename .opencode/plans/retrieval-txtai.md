# Plan: Recuperación documental con txtai

## Estado: Implementación en curso

## Resumen del diseño

### Arquitectura

```
CLI (argparse + SocraticClient)
  → REST (httpx)
    → FastAPI
      → RetrievalService
        → DocumentRetriever (Protocol)
          → TxtaiDocumentRetriever
            → txtai Embeddings
            → SQLite (fuente de verdad)
```

txtai es un índice reconstruible. SQLite es la fuente de verdad.

### Módulos nuevos

| Archivo | Contenido |
|---------|-----------|
| `src/socratic/retrieval/__init__.py` | Exports |
| `src/socratic/retrieval/models.py` | `RetrievedBlock`, `DocumentRetriever` (Protocol), `Context` |
| `src/socratic/retrieval/txtai_backend.py` | `TxtaiDocumentRetriever` |
| `src/socratic/retrieval/service.py` | `RetrievalService` |

### Archivos modificados

| Archivo | Cambios |
|---------|---------|
| `src/socratic/config/settings.py` | 4 nuevos campos |
| `src/socratic/app.py` | Crear `RetrievalService` |
| `src/socratic/api/ask.py` | Contexto ampliado |
| `src/socratic/api/retrieval.py` | **Nuevo** — endpoints reindex + search |
| `socratic-cli/socratic_cli/main.py` | Subcommands reindex + search-document |
| `socratic-cli/socratic_cli/client.py` | Métodos reindex_document + search_document |
| `pyproject.toml` | Añadir `txtai` |
| `.gitignore` | Añadir `data/retrieval/` |

### Filtrado de bloques

Solo se descartan bloques:
- Vacíos o solo espacios
- Solo puntuación

No se descarta por longitud (conserva encabezados cortos).

### Indexación

- Sin endpoint REST para reindexar (operación administrativa)
- CLI: `socratic reindex` y `socratic reindex <document-id>`
- Se usa `upsert` para indexación repetida segura

### Búsqueda

- Filtrado por `tags` en consulta SQL: `select * from txtai where similar('consulta') and tags='doc-id'`
- No se necesita filtrado posterior

### Contexto ampliado

1. System prompt
2. Bloque actual
3. 2 bloques anteriores
4. 2 bloques siguientes
5. Bloques recuperados txtai (deduplicados)
6. Historial reciente
7. Pregunta del usuario

### RetrievalService

Centraliza toda la lógica de recuperación:
- `retrieve_context(study, current_block, question)` → Context
- `reindex_document(document_id)` → int (bloques indexados)
- `search(document_id, query, limit)` → list[RetrievedBlock]
