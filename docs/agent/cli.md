# Cliente CLI (agentes)

`socratic-cli/` — cliente Python thin que consume la API REST.

## Estructura

```
socratic-cli/
├── pyproject.toml           # Deps: httpx; dev: pytest, uvicorn, fastapi,
│                            #       pdfplumber, fpdf2, pydantic-settings
│                            # Entry point: socratic = socratic_cli.main:main
├── socratic_cli/
│   ├── __init__.py
│   ├── __main__.py          # python -m socratic_cli
│   ├── client.py            # SocraticClient (httpx sync) + SocraticAPIError
│   ├── main.py              # argparse + comandos + cmd_config_import_opencode
│   └── inspect_pdf.py       # socratic inspect-pdf (usa parse_pdf del server)
└── tests/
    ├── test_cli_persistence.py   # Integración con reinicio del servidor
    ├── test_full_flow.py         # Flujo completo con servidor real
    ├── test_next_block.py
    ├── test_previous_block.py
    └── test_config_import_opencode.py
```

## `SocraticClient` (`client.py`)

- `httpx.Client` sync con `base_url` y `timeout=30.0`.
- Context manager (`__enter__`/`__exit__`).
- `_request(method, path, **kwargs)`: lanza `SocraticAPIError(status, detail)`
  si `status >= 400`; devuelve JSON o `None` para 204.

Métodos: `upload_document`, `delete_document`, `list_documents`,
`get_document`, `reindex_document`, `search_document`, `create_study`,
`list_studies`, `get_study`, `get_current_block`, `complete_block`,
`previous_block`, `list_messages`, `create_message`, `ask`.

> **No existe** método `interact`: la CLI no expone todavía el endpoint
> `/interact`. Pendiente de implementar.

## Comandos (`main.py`)

| Comando | Descripción |
|---|---|
| `upload <pdf>` | Subir PDF |
| `documents` | Listar documentos |
| `document <id>` | Detalle con bloques |
| `delete <id>` | Eliminar en cascada |
| `create-study <document_id>` | Crear estudio |
| `studies` | Listar estudios |
| `study <study_id>` | Estado de un estudio |
| `current-block <study_id>` | Bloque actual (no avanza) |
| `complete-block <study_id> <block_id>` | Marcar completado y avanzar |
| `next-block <study_id> [--verbose]` | Obtener, imprimir y completar el actual |
| `previous-block <study_id> [--verbose]` | Retroceder (solo lectura del bloque anterior) |
| `messages <study_id>` | Listar mensajes |
| `message <study_id> <content> [--role ROLE] [--block-id ID]` | Crear mensaje |
| `ask <study_id> <question>` | Pregunta contextual al LLM |
| `reindex [<document_id>]` | Indexar todos o un documento |
| `search-document <id> <query> [--limit N]` | Búsqueda de diagnóstico |
| `inspect-pdf <pdf> [--format text\|json] [--pages N-M] [--output FILE]` | Inspeccionar PDF sin subirlo |
| `config import-opencode --provider P --model M (--export-shell\|--print-env)` | Generar variables SOCRATIC_LLM_* desde OpenCode |

URL: `--url` o `SOCRATIC_URL` (default `http://127.0.0.1:8885`).

## `inspect-pdf`

Usa `parse_pdf()` del paquete `socratic.document_processing` (depende
del servidor instalado). No requiere servidor corriendo. Útil para
diagnosticar la descomposición documental sin subir el PDF.

## `cmd_config_import_opencode`

Lee `~/.config/opencode/opencode.json`:
- `provider.<name>.options.baseURL` (o `base_url`)
- `provider.<name>.options.apiKey` (o `options.api_key_env`)
- `provider.<name>.options.timeout` (si es `False`/`0` → 120)
- Selección interactiva si hay múltiples proveedores/modelos.

Genera: `SOCRATIC_LLM_PROVIDER`, `SOCRATIC_LLM_BASE_URL`,
`SOCRATIC_LLM_MODEL`, `SOCRATIC_LLM_API_KEY`,
`SOCRATIC_LLM_TIMEOUT_SECONDS`.

`--export-shell` y `--print-env` son **mutuamente excluyentes** y
**requeridos** (uno de los dos).

## Tests

Los tests de la CLI levantan el servidor real con `uvicorn` en un hilo
sobre una BD temporal, ejecutan el flujo completo vía CLI, reinician el
servidor sobre la misma BD y verifican recuperación. Requieren el
paquete `socratic-server` instalado en el entorno.
