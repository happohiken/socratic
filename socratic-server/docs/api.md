# Documentación de la API

## Endpoints de Documentos

### POST /documents

Sube un documento PDF.

**Cuerpo de la solicitud:**

- `file` (archivo, requerido): Archivo PDF a subir.

**Respuesta 201:**

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

### GET /documents

Lista todos los documentos.

**Respuesta 200:**

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

**Respuesta 200:**

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

---

## Endpoints de Estudios

### POST /studies

Crea un estudio para un documento.

**Cuerpo de la solicitud:**

```json
{
  "document_id": "uuid"
}
```

**Respuesta 201:**

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

### GET /studies

Lista todos los estudios.

**Respuesta 200:**

```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "current_block_id": "uuid",
    "last_completed_block_id": null,
    "created_at": "2026-07-12T12:00:00Z",
    "updated_at": "2026-07-12T12:00:00Z"
  }
]
```

### GET /studies/{study_id}

Obtiene el estado de un estudio.

**Respuesta 200:**

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

### GET /studies/{study_id}/current-block

Obtiene el bloque actual de lectura sin avanzar la posición.

**Respuesta 200:**

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

### POST /studies/{study_id}/blocks/{block_id}/complete

Marca un bloque como completado y avanza la posición.

**Respuesta 200:**

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

### GET /studies/{study_id}/messages

Obtiene el historial de mensajes de un estudio.

**Respuesta 200:**

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

Crea un mensaje en el estudio.

**Cuerpo de la solicitud:**

```json
{
  "content": "Pregunta del usuario",
  "role": "user",
  "content_block_id": null
}
```

**Respuesta 201:**

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
