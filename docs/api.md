# API Pública - Socratic Server

Servidor FastAPI expuesto en `127.0.0.1:8000`.

## Endpoints

### Cargar documento

```
POST /documents
```

**Body**: `multipart/form-data` con campo `file` (PDF).

**Respuesta 200**:
```json
{
  "id": "uuid",
  "filename": "nombre.pdf",
  "size": 12345,
  "created_at": "2026-07-12T10:00:00Z",
  "block_count": 7
}
```

**Errores**:
- `400` — Archivo no es PDF o nombre vacío.

### Listar documentos

```
GET /documents
```

**Respuesta 200**: lista de documentos con `id`, `filename`, `size`, `created_at`, `block_count`.

### Detalle de documento

```
GET /documents/{id}
```

**Respuesta 200**:
```json
{
  "id": "uuid",
  "filename": "nombre.pdf",
  "size": 12345,
  "created_at": "2026-07-12T10:00:00Z",
  "content_blocks": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "order": 0,
      "content": "Texto del bloque...",
      "created_at": "2026-07-12T10:00:00Z"
    }
  ]
}
```

**Errores**:
- `404` — Documento no encontrado.

## Formato de respuesta

Todas las respuestas son JSON. Las fechas usan ISO 8601 con timezone UTC.
