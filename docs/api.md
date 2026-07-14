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

## Formato de respuesta

Todas las respuestas son JSON. Las fechas usan ISO 8601 con timezone UTC.
