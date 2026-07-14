# Socratic CLI

Cliente CLI de Socratic. Consume la API pública REST del servidor. Es un cliente
thin: envía comandos y muestra respuestas. El servidor es la fuente de verdad
del estado.

## Instalación

```bash
cd socratic-cli
pip install -e .
```

Requiere `httpx`. Para desarrollo y tests añade `pip install -e ".[dev]"`.

## Uso

Arranca el servidor (`socratic-server`) en otra terminal y luego:

```bash
socratic upload ruta/al.pdf
socratic documents
socratic create-study <document_id>
socratic current-block <study_id>
socratic complete-block <study_id> <block_id>
socratic next-block <study_id>
socratic previous-block <study_id>
socratic message <study_id> "¿Pregunta?" --role user
socratic messages <study_id>
socratic ask <study_id> "¿Qué significa este término?"
socratic delete <document_id>

# Recuperación documental
socratic reindex [<document_id>]
socratic search-document <id> "consulta"

# Inspeccionar un PDF
socratic inspect-pdf ruta/al.pdf [--format json] [--pages 1-5]
```

La URL del servidor se configura con `--url` o la variable de entorno
`SOCRATIC_URL` (default `http://127.0.0.1:8885`).

```bash
SOCRATIC_URL=http://192.168.1.10:8885 socratic documents
# o
socratic --url http://192.168.1.10:8885 documents
```

## Comandos

| Comando | Descripción |
|---------|-------------|
| `upload <pdf>` | Subir un PDF al servidor |
| `documents` | Listar documentos |
| `document <id>` | Detalle de un documento y sus bloques |
| `create-study <document_id>` | Crear un estudio para un documento |
| `studies` | Listar estudios |
| `study <study_id>` | Consultar el estado de un estudio |
| `current-block <study_id>` | Obtener el bloque actual de lectura |
| `complete-block <study_id> <block_id>` | Marcar un bloque como completado y avanzar |
| `messages <study_id>` | Listar mensajes de un estudio |
| `message <study_id> <content> [--role ROLE] [--block-id ID]` | Crear un mensaje |
| `reindex [<document_id>]` | Indexar todos los documentos o un concreto para recuperación |
| `search-document <id> <query> [--limit N]` | Buscar bloques relevantes (diagnóstico) |

## Tests

```bash
pip install -e ".[dev]"
# Requiere el paquete del servidor instalado (socratic-server) para create_app
python -m pytest tests/ -v
```

Los tests levantan el servidor real con uvicorn en un hilo, ejecutan el flujo
completo vía CLI, reinician el servidor sobre la misma BD y verifican que el
estado se conservó.
