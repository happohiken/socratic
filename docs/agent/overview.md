# Visión general (agentes)

## Qué es Socratic

Aplicación de estudio interactivo: transforma un PDF en una conversación
guiada. El usuario recorre bloques de texto secuenciales, puede
interrumpir para preguntar, pedir aclaración, repetir o retroceder, y
continuar desde el punto exacto.

Filosofía: reproducir un profesor particular que mantiene el hilo de la
explicación. **No** es un chatbot sobre PDF arbitrario; prioriza la
continuidad de lectura y la comprensión progresiva.

## Componentes

| Ruta | Rol |
|---|---|
| `socratic-server/` | Servidor FastAPI: dominio, persistencia SQLite, parser PDF, LLM, RAG, orquestador. Fuente de verdad del estado. |
| `socratic-cli/` | Cliente CLI Python que consume la API REST. Thin view. |

No existe cliente macOS nativo todavía; la CLI es el facilitador de
desarrollo/pruebas.

## Flujo funcional mínimo (MVP cerrado)

```
PDF → procesamiento → lectura de bloque → pregunta → respuesta → reanudación
```

## Estado real (verificado en código)

Implementados y operativos:

- Carga y extracción de PDF (pdfplumber) → bloques en SQLite.
- Estudios con posición de lectura (`current_block_id`,
  `last_completed_block_id`).
- Reinicio y recuperación persistente.
- Pregunta contextual al LLM (`POST /studies/{id}/ask`).
- Recuperación documental con txtai + sentence-transformers
  (RAG opcional, ejecutado por el orquestador o por `/ask`).
- Orquestador conversacional con tool calling y un único LLM por Turn
  (`POST /studies/{id}/interact`).
- Eliminación de documentos en cascada.

**Pendiente / fuera de MVP**: cliente macOS, Android, audio (STT/TTS),
streaming, multiusuario, OCR, multidocumento activo, persistencia de
tool calls.

## Reglas de simplicidad (de `AGENTS.md`)

- No crear abstracción sin dos implementaciones reales o necesidad
  demostrada.
- No añadir infraestructura para funcionalidad aplazada.
- No introducir streaming hasta que exista caso de uso real.
- No diseñar para escalado multiusuario antes de necesitarlo.
- Cada hito debe producir un flujo pequeño, verificable y utilizable
  de extremo a extremo.
- Toda nueva capa, patrón o dependencia debe explicar qué problema
  concreto resuelve.

## Decisiones estructurales relevantes

- `src-layout` para evitar imports accidentales en tests.
- SQLite stdlib (no SQLAlchemy) — simplicidad.
- `check_same_thread=False` para FastAPI multi-hilo.
- `create_app(storage_path)` factory: permite tests de reinicio sobre
  la misma BD sin efectos al importar.
- `LLMClient` Protocol con `complete()` y `complete_with_tools()` —
  abstracción propia, no acoplada a proveedor.
- `DocumentRetriever` Protocol — backend de recuperación intercambiable.
- Orquestador independiente del protocolo (no importa FastAPI).

## Operaciones

- Servidor: `cd socratic-server && python -m main` (puerto 8885).
- Tests servidor: `cd socratic-server && python -m pytest tests/ -v`.
- Tests CLI: `cd socratic-cli && python -m pytest tests/ -v`.
- No hay comandos lint/typecheck configurados.

## Dónde encontrar qué

- Arquitectura del servidor: [architecture.md](architecture.md)
- Dominio y persistencia: [persistence.md](persistence.md)
- API REST: [api.md](api.md)
- Orquestador: [orchestrator.md](orchestrator.md)
- RAG: [retrieval.md](retrieval.md)
- Configuración: [config.md](config.md)
- CLI: [cli.md](cli.md)
