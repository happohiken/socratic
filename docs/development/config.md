# Configuración

## Servidor (`socratic-server/src/socratic/config/settings.py`)

`Settings` (Pydantic BaseSettings) con prefijo `SOCRATIC_`, lee `.env`
si existe, `extra="ignore"`.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOCRATIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_path: Path = Path("data/socratic.db")
    host: str = "0.0.0.0"
    port: int = 8885

    llm_provider: str = "openai-compatible"
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_api_key: str | None = None
    llm_timeout_seconds: int = 120

    retrieval_storage: Path = Path("data/retrieval")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_limit: int = 5
    retrieval_context_limit_chars: int = 2000

    orchestrator_max_tool_iterations: int = 5
    orchestrator_history_messages: int = 10
```

## Tabla completa de variables

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_STORAGE_PATH` | `data/socratic.db` | Ruta de la BD SQLite |
| `SOCRATIC_HOST` | `0.0.0.0` | Interfaz de escucha |
| `SOCRATIC_PORT` | `8885` | Puerto |
| `SOCRATIC_LLM_PROVIDER` | `openai-compatible` | Proveedor LLM |
| `SOCRATIC_LLM_BASE_URL` | `None` | URL del endpoint de completado (requerido en uso real) |
| `SOCRATIC_LLM_MODEL` | `gpt-4o-mini` | Nombre del modelo |
| `SOCRATIC_LLM_TEMPERATURE` | `0.0` | Temperatura |
| `SOCRATIC_LLM_API_KEY` | `None` | API key del proveedor |
| `SOCRATIC_LLM_TIMEOUT_SECONDS` | `120` | Timeout en segundos |
| `SOCRATIC_RETRIEVAL_STORAGE` | `data/retrieval/` | Ruta del índice vectorial |
| `SOCRATIC_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo de embeddings |
| `SOCRATIC_RETRIEVAL_LIMIT` | `5` | Máx. resultados por búsqueda |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | `2000` | Límite de contexto recuperado en `/ask` |
| `SOCRATIC_ORCHESTRATOR_MAX_TOOL_ITERATIONS` | `5` | Máx. iteraciones del bucle por Turn |
| `SOCRATIC_ORCHESTRATOR_HISTORY_MESSAGES` | `10` | Mensajes de historial reciente en el Turn |

## LLM (`socratic-server/src/socratic/llm/`)

### `base.py`

Protocolo `LLMClient` con dos métodos:

```python
class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...
    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...
```

- `LLMResponse(content: str, tool_calls: list[ToolCall])` con
  `has_tool_calls: bool`.
- `ToolCall(id, name, arguments_json)` (frozen).

### `openai_client.py`

`OpenAIClient(api_key=None, base_url=None, model="gpt-4o-mini",
temperature=0.0, timeout=120)`:

- Usa el SDK oficial `openai`.
- Compatible con cualquier API OpenAI-compatible (LiteLLM, Ollama,
  vLLM, etc.).
- `api_key` cae a `os.environ["OPENAI_API_KEY"]` si no se pasa.
- Cliente lazy (`_synced_client` property).
- `complete(messages, **kwargs)`: pasa `model` y `temperature`
  (sustituibles por kwargs).
- `complete_with_tools`: pasa `tools` y `tool_choice` solo si
  procede; procesa `message.tool_calls` y construye `ToolCall` con
  `tc.function.arguments or "{}"`.

## CLI (`socratic-cli/socratic_cli/main.py`)

URL configurable con `--url` o `SOCRATIC_URL` (default
`http://127.0.0.1:8885`).

```bash
socratic --url http://192.168.1.10:8885 documents
# o
SOCRATIC_URL=http://192.168.1.10:8885 socratic documents
```

## Importar configuración desde OpenCode

`socratic config import-opencode` lee
`~/.config/opencode/opencode.json` y genera las variables
`SOCRATIC_LLM_*`.

```bash
# Vista previa (formato systemd)
socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --print-env

# Exportar variables para la sesión actual
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

### Resolución de campos desde `opencode.json`

- `baseURL` (o `base_url`) en `provider.<name>.options`.
- `apiKey` (o `api_key_env`, que se resuelve desde el entorno) en
  `provider.<name>.options`.
- `timeout` en `provider.<name>.options` (si es `False` o `0` → 120).

### Advertencias

- La salida de `--print-env` **puede contener secretos** (API key). No
  la guardes en el repositorio ni en logs compartidos.
- Si no se resuelve la API key, se generan el resto de variables y se
  muestra un error por stderr.
- Si no se encuentra `baseURL`, la orden falla.

## main.py (servidor)

```python
settings = Settings()
app = create_app(settings.storage_path)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
```

`reload=True` significa que el módulo `main` se reimporta en cada
cambio de archivo. Cualquier `print` o efecto lateral a nivel de
módulo se ejecuta en cada reload.

> **Pendiente**: `config/settings.py` contiene `print(...)` de
> diagnóstico en `Settings.__init__` (commit `ffecead` "debug: añadir
> prints de diagnóstico en Settings para variables de entorno"). Es
> código, no documentación; debería limpiarse antes de producción.
