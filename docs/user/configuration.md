# Configuración

Socratic se configura con variables de entorno con prefijo `SOCRATIC_`.
El servidor lee automáticamente un archivo `.env` si existe en el
directorio desde el que se arranca.

## Variables del servidor

### Persistencia y red

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_STORAGE_PATH` | `data/socratic.db` | Ruta de la base de datos SQLite. |
| `SOCRATIC_HOST` | `0.0.0.0` | Interfaz de escucha. `0.0.0.0` permite acceso desde la LAN. |
| `SOCRATIC_PORT` | `8885` | Puerto del servidor. |

### LLM

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_LLM_PROVIDER` | `openai-compatible` | Proveedor LLM. |
| `SOCRATIC_LLM_BASE_URL` | _(vacío)_ | URL del endpoint de completado. **Requerido** para `/ask` y `/interact`. |
| `SOCRATIC_LLM_MODEL` | `gpt-4o-mini` | Nombre del modelo. |
| `SOCRATIC_LLM_TEMPERATURE` | `0.0` | Temperatura del LLM. |
| `SOCRATIC_LLM_API_KEY` | _(vacío)_ | API key del proveedor. **Requerido** para `/ask` y `/interact`. |
| `SOCRATIC_LLM_TIMEOUT_SECONDS` | `120` | Timeout en segundos. |

### Recuperación documental (RAG)

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_RETRIEVAL_STORAGE` | `data/retrieval/` | Ruta del índice vectorial txtai. |
| `SOCRATIC_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo de embeddings. |
| `SOCRATIC_RETRIEVAL_LIMIT` | `5` | Máx. resultados por búsqueda. |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | `2000` | Límite de contexto recuperado en `/ask`. |

El modelo de embeddings se descarga la primera vez que se usa y se
cachea. El directorio `data/retrieval/` se excluye de Git.

### Orquestador

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_ORCHESTRATOR_MAX_TOOL_ITERATIONS` | `5` | Máx. iteraciones del bucle de tool calling por Turn. |
| `SOCRATIC_ORCHESTRATOR_HISTORY_MESSAGES` | `10` | Mensajes de historial reciente incluidos en el contexto. |

## Variables de la CLI

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_URL` | `http://127.0.0.1:8885` | URL base del servidor. |

También se puede pasar con `--url` en cada comando.

## Configurar el LLM desde OpenCode

Si ya tienes OpenCode configurado en `~/.config/opencode/opencode.json`,
puedes importar la configuración del LLM:

```bash
# Vista previa (formato systemd, con API key visible)
socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --print-env

# Exportar variables para la sesión actual (para usar con eval)
eval "$(socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --export-shell)"

# Arrancar el servidor con las variables exportadas
cd socratic-server && python -m main
```

### Argumentos

- `--provider <nombre>`: nombre del proveedor en `opencode.json`. Si se
  omite y hay varios, selección interactiva.
- `--model <nombre>`: nombre del modelo dentro del proveedor. Si se
  omite y hay varios, selección interactiva.
- `--export-shell`: genera `export KEY='value'` para usar con `eval`.
- `--print-env`: genera `KEY=value` para systemd.

`--export-shell` y `--print-env` son **mutuamente excluyentes** y
**requeridos** (uno de los dos).

### Variables generadas

`SOCRATIC_LLM_PROVIDER`, `SOCRATIC_LLM_BASE_URL`, `SOCRATIC_LLM_MODEL`,
`SOCRATIC_LLM_API_KEY`, `SOCRATIC_LLM_TIMEOUT_SECONDS`.

### Advertencias

- La salida de `--print-env` **puede contener secretos** (API key). No
  la guardes en el repositorio ni en logs compartidos.
- Si no se resuelve la API key, se generan el resto de variables y se
  muestra un error por stderr.
- Si no se encuentra `baseURL`, la orden falla.

## Configurar el LLM manualmente

Si no usas OpenCode, define las variables directamente:

```bash
export SOCRATIC_LLM_BASE_URL="https://api.openai.com/v1"
export SOCRATIC_LLM_MODEL="gpt-4o-mini"
export SOCRATIC_LLM_API_KEY="sk-..."
export SOCRATIC_LLM_TIMEOUT_SECONDS=120

cd socratic-server && python -m main
```

O en un archivo `.env` en `socratic-server/`:

```env
SOCRATIC_LLM_BASE_URL=https://api.openai.com/v1
SOCRATIC_LLM_MODEL=gpt-4o-mini
SOCRATIC_LLM_API_KEY=sk-...
SOCRATIC_LLM_TIMEOUT_SECONDS=120
```

> **No subas `.env` a Git**: añádelo a `.gitignore`. Las API keys son
> secretos.

## Proveedores compatibles

`OpenAIClient` usa el SDK oficial `openai`, compatible con cualquier
API OpenAI-compatible:

- OpenAI oficial (`https://api.openai.com/v1`).
- LiteLLM, Ollama, vLLM, etc.
- Proveedores locales (servidor local en `http://localhost:PORT/v1`).

Solo necesitas cambiar `SOCRATIC_LLM_BASE_URL`, `SOCRATIC_LLM_MODEL` y
`SOCRATIC_LLM_API_KEY` según el proveedor.
