# API REST (agentes)

Servidor FastAPI en `0.0.0.0:8885`. Documentación interactiva en
`/docs` (Swagger). Respuestas JSON; fechas ISO 8601 UTC.

## Endpoints

### Documentos (`api/documents.py`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/documents` | Subir PDF. `multipart/form-data` campo `file`. Extrae bloques y persiste. 201 con `{document, blocks}`. 400 si no es PDF. |
| GET | `/documents` | Lista documentos. |
| GET | `/documents/{id}` | Detalle con bloques. 404 si no existe. |
| DELETE | `/documents/{id}` | Elimina en cascada (bloques, estudios, mensajes). 204. |

### Estudios y mensajes (`api/studies.py`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/studies` | Body `{document_id}`. Inicializa `current_block_id` en el primer bloque. 404 si doc no existe; 400 si no tiene bloques. |
| GET | `/studies` | Lista estudios. |
| GET | `/studies/{id}` | Estado. 404 si no existe. |
| GET | `/studies/{id}/current-block` | Bloque actual **sin avanzar**. 400 si no hay bloque actual. |
| POST | `/studies/{id}/blocks/{blockId}/complete` | Marca completado y avanza. 400 si bloque ajeno al documento. |
| POST | `/studies/{id}/previous-block` | Retrocede. 400 si primer bloque o sin completados. |
| GET | `/studies/{id}/messages` | Historial ordenado por `created_at` ASC. |
| POST | `/studies/{id}/messages` | Body `{content, role, content_block_id?}`. 201. |

### Pregunta contextual (`api/ask.py`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/studies/{id}/ask` | Body `{question}`. Construye contexto ampliado (bloque actual + 2 anteriores + 2 siguientes + RAG + historial reciente) y llama **una sola vez** a `LLMClient.complete()`. Persiste user+assistant. **No** modifica posición de lectura. 400 si no hay bloque actual. |

### Conversacional (`api/interact.py`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/studies/{id}/interact` | Body `{input}`. Inicia Turn conversacional. El orquestador decide tools, compone respuesta final, persiste user/assistant. 404 si estudio no existe. |

### Recuperación (`api/retrieval.py`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/documents/{id}/reindex` | Indexa bloques con txtai. 202 con `{status, blocks}`. |
| POST | `/documents/{id}/search` | Body `{query, limit=5}`. Diagnóstico; devuelve bloques con `score`. 404 si doc no existe. |

## Patrones de los endpoints

- Dependencias vía `Depends(get_db)`, `Depends(get_llm)`,
  `Depends(get_retrieval)`, `Depends(get_navigation)`,
  `Depends(get_orchestrator)` — todas leen de `app.state`.
- Errores: `HTTPException(status_code=..., detail=...)`.
- `interact.py` es **capa fina**: valida HTTP, obtiene `Study`, delega
  en `app.state.orchestrator.interact(study, input)`. Toda la lógica
  está en el orquestador.
- `ask.py` conserva composición imperativa del prompt (mantenido durante
  transición a orquestador); `interact.py` es la vía nueva con tools.

## Esquemas Pydantic por endpoint

Cada router define sus modelos de request/response inline
(`DocumentSummary`, `StudyResponse`, `BlockResponse`, `MessageResponse`,
`AskRequest`/`AskResponse`, `InteractRequest`/`InteractResponse`,
`SearchRequest`, `RetrievedBlockSummary`). Las fechas se serializan con
`.isoformat()`.

## Referencia completa

Para detalle de cuerpos y respuestas, ver
`docs/development/api.md`.
