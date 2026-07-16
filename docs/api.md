# API Pública - Socratic Server

Servidor FastAPI expuesto en `0.0.0.0:8885` (todas las interfaces).

## Endpoints de Documentos

### POST /documents

Sube un documento PDF, extrae bloques ordenados y los persiste.

**Cuerpo de la solicitud**: `multipart/form-data` con campo `file` (PDF).

**Respuesta 201**:

```json
{
  "document": {
    "id": "uuid",
    "filename": "sample.pdf",
    "page_count": 1,
    "block_count": 5,
    "format": "pdf",
    "created_at": "2026-07-12T12:00:00Z",
    "updated_at": "2026-07-12T12:00:00Z"
  },
  "blocks": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "ordinal": 1,
      "text": "Texto del bloque",
      "page_number": 1,
      "block_type": "paragraph"
    }
  ]
}
```

**Errores**:
- `400` — Archivo no es PDF o nombre vacío.

### GET /documents

Lista todos los documentos.

**Respuesta 200**:

```json
[
  {
    "id": "uuid",
    "filename": "sample.pdf",
    "page_count": 1,
    "block_count": 5,
    "format": "pdf",
    "created_at": "2026-07-12T12:00:00Z",
    "updated_at": "2026-07-12T12:00:00Z"
  }
]
```

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
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z",
  "blocks": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "ordinal": 1,
      "text": "Texto del bloque",
      "page_number": 1,
      "block_type": "paragraph"
    }
  ]
}
```

**Errores**:
- `404` — Documento no encontrado.

### DELETE /documents/{document_id}

Elimina un documento y todos sus asociados (bloques, estudios, mensajes) mediante cascada.

**Respuesta 204**: Sin contenido.

**Errores**:
- `404` — Documento no encontrado.

---

## Endpoints de Estudios

### POST /studies

Crea un estudio para un documento. Inicializa la posición en el primer bloque.

**Cuerpo de la solicitud**:

```json
{
  "document_id": "uuid"
}
```

**Respuesta 201**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "current_block_id": "uuid",
  "last_completed_block_id": null,
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z"
}
```

**Errores**:
- `404` — Documento no encontrado.
- `400` — El documento no tiene bloques extraídos.

### GET /studies

Lista todos los estudios.

**Respuesta 200**: lista de estudios con `id`, `document_id`, `current_block_id`, `last_completed_block_id`, `created_at`, `updated_at`.

### GET /studies/{study_id}

Obtiene el estado de un estudio.

**Respuesta 200**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "current_block_id": "uuid",
  "last_completed_block_id": "uuid",
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z"
}
```

**Errores**:
- `404` — Estudio no encontrado.

### GET /studies/{study_id}/current-block

Obtiene el bloque actual de lectura sin avanzar la posición. Permite repetir el bloque.

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

Marca un bloque como completado y avanza la posición al siguiente bloque.

**Respuesta 200**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "current_block_id": "uuid",
  "last_completed_block_id": "uuid",
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z"
}
```

**Errores**:
- `404` — Estudio o documento no encontrado.
- `400` — El bloque no pertenece al documento.

### POST /studies/{study_id}/previous-block

Retrocede al bloque anterior del documento. Actualiza `current_block_id` al bloque anterior. Si `current_block_id` es `None` (fin del documento), vuelve al último bloque completado.

**Respuesta 200**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "current_block_id": "uuid",
  "last_completed_block_id": "uuid",
  "created_at": "2026-07-12T12:00:00Z",
  "updated_at": "2026-07-12T12:00:00Z"
}
```

**Errores**:
- `404` — Estudio o documento no encontrado.
- `400` — Ya estás en el primer bloque / no tiene bloques completados para retroceder.

### GET /studies/{study_id}/messages

Obtiene el historial de mensajes de un estudio, ordenado por fecha de creación.

**Respuesta 200**:

```json
[
  {
    "id": "uuid",
    "study_id": "uuid",
    "content_block_id": null,
    "role": "user",
    "content": "¿Qué es Socratic?",
    "created_at": "2026-07-12T12:00:00Z"
  }
]
```

### POST /studies/{study_id}/messages

Crea un mensaje en el estudio. Se usa para guardar preguntas del usuario y respuestas del asistente.

**Cuerpo de la solicitud**:

```json
{
  "content": "Pregunta del usuario",
  "role": "user",
  "content_block_id": null
}
```

**Respuesta 201**:

```json
{
  "id": "uuid",
  "study_id": "uuid",
  "content_block_id": null,
  "role": "user",
  "content": "Pregunta del usuario",
  "created_at": "2026-07-12T12:00:00Z"
}
```

---

## Preguntas contextuales

### POST /studies/{study_id}/ask

Envía una pregunta sobre el bloque actual de lectura. El servidor compone un contexto ampliado con el bloque actual, bloques anteriores y siguientes, fragmentos recuperados del documento completo mediante indexación vectorial, historial reciente y la pregunta. La respuesta se guarda en el historial sin avanzar la posición de lectura.

**Cuerpo de la solicitud**:

```json
{
  "question": "¿Qué significa este término?"
}
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

---

## Interacción conversacional

### POST /studies/{study_id}/interact

Inicia un Turn conversacional. El orquestador decide qué tools invocar
para satisfacer la intención del usuario (continuar, repetir, retroceder,
preguntar) y compone la respuesta final con un único LLM por Turn.

Las tools disponibles son:
- `get_current_block()` — devuelve el bloque actual sin modificar el estado.
- `complete_current_block()` — marca el bloque actual como completado y avanza.
- `previous_block()` — retrocede al bloque anterior.
- `retrieve_document_context(query)` — recupera fragmentos documentales
  relevantes para la consulta (sin modificar el estado).

Solo se persisten los mensajes `user` y `assistant` finales; los tool
calls viven en memoria durante el Turn. El RAG se ejecuta solo si el
LLM lo solicita mediante `retrieve_document_context`.

**Cuerpo de la solicitud**:

```json
{
  "input": "explíca esto y luego continúa"
}
```

**Respuesta 201**:

```json
{
  "answer": "Respuesta final del asistente",
  "study_id": "uuid",
  "message_id": "uuid"
}
```

**Errores**:
- `404` — Estudio no encontrado.

---

## Recuperación documental

### POST /documents/{document_id}/reindex

Indexa todos los bloques de un documento para recuperación vectorial mediante txtai. Devuelve 202 Accepted para indicar que la indexación se ha completado.

**Respuesta 202**:

```json
{
  "status": "indexed",
  "blocks": 8
}
```

**Errores**:
- `404` — Documento no encontrado.

### POST /documents/{document_id}/search

Busca bloques relevantes en un documento indexado. Se usa para diagnóstico. Filtra por document_id mediante consulta SQL en txtai.

**Cuerpo de la solicitud**:

```json
{
  "query": "machine learning medicina",
  "limit": 5
}
```

**Respuesta 200**:

```json
[
  {
    "block_id": "uuid",
    "page_number": 1,
    "ordinal": 8,
    "block_type": "paragraph",
    "score": 0.5973,
    "text": "El machine learning representa una herramienta fundamental..."
  }
]
```

**Errores**:
- `404` — Documento no encontrado.

## Formato de respuesta

Todas las respuestas son JSON. Las fechas usan ISO 8601 con timezone UTC.
