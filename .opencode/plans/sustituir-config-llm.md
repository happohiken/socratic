# Plan: Sustituir configuración ficticia del LLM por configuración funcional desde OpenCode

## Resumen

Añadir la orden CLI `socratic config import-opencode` que lee `~/.config/opencode/opencode.json`
y exporta variables de entorno para conectar Socratic con un proveedor compatible con OpenAI.

## Archivos a modificar

### Servidor (socratic-server/)

1. **src/socratic/config/settings.py** — Cambiar `BaseModel` → `BaseSettings` con prefijo `SOCRATIC_`.
   Añadir campos: `llm_provider`, `llm_base_url`, `llm_api_key`, `llm_timeout_seconds`.

2. **src/socratic/app.py** — Pasar `api_key`, `base_url` y `timeout` al crear `OpenAIClient`.

3. **src/socratic/llm/openai_client.py** — Añadir parámetro `timeout` al constructor y pasarlo a `OpenAI()`.

4. **pyproject.toml** — Añadir `pydantic-settings>=2.0,<3` a dependencies.

### CLI (socratic-cli/)

5. **socratic_cli/main.py** — Añadir subcomando `config import-opencode` con:
   - `--provider` (opcional, selección no interactiva)
   - `--model` (opcional, selección no interactiva)
   - `--export-shell` (modo 1: genera `export KEY='value'`)
   - `--print-env` (modo 2: genera `KEY=value`)

### Pruebas

6. **socratic-cli/tests/test_config_import_opencode.py** — Tests para:
   - lectura de opencode.json válido
   - selección de proveedor y modelo
   - proveedor inexistente
   - modelo inexistente
   - JSON inválido
   - generación correcta de `export`
   - generación correcta de `KEY=value`
   - escape seguro de valores shell
   - ausencia de mensajes adicionales en stdout con `--export-shell`
   - warning por stderr en `--print-env`

### Documentación

7. **docs/implementation-plan.md** — Añadir sección sobre `config import-opencode`.

## Limitaciones fuera de alcance

- No crear TOML de configuración propio.
- No lectura automática de OpenCode al arrancar el servidor.
- No soporte para múltiples proveedores simultáneos.
- No edición automática de unidades systemd.
- No almacenamiento de secretos.
- No integración con almacenes de credenciales externos.
