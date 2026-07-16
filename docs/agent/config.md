# Configuración (agentes)

## Servidor (`socratic-server/src/socratic/config/settings.py`)

`Settings` (Pydantic BaseSettings) con prefijo `SOCRATIC_`, lee `.env`
si existe. Instanciado al importar tanto en `main.py` como en `app.py`.

| Variable | Default | Descripción |
|---|---|---|
| `SOCRATIC_STORAGE_PATH` | `data/socratic.db` | BD SQLite |
| `SOCRATIC_HOST` | `0.0.0.0` | Interfaz de escucha |
| `SOCRATIC_PORT` | `8885` | Puerto |
| `SOCRATIC_LLM_PROVIDER` | `openai-compatible` | Proveedor |
| `SOCRATIC_LLM_BASE_URL` | `None` | URL del endpoint (requerido en uso real) |
| `SOCRATIC_LLM_MODEL` | `gpt-4o-mini` | Modelo |
| `SOCRATIC_LLM_TEMPERATURE` | `0.0` | Temperatura |
| `SOCRATIC_LLM_API_KEY` | `None` | API key |
| `SOCRATIC_LLM_TIMEOUT_SECONDS` | `120` | Timeout LLM |
| `SOCRATIC_RETRIEVAL_STORAGE` | `data/retrieval/` | Índice vectorial |
| `SOCRATIC_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embeddings |
| `SOCRATIC_RETRIEVAL_LIMIT` | `5` | Resultados por búsqueda |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | `2000` | Límite chars RAG en `/ask` |
| `SOCRATIC_ORCHESTRATOR_MAX_TOOL_ITERATIONS` | `5` | Iteraciones del bucle |
| `SOCRATIC_ORCHESTRATOR_HISTORY_MESSAGES` | `10` | Mensajes de historial en Turn |

> **Nota**: `config/settings.py` contiene `print(...)` de diagnóstico en
> `__init__` (no deberían estar en producción). Es código, no
> documentación; fuera del alcance de `docs-init`.

## LLM (`socratic-server/src/socratic/llm/`)

- **`base.py`** — `LLMClient` Protocol con dos métodos:
  - `complete(messages, **kwargs) -> str` (sin tools; usado por `/ask`).
  - `complete_with_tools(messages, tools=None, *, tool_choice=None, **kwargs) -> LLMResponse`
    (con tools; usado por el orquestador).
  - `LLMResponse(content, tool_calls)` con `has_tool_calls`.
  - `ToolCall(id, name, arguments_json)` (frozen).
- **`openai_client.py`** — `OpenAIClient` usa el SDK oficial `openai`.
  Compatible con cualquier API OpenAI-compatible (LiteLLM, Ollama,
  vLLM, etc.). `api_key` cae a `OPENAI_API_KEY` si no se pasa. Cliente
  lazy (`_synced_client`).

## CLI (`socratic-cli/socratic_cli/main.py`)

URL configurable con `--url` o `SOCRATIC_URL` (default
`http://127.0.0.1:8885`).

## Importar config desde OpenCode

`socratic config import-opencode --provider <p> --model <m>`
(--export-shell | --print-env) lee `~/.config/opencode/opencode.json`,
extrae `baseURL`, `apiKey` (o `api_key_env`), `timeout` y genera las
variables `SOCRATIC_LLM_*`.

- `--export-shell`: `export KEY='value'` para `eval`.
- `--print-env`: `KEY=value` para systemd. **Puede contener secretos.**

## main.py (servidor)

```python
settings = Settings()
app = create_app(settings.storage_path)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
```

`reload=True` significa que el módulo `main` se reimporta en cada
cambio — los `print` de `Settings.__init__` se ejecutan en cada reload.
