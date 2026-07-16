# Decisiones arquitectónicas

Lista de decisiones relevantes con su justificación. Orden
aproximadamente cronológico.

## Lenguaje y framework

- **Python 3.11+** para servidor y CLI: velocidad de implementación,
  ecosistema de PDFs y LLMs, tipado razonable.
- **FastAPI**: framework async ligero, OpenAPI automático, inyección
  de dependencias con `Depends`,广泛adopción.
- **CLI con argparse + httpx sync**: sin frameworks de CLI para
  minimizar dependencias. El servidor es la fuente de verdad y la CLI
  es un thin view.

## Persistencia

- **sqlite3 stdlib** en vez de SQLAlchemy: simplicidad para MVP. CRUD
  manual con `sqlite3.Connection`.
- **`check_same_thread=False`**: permite usar la misma conexión SQLite
  en hilos asíncronos de FastAPI.
- **`PRAGMA journal_mode=WAL`**: mejora concurrencia de lectura.
- **`PRAGMA foreign_keys=ON`**: activa `ON DELETE CASCADE` para que
  borrar un documento propague a bloques, estudios y mensajes.
- **`UNIQUE(document_id, ordinal)`**: evita duplicados accidentales de
  bloques al re-procesar.

## Identificadores

- **UUID** para todos los IDs (Document, ContentBlock, Study, Message):
  compatible con API pública, distribuido, sin colisiones.
- **`ContentBlock.ordinal` ordena, no identifica**: la posición de
  lectura referencia el `id` UUID, no el ordinal. Permite
  reordenamientos y reprocesamientos sin perder la posición.

## Estructura del proyecto

- **`src-layout`**: estándar en proyectos Python profesionales. Evita
  que tests y herramientas usen el paquete sin instalar. Múltiples
  versiones del mismo paquete en el mismo entorno.
- **Factory `create_app(storage_path)`**: separa la construcción de la
  app del entry point. Permite tests de reinicio sobre la misma BD sin
  efectos secundarios al importar. La BD se inicializa al construir la
  app (no en lifespan) para que los tests con `ASGITransport` tengan
  `app.state.db` sin disparar startup.

## PDF

- **pdfplumber** en vez de PyMuPDF: licencia MIT (PyMuPDF es AGPL o
  comercial), bueno para PDFs de una columna. Soporta info de fuentes,
  bbox.
- **pypdf opcional** (extra `pip install -e ".[pdf]"`): solo para
  extraer TOC desde `reader.outline`. Si no está instalado, se omite el
  TOC.
- **`parse_pdf(path, page_range=None)` compartido** entre
  `POST /documents` y `socratic inspect-pdf`: una sola implementación
  del parser, dos superficies de uso.

## LLM

- **`LLMClient` Protocol**: abstracción mínima propia. No acopla a un
  proveedor concreto. Dos métodos: `complete()` (sin tools, para
  `/ask`) y `complete_with_tools()` (con tools, para el orquestador).
- **`OpenAIClient`**: implementación que usa el SDK oficial `openai`.
  Compatible con cualquier API OpenAI-compatible (LiteLLM, Ollama,
  vLLM, etc.).
- **Cliente lazy**: el cliente `OpenAI` se construye en el primer uso
  (`_synced_client` property), no en `__init__`.
- **`api_key` cae a `OPENAI_API_KEY`**: si no se pasa explícitamente.

## Recuperación documental

- **txtai** para recuperación: índice vectorial ligero, persistencia en
  disco, filtrado SQL por `tags` (document_id).
- **`DocumentRetriever` Protocol**: abstracción mínima que permite
  cambiar el motor de búsqueda en el futuro sin modificar
  `RetrievalService` ni los endpoints.
- **SQLite fuente de verdad, txtai reconstruible**: borrar
  `data/retrieval/` es seguro; se reconstruye con `reindex`.
- **`upsert` en indexación**: idempotente, seguro ante reindexaciones.
- **`sentence-transformers/all-MiniLM-L6-v2`**: multilingüe, ~23 MB,
  Apache 2.0, default de txtai.
