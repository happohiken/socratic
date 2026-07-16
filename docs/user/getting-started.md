# Puesta en marcha

## Requisitos

- Python 3.11 o superior.
- pip.
- Un proveedor LLM accesible por API HTTP compatible con OpenAI
  (OpenAI, LiteLLM, Ollama, vLLM, etc.) con su API key.

## Instalar el servidor

```bash
cd socratic-server

# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 2. Instalar dependencias (incluye dev para tests)
pip install -e ".[dev]"

# 3. (Opcional) Soporte de extracción de TOC con pypdf
pip install -e ".[pdf]"
```

## Configurar el LLM (necesario para preguntar y conversar)

Sin `SOCRATIC_LLM_BASE_URL` y `SOCRATIC_LLM_API_KEY`, los endpoints que
llaman al LLM fallarán. La forma más rápida de configurarlos es
importarlos desde OpenCode:

```bash
cd socratic-cli
pip install -e .

# Vista previa (formato systemd)
socratic config import-opencode --provider <nombre> --model <nombre> --print-env

# Exportar variables para la sesión actual
eval "$(socratic config import-opencode --provider <nombre> --model <nombre> --export-shell)"
```

Ver [configuration.md](configuration.md) para todas las variables.

## Arrancar el servidor

```bash
cd socratic-server
python -m main
```

El servidor escucha en `0.0.0.0:8885`:

- Local: `http://127.0.0.1:8885`
- LAN: `http://<IP-de-la-maquina>:8885`
- Swagger UI: `http://127.0.0.1:8885/docs`

> El comando de arranque es `python -m main` desde `socratic-server/`.
> No existe un comando `socratic-server` instalable.

## Instalar la CLI

```bash
cd socratic-cli
# Reutiliza el venv del servidor o crea uno propio
pip install -e .
```

## Primer PDF, primer estudio

En otra terminal (con el servidor corriendo):

```bash
# 1. Subir un PDF
socratic upload ruta/al.pdf
# → document_id  <uuid>

# 2. (Recomendado) Indexar para recuperación documental
socratic reindex <document_id>

# 3. Crear un estudio
socratic create-study <document_id>
# → study_id  <uuid>

# 4. Leer el primer bloque
socratic current-block <study_id>

# 5. Avanzar al siguiente bloque (obtiene, imprime y completa)
socratic next-block <study_id>

# 6. Retroceder
socratic previous-block <study_id>

# 7. Preguntar sobre el bloque actual
socratic ask <study_id> "¿Qué significa este término?"

# 8. Ver historial de mensajes
socratic messages <study_id>
```

## Cerrar y reanudar

El estado se persiste en SQLite. Puedes cerrar el servidor y la CLI, y
reanudar más tarde:

```bash
cd socratic-server
python -m main
# El estado (documentos, estudios, mensajes) se conserva.

socratic studies              # ver estudios disponibles
socratic current-block <study_id>   # seguir donde se dejó
```

## Ver también

- [cli-reference.md](cli-reference.md) — todos los comandos.
- [configuration.md](configuration.md) — configuración completa.
- [workflows.md](workflows.md) — flujos típicos.
- [troubleshooting.md](troubleshooting.md) — errores frecuentes.
