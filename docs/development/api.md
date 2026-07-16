# API Pública - Socratic Server

Servidor FastAPI expuesto en `0.0.0.0:8885` (todas las interfaces).
Documentación interactiva en `http://<host>:8885/docs` (Swagger UI).

Todas las respuestas son JSON. Las fechas usan ISO 8601 con timezone UTC.

## Endpoints de Documentos

### POST /documents

Sube un documento PDF, extrae bloques ordenados y los persiste.

**Cuerpo**: `multipart/form-data` con campo `file` (PDF).

**Respuesta 201**:

```json
{
  "document": {
    "id": "uuid",
    "filename": "sample.pdf",
    "page_count": 1,
    "block_count": 5,
    "format": "pdf",
    "created_at": "2026-07-12T12:00:00+00:00",
    "updated_at": "2026-07-12T12:00:00+00:00"
  },
  "blocks": [
    {
      "id": "uuid",
      "ordinal": 1,
      "text": "Texto del bloque",
      "page_number": 1,
      "block_type": "paragraph"
    }
  ]
}
```

**Errores**:
- `400` — El archivo no es PDF o el nombre está vacío.

### GET /documents

Lista todos los documentos, ordenados por `created_at DESC`.

**Respuesta 200**: lista de `DocumentSummary`.

### GET /documents/{document_id}

Obtiene un documento con sus bloques.

**Respuesta 200**:

```json
{
  "id": "uuid",
  "filename": "sample.pdf",
  "page_count": 1,
  "block_count": 5,
  "format": "pdf",
  "created_at": "2026-07-12T12:00:00+00:00",
  "updated_at": "2026-07-12T12:00:00+00:00",
  "blocks": [
    {
      "id": "uuid",
      "ordinal": 1,
      "text": "Texto del bloque",
      "page_number": 1,
      "block_type": "paragraph"
    }
  ]
}
```

**Errores**: `404` — Documento no encontrado.

### DELETE /documents/{document_id}

Elimina un documento y todos sus asociados (bloques, estudios,
mensajes) mediante cascada SQL.

**Respuesta 204**: sin contenido.

**Errores**: `404` — Documento no encontrado; `500` — error al
eliminar.

---

## Endpoints de Estudios

### POST /studies

Crea un estudio para un documento. Inicializa la posición en el primer
bloque.

**Cuerpo**:

```json
{ "document_id": "uuid" }
```

**Respuesta 201**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "current_block_id": "uuid",
  "last_completed_block_id": null,
  "created_at": "2026-07-12T12:00:00+00:00",
  "updated_at": "2026-07-12T12:00:00+00:00"
}
```

**Errores**:
- `404` — Documento no encontrado.
- `400` — El documento no tiene bloques extraídos.

### GET /studies

Lista todos los estudios.

**Respuesta 200**: lista de `StudyResponse`.

### GET /studies/{study_id}

Obtiene el estado de un estudio.

**Errores**: `404` — Estudio no encontrado.

### GET /studies/{study_id}/current-block

Obtiene el bloque actual de lectura **sin avanzar** la posición.
Permite repetir el bloque.

**Respuesta 200**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "ordinal": 1,
  "text": "Texto del bloque",
  "page_number": 1,
  "block_type": "paragraph"
}
```

**Errores**:
- `404` — Estudio no encontrado.
- `400` — El estudio no tiene bloque actual (lectura completada).

### POST /studies/{study_id}/blocks/{block_id}/complete

Marca un bloque como completado y avanza la posición al siguiente
bloque.

**Respuesta 200**: `StudyResponse` con `current_block_id` y
`last_completed_block_id` actualizados.

**Errores**:
- `404` — Estudio no encontrado.
- `400` — El bloque no pertenece al documento.

### POST /studies/{study_id}/previous-block

Retrocede al bloque anterior del documento. Actualiza `current_block_id`
al bloque anterior. Si `current_block_id` es `None` (fin del documento),
vuelve al último bloque completado.

**Respuesta 200**: `StudyResponse` actualizada.

**Errores**:
- `404` — Estudio no encontrado.
- `400` — Ya estás en el primer bloque / no tiene bloques completados
  para retroceder.

### GET /studies/{study_id}/messages

Obtiene el historial de mensajes de un estudio, ordenado por
`created_at` ASC.

**Respuesta 200**: lista de `MessageResponse`:

```json
[
  {
    "id": "uuid",
    "study_id": "uuid",
    "content_block_id": null,
    "role": "user",
    "content": "¿Qué es Socratic?",
    "created_at": "2026-07-12T12:00:00+00:00"
  }
]
```

