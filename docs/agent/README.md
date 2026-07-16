# Documentación para agentes

Capa compacta y modular para que un agente de coding pueda localizar y
modificar el código con seguridad. Es autosuficiente para el trabajo
habitual; consulta `docs/development/` solo para profundizar o comprobar
coherencia.

Cargar bajo demanda el módulo relacionado con la tarea.

## Índice

| Módulo | Cuándo cargarlo |
|---|---|
| [overview.md](overview.md) | Siempre. Producto, filosofía, reglas, estado. |
| [architecture.md](architecture.md) | Tareas sobre estructura del servidor, capas, dependencias. |
| [persistence.md](persistence.md) | Tareas sobre dominio, SQLite, cascadas, invariantes. |
| [api.md](api.md) | Tareas sobre endpoints REST o contratos HTTP. |
| [orchestrator.md](orchestrator.md) | Tareas sobre Turn, tools, registro, bucle de tool calling. |
| [retrieval.md](retrieval.md) | Tareas sobre RAG, txtai, indexación, recuperación. |
| [config.md](config.md) | Tareas sobre settings, variables de entorno, LLM. |
| [cli.md](cli.md) | Tareas sobre el cliente CLI `socratic-cli/`. |

## Convenciones del repositorio

- Idioma: español en comunicación y documentación.
- Lenguaje: Python 3.11+.
- `src-layout` en el servidor (`socratic-server/src/socratic/`).
- El servidor es la fuente de verdad del estado. La CLI es un thin view.
- No modificar código en skills; la lógica vive en `.agentic/skills/`.
- Operaciones: tests con `pytest` (sin lint/typecheck configurados).
- `AGENTS.md` raíz es la entrada compacta; enruta a esta documentación.
