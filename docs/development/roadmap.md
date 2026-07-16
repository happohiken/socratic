# Hoja de ruta

## Estado actual

Implementados y operativos (verificado en código y tests):

- **Hito 1**: Carga y extracción de PDFs con persistencia en SQLite.
- **Hito 2**: Creación de estudio y lectura secuencial de bloques.
- **Hito 3**: Reinicio y recuperación persistente — cerrar y reabrir
  servidor y CLI conserva documento, bloques, estudio (bloque actual y
  último completado) e historial de mensajes.
- **Hito 4**: Pregunta contextual al LLM (`POST /studies/{id}/ask`) —
  contexto mínimo (bloque actual, 2 anteriores, 2 siguientes,
  fragmentos RAG, historial breve). La respuesta se guarda en el
  historial sin avanzar la posición.
- **Hito 5**: Validación del flujo completo — la CLI ejecuta el flujo
  extremo a extremo con un PDF real. Test en
  `socratic-cli/tests/test_full_flow.py`.
- **Recuperación documental**: módulo `socratic/retrieval/` con
  indexación vectorial (txtai + sentence-transformers). El contexto de
  `/ask` incluye 2 bloques anteriores, 2 siguientes y fragmentos
  recuperados del documento completo, deduplicados.
- **Orquestador conversacional**: módulo `socratic/orchestrator/` con
  tool calling y un único LLM por Turn. Endpoint `POST /studies/{id}/interact`
  permite al usuario hablar en lenguaje natural; el LLM decide qué
  tools invocar (continuar, repetir, retroceder, recuperar contexto) y
  compone la respuesta final. Solo se persisten los mensajes
  user/assistant; los tool calls viven en memoria durante el Turn.

## Hitos históricos

| Commit | Hito |
|---|---|
| `e1d38fd` | Hito 3: persistencia y CLI (incluye Hito 1 y 2). |
| `9388bac` | Hito 4: integrar LLM y endpoint de pregunta contextual. |
| `4de9c58` | Hito 5: validación del flujo completo. |
| `49fd076` | Sustituir configuración ficticia del LLM por configuración funcional desde OpenCode. |
| `2560c9f` | `inspect-pdf` para diagnóstico de extracción. |
| `996a1a4` | Umbral dinámico de fusión de líneas y detección automática de cabeceras y pies. |
| `4a458ac` | Integrar parser documental común en `POST /documents`. |
| `d30c83e` | Actualizar README y arquitectura para parser compartido. |
| `a7b6d19` | Eliminación de documentos con cascada. |
| `3d2a31a` | Comandos CLI `next-block` y `previous-block`. |
| `13254f9` | Fix: `previous-block` actualiza `current_block_id`. |
| `163a207` | Agrupar `list_item` en nodos `list` y corregir bug de fusión. |
| `5779cb4` | Recuperación documental con txtai. |
| `197cd6f` | Actualizar plan con recuperación documental. |
| `50d91cb` | Actualizar READMEs con recuperación documental. |
| `dba8a2e` | Actualizar `api.md` y `architecture.md` con toda la funcionalidad. |
| `c7fa3af` | Orquestador conversacional con tool calling. |
| `9d8408b` | Track git de plans. |

## Hipótesis ya validadas

Las hipótesis del plan original se resolvieron así:

1. **Librería de extracción de PDFs**: pdfplumber (MIT), con pypdf
   opcional para TOC. Validado con PDFs de una columna; PDFs complejos
   (dos columnas, escaneados, tablas) fuera del MVP.
2. **Estrategia de contexto del LLM**: contexto local (bloque actual +
   2 anteriores + 2 siguientes) + RAG opcional (txtai). Validado en
   producción con el flujo `/ask` y el orquestador.
3. **Proveedor LLM**: interfaz propia `LLMClient` con `OpenAIClient`.
   Compatible con cualquier API OpenAI-compatible.
4. **Tipo y tamaño de PDFs objetivo**: documentos de una columna,
   texto-based, sin OCR. PDFs complejos fuera del MVP.
5. **Experiencia del equipo**: Python confirmado como lenguaje
   principal.

## Decisiones adoptadas (resumen)

- Servidor en Python con FastAPI.
- API pública REST (sin WebSocket, SSE, gRPC ni streaming hasta que
  REST no pueda resolverlo).
- Cliente macOS inicial sustituido por CLI en Python (facilitador de
  desarrollo/pruebas).
- Futuro cliente Android en Kotlin, consume la misma API.
- Flet descartado.
- SQLite desde la primera versión persistente.
- El servidor es la fuente de verdad del estado.
- TTS ejecutado en el cliente, no en el servidor (pendiente de
  implementar).
- Reanudación a nivel de bloque completo.
- LLM remoto detrás de interfaz propia.
- Primera versión: un único documento activo, una única conversación,
  una única sesión de estudio. El modelo no impide ampliación.

## Funcionalidades explícitamente aplazadas

- Aplicación Android.
- Interfaz gráfica (CLI inicial; Flet descartado).
- WebSocket, SSE, gRPC, streaming de texto/audio.
- TTS en el servidor, STT.
- Resúmenes acumulados por párrafo.
- OCR.
- Procesamiento perfecto de tablas, capítulos y secciones.
- Múltiples conversaciones por documento, múltiples sesiones abiertas.
- Soporte multiusuario, autenticación avanzada, escalado distribuido.
- Múltiples proveedores de almacenamiento.
- CQRS, event buses, arquitectura basada en eventos.
- Abstracciones especulativas.
- Soporte de todos los formatos documentales.
- Persistencia detallada de tool calls.
- Operaciones multidocumento desde el orquestador.

## Pendientes técnicos identificados

- **CLI no expone `/interact`**: el cliente CLI no tiene todavía un
  comando `interact`. Falta implementar `SocraticClient.interact()` y
  el comando correspondiente.
- **`print(...)` de debug en `config/settings.py`**: commit `ffecead`
  añadió diagnóstico en `Settings.__init__`. Debería limpiarse antes
  de producción.
- **`SOCRATIC_RETRIEVAL_LIMIT` no se aplica en `/ask`**: el default
  hardcoded en `RetrievalService.retrieve_context` es `5`; el endpoint
  `/ask` no lo lee de settings. Pendiente de unificar.
- **`AGENTS.md` desactualizado**: afirma "No hay código fuente aún".
  Debe corregirlo el usuario (fuera del alcance de `docs-init`).
- **`block_type` vacío en `/documents/{id}/search`**:
  `RetrievedBlockSummary.from_retrieved` inicializa `block_type=""`
  porque `RetrievedBlock` no incluye tipo. Mejora menor.

## Reglas de simplicidad aplicadas

1. No crear una abstracción sin dos implementaciones reales o una
   necesidad demostrada.
2. No añadir infraestructura para una funcionalidad aplazada.
3. No introducir streaming hasta que exista un caso de uso que REST no
   pueda resolver.
4. No diseñar para escalado multiusuario antes de que exista esa
   necesidad.
5. No intentar resolver PDFs complejos antes de que el flujo funcione
   correctamente con documentos sencillos y representativos.
6. No añadir RAG, embeddings ni recuperación semántica hasta demostrar
   que el contexto local es insuficiente. *(RAG se añadió tras
   demostrar la necesidad.)*
7. Cada hito debe producir un flujo pequeño, verificable y utilizable
   de extremo a extremo.
8. Toda nueva capa, patrón o dependencia debe explicar qué problema
   concreto resuelve.
9. Si una funcionalidad no es necesaria para completar el flujo
   PDF → leer → preguntar → continuar, queda fuera de la primera
   versión.