### POST /studies/{study_id}/messages

Crea un mensaje en el estudio. Se usa para guardar preguntas del
usuario y respuestas del asistente.

**Cuerpo**:

```json
{
  "content": "Pregunta del usuario",
  "role": "user",
  "content_block_id": null
}
```

**Respuesta 201**: `MessageResponse`.

---

## Preguntas contextuales

### POST /studies/{study_id}/ask

Envía una pregunta sobre el bloque actual de lectura. El servidor
compone un contexto ampliado con el bloque actual, bloques anteriores y
siguientes, fragmentos recuperados del documento completo mediante
indexación vectorial, historial reciente y la pregunta. La respuesta se
guarda en el historial **sin avanzar** la posición de lectura.

**Cuerpo**:

```json
{ "question": "¿Qué significa este término?" }
```

**Respuesta 201**:

```json
{
  "answer": "El término se refiere a...",
  "study_id": "uuid",
  "message_id": "uuid"
}
```

**Errores**:
- `404` — Estudio no encontrado.
- `400` — El estudio no tiene bloque actual.

**Composición del contexto** (en `api/ask.py`):

1. System prompt.
2. Bloque actual.
3. 2 bloques anteriores.
4. 2 bloques siguientes.
5. Fragmentos recuperados (txtai, deduplicados por `block_id`).
6. Historial reciente (últimos 4 mensajes).
7. Pregunta del usuario.

Inserta mensajes `assistant` ficticios para forzar alternancia
user/assistant. Llama **una sola vez** a `LLMClient.complete()`.

---

## Interacción conversacional

### POST /studies/{study_id}/interact

Inicia un Turn conversacional. El orquestador decide qué tools invocar
para satisfacer la intención del usuario (continuar, repetir,
retroceder, preguntar) y compone la respuesta final con un único LLM
por Turn.

**Tools disponibles**:
- `get_current_block()` — devuelve el bloque actual sin modificar el
  estado.
- `complete_current_block()` — marca el bloque actual como completado y
  avanza.
- `previous_block()` — retrocede al bloque anterior.
- `retrieve_document_context(query)` — recupera fragmentos documentales
  relevantes para la consulta (sin modificar el estado).

Solo se persisten los mensajes `user` y `assistant` finales; los tool
calls viven en memoria durante el Turn. El RAG se ejecuta solo si el
LLM lo solicita mediante `retrieve_document_context`.

**Cuerpo**:

```json
{ "input": "explíca esto y luego continúa" }
```

**Respuesta 201**:

```json
{
  "answer": "Respuesta final del asistente",
  "study_id": "uuid",
  "message_id": "uuid"
}
```

**Errores**: `404` — Estudio no encontrado.

Ver [orchestrator.md](orchestrator.md) para el flujo completo.

---

## Recuperación documental

### POST /documents/{document_id}/reindex

Indexa todos los bloques de un documento para recuperación vectorial
mediante txtai. Devuelve 202 Accepted.

**Respuesta 202**:

```json
{ "status": "indexed", "blocks": 8 }
```

**Errores**: `404` — Documento no encontrado.

### POST /documents/{document_id}/search

Busca bloques relevantes en un documento indexado. Se usa para
diagnóstico. Filtra por `document_id` mediante consulta SQL en txtai.

**Cuerpo**:

```json
{ "query": "machine learning medicina", "limit": 5 }
```

**Respuesta 200**:

```json
[
  {
    "block_id": "uuid",
    "page_number": 1,
    "ordinal": 8,
    "block_type": "",
    "score": 0.5973,
    "text": "El machine learning representa una herramienta fundamental..."
  }
]
```

**Errores**: `404` — Documento no encontrado.

> **Nota**: el campo `block_type` se devuelve vacío en la respuesta
> (la serialización en `RetrievedBlockSummary.from_retrieved` lo
> inicializa como `""` porque `RetrievedBlock` no incluye tipo).

---

## Esquemas Pydantic

Cada router define sus modelos inline. Los más relevantes:

- `DocumentSummary`, `DocumentDetail`, `UploadResponse` (`documents.py`).
- `StudyCreate`, `StudyResponse`, `BlockResponse`, `MessageResponse`,
  `MessageCreate` (`studies.py`).
- `AskRequest`, `AskResponse` (`ask.py`).
- `InteractRequest`, `InteractResponse` (`interact.py`).
- `SearchRequest`, `RetrievedBlockSummary` (`retrieval.py`).

Las fechas se serializan con `.isoformat()` al construir las
respuestas.
