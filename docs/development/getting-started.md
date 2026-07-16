# Puesta en marcha

## Requisitos

- Python 3.11+ (verificado en `pyproject.toml`: `requires-python = ">=3.11"`).
- pip.
- Para tests: pytest 8+, httpx, fpdf2, uvicorn.

## Servidor

```bash
cd socratic-server

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Instalar dependencias (incluye dev para tests)
pip install -e ".[dev]"

# (Opcional) Soporte de extracción de TOC con pypdf
pip install -e ".[pdf]"

# Ejecutar servidor (puerto 8885, reload activado)
python -m main
```

El servidor escucha en `0.0.0.0:8885` (accesible desde la LAN).
Swagger UI en `http://127.0.0.1:8885/docs`.

> **Nota**: el comando de arranque es `python -m main` desde
> `socratic-server/`. `pyproject.toml` no define `[project.scripts]`
> para el servidor.

## Cliente CLI

```bash
cd socratic-cli

# Reutiliza el venv del servidor (comparte httpx) o crea uno propio
pip install -e .

# Para tests
pip install -e ".[dev]"

socratic --help
```

## Tests

### Servidor

```bash
cd socratic-server
python -m pytest tests/ -v
```

Cobertura actual (ver `tests/`):
- `test_document.py` — subida, listado, detalle, errores (no PDF, nombre vacío).
- `test_study.py` — estudios, mensajes, avance de bloques.
- `test_persistence.py` — reinicio y recuperación del estado.
- `test_ask.py` — endpoint `/ask` con StubLLM.
- `test_orchestrator.py` — bucle de Turn, detección de bucle, persistencia.
- `test_orchestrator_tools.py` — las 4 tools.
- `test_registry.py` — registro de tools vía decorador.
- `test_retrieval.py` — indexación y recuperación.
- `test_llm.py` — `StubLLM` y `ScriptedLLM` para tests.
- `test_interact.py` — endpoint `/interact`.

### CLI

```bash
cd socratic-cli
python -m pytest tests/ -v
```

Los tests de la CLI levantan el servidor real con `uvicorn` en un hilo
sobre una BD temporal, ejecutan el flujo completo vía CLI, reinician el
servidor sobre la misma BD y verifican recuperación. **Requieren el
paquete `socratic-server` instalado** en el entorno (la CLI importa
`parse_pdf` y `create_app`).

## Configuración del LLM (necesaria para `/ask` y `/interact`)

Sin `SOCRATIC_LLM_BASE_URL` y `SOCRATIC_LLM_API_KEY`, los endpoints que
llaman al LLM fallarán en runtime. Ver [config.md](config.md) para
todas las variables y la importación desde OpenCode.

## Datos persistentes

- `socratic-server/data/socratic.db` — base SQLite (fuente de verdad).
- `socratic-server/data/retrieval/` — índice vectorial txtai (reconstruible).
- Ambos excluidos de Git (`.gitignore`).

## Reinicio y recuperación

`create_app(storage_path)` inicializa la BD al construirla (no en
lifespan), permitiendo que los tests con `ASGITransport` tengan
`app.state.db` sin disparar startup. Cerrar y reabrir el servidor
sobre la misma ruta conserva documentos, bloques, estudios y mensajes.
