# Documentación para desarrolladores

Capa técnica completa y autosuficiente para comprender, mantener y
ampliar el proyecto. No requiere consultar `docs/agent/` ni
`docs/user/`.

## Índice

| Documento | Contenido |
|---|---|
| [getting-started.md](getting-started.md) | Instalación, entorno, ejecución, tests. |
| [product-context.md](product-context.md) | Intención del producto, filosofía, alcance. |
| [architecture.md](architecture.md) | Estructura del servidor, capas, responsabilidades. |
| [domain-and-persistence.md](domain-and-persistence.md) | Modelo de dominio y SQLite. |
| [pdf-processing.md](pdf-processing.md) | Parser documental: extractor, classifier, adapter, formatters. |
| [api.md](api.md) | Referencia completa de la API REST. |
| [orchestrator.md](orchestrator.md) | Orquestador conversacional: Turn, tools, registro, bucle. |
| [retrieval.md](retrieval.md) | RAG con txtai: indexación, recuperación, configuración. |
| [config.md](config.md) | Variables de entorno, settings, importación desde OpenCode. |
| [decisions.md](decisions.md) | Decisiones arquitectónicas y sus razones. |
| [roadmap.md](roadmap.md) | Hitos históricos y pendientes. |

## Cómo contribuir

- Operaciones: `pytest` (sin lint/typecheck configurados todavía).
- Mantener la documentación sincronizada con el código: las skills
  `commit-work` y `docs-update` revisan cambios desde el último
  baseline en `.agentic.lock.json`.
- Idioma: español.
- No modificar la lógica de skills desde los wrappers en `.claude/` o
  `.opencode/`; la fuente única es `.agentic/skills/`.