- **Deduplicación por `block_id`**: evita fragmentos duplicados en el
  contexto combinado (local + RAG).
- **RAG ejecutado por el LLM**: el orquestador no ejecuta RAG siempre;
  lo hace solo cuando el LLM invoca `retrieve_document_context`. No hay
  clasificador externo.

## Orquestador

- **Un único LLM por Turn**: no existe un segundo LLM de respuesta.
  Las tools devuelven datos estructurados; el LLM compone la respuesta
  final.
- **Independiente del protocolo**: el orquestador no importa FastAPI ni
  `starlette`. Recibe objetos de dominio y devuelve texto. Reutilizable
  desde CLI, REST, WebSocket, Android y tests.
- **Mismo mecanismo para todas las tools**: no hay categorías técnicas
  distintas. La diferencia entre tools de dominio y de recuperación es
  semántica, no técnica.
- **Decorador + introspección de firma + Pydantic**: mínimo boilerplate
  para registrar tools. El esquema se deriva de las anotaciones de
  tipo. Validación en runtime. Evita escribir esquemas JSON a mano.
- **`TurnContext` mutable dentro del Turn**: las tools de dominio que
  avanzan la posición actualizan `study` y `current_block` para que
  las siguientes tools del mismo Turn vean el estado actualizado.
- **No persistir tool calls**: solo se persisten mensajes `user` y
  `assistant` finales. Los tool calls viven en memoria y se registran
  en `TurnResult.tool_calls` para depuración.
- **Endpoint `/interact` junto a `/ask`** (alternativa A del plan):
  mantener `/ask` para compatibilidad con la CLI textual existente y
  añadir `/interact` para el flujo conversacional con tools. Transición
  gradual.

## API

- **HTTP/REST** (sin WebSocket, SSE, gRPC ni streaming): decisión
  inicial. El protocolo se escogió según necesidades reales, no por
  analogía. Streaming aplazado hasta que exista caso de uso (audio,
  cancelación, latencia perceptible).
- **`POST /documents` con `multipart/form-data`**: subida directa del
  PDF, procesamiento síncrono, respuesta con documento y bloques.
- **`POST /studies/{id}/ask` sin tools**: composición imperativa del
  prompt (system → bloque actual → anteriores → siguientes → RAG →
  historial → pregunta). Llamada única al LLM. Mantenido durante la
  transición al orquestador.
- **`POST /studies/{id}/interact` capa fina HTTP ↔ orquestador**:
  valida entrada, obtiene estudio, delega en
  `orchestrator.interact(study, input)`. Toda la lógica está en el
  orquestador.
- **`POST /documents/{id}/reindex` devuelve 202 Accepted**: la
  indexación es síncrona pero se mantiene el código 202 por
  convención.

## Cliente CLI

- **Thin view**: la CLI solo envía comandos y muestra respuestas. El
  servidor es la fuente de verdad.
- **`inspect-pdf` reutiliza `parse_pdf` del servidor**: requiere el
  paquete `socratic-server` instalado en el entorno. Permite
  diagnosticar la descomposición documental sin subir el PDF.
- **`config import-opencode`**: integra con la configuración existente
  de OpenCode en `~/.config/opencode/opencode.json`. Genera variables
  para systemd o para shell.

## Configuración

- **Pydantic Settings**: configuración externalizada via variables de
  entorno con prefijo `SOCRATIC_`. Lee `.env` si existe.
- **`create_app` recibe `storage_path` y `llm_client`**: permite a los
  tests inyectar un `StubLLM` o `ScriptedLLM` y apuntar a una BD
  temporal.

## Lo que se aplazó explícitamente

- Streaming (hasta caso de uso real).
- WebSocket, SSE, gRPC.
- Multiusuario, autenticación, escalado distribuido.
- OCR, tablas, fórmulas.
- Múltiples conversaciones por documento, múltiples sesiones abiertas.
- Persistencia detallada de tool calls.
- Cliente macOS nativo, Android.
- Audio: STT, TTS, captura, formatos, transporte, buffering.
- Operaciones multidocumento desde el orquestador.
- MCP (no se adopta por analogía).
