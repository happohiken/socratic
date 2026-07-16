# Socratic

Socratic es una aplicación de estudio interactivo que transforma cualquier documento PDF en una conversación guiada. Mientras recorres un PDF, puedes interrumpir la lectura para hacer preguntas, pedir aclaraciones, solicitar ejemplos o repetir fragmentos, y continuar exactamente donde te quedaste.

El sistema está formado por:

- **`socratic-server/`** — servidor FastAPI con la lógica de dominio, persistencia SQLite y extracción de PDFs.
- **`socratic-cli/`** — cliente CLI en Python que consume la API pública.

## Flujo básico

- **Lectura guiada**: PDF → procesamiento → lectura de bloques → pregunta contextual → respuesta → reanudación.
- **Conversacional**: el usuario habla con Socratic en lenguaje natural y un orquestador con un único LLM por Turn decide qué tools invocar (continuar, repetir, retroceder, recuperar contexto) para componer la respuesta. La recuperación documental (RAG) se ejecuta solo cuando el LLM lo solicita.

## Recuperación documental

El servidor indexa el documento completo para responder preguntas sobre cualquier
parte del texto, no solo el bloque actual.

```bash
# Indexar todos los documentos
socratic reindex

# Indexar un documento concreto
socratic reindex <document_id>

# Buscar bloques relevantes (diagnóstico)
socratic search-document <document_id> "consulta"
```

## Instalación y ejecución

### Requisitos

- Python 3.12+
- pip

### Pasos

```bash
# 1. Entrar en el directorio del servidor
cd socratic-server

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 4. Instalar dependencias (incluye dev)
pip install -e ".[dev]"

# 5. Ejecutar servidor
python -m main
```

El servidor escuchará en todas las interfaces de red. Accede desde:

- `http://127.0.0.1:8885` (local)
- `http://<IP-de-la-maquina>:8885` (desde la LAN)

Documentación interactiva: `http://<IP-de-la-maquina>:8885/docs` (Swagger UI).

### Ejecutar tests

```bash
cd socratic-server
python -m pytest tests/ -v
```

Los tests cubren:
- Subida de documentos PDF
- Listado de documentos
- Recuperación de detalle
- Manejo de errores (archivos no PDF, nombres vacíos)
- Persistencia en SQLite
- Creación de estudios
- Listado y consulta de estudios
- Obtención y avance de bloques
- Creación y consulta de mensajes
- **Reinicio del servidor y recuperación del estado** (documento, bloques, estudio, mensajes)
- **Eliminación de documentos** ( CASCADE a bloques, estudios y mensajes)
- **Orquestador conversacional**: registro de tools, bucle de Turn, detección de bucle infinito, persistencia de user/assistant (no tool calls)
- **Endpoint `/interact`**: Turn conversacional con tools de dominio y recuperación

## Cliente CLI

```bash
cd socratic-cli
# Usar el mismo venv que el servidor (comparte httpx) o crear uno propio
pip install -e .

# Arrancar el servidor (en otra terminal)
cd ../socratic-server && python -m main

# Flujo básico
socratic upload ruta/al.pdf
socratic documents
socratic create-study <document_id>
socratic current-block <study_id>
socratic complete-block <study_id> <block_id>
socratic next-block <study_id>          # obtiene, imprime y completa el bloque actual
socratic previous-block <study_id>      # retrocede al bloque anterior (actualiza current_block_id)
socratic message <study_id> "¿Pregunta?" --role user
socratic messages <study_id>
socratic ask <study_id> "¿Qué significa este término?"
socratic delete <document_id>

# Recuperación documental
socratic reindex [<document_id>]        # indexa todos o un documento concreto
socratic search-document <id> "consulta"  # diagnóstico de recuperación

# Inspeccionar la descomposición de un PDF sin subirlo al servidor
socratic inspect-pdf ruta/al.pdf [--format json] [--pages 1-5]
```

La URL del servidor se configura con `--url` o la variable de entorno `SOCRATIC_URL`
(default `http://127.0.0.1:8885`).

### Configuración del LLM

Para conectar el servidor con un proveedor compatible con OpenAI, importa la
configuración desde OpenCode:

```bash
# Vista previa (formato systemd)
socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --print-env

# Exportar variables para la sesión actual
eval "$(socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --export-shell)"

# Arrancar el servidor con las variables exportadas
socratic-server
```

Las variables que se generan son: `SOCRATIC_LLM_PROVIDER`, `SOCRATIC_LLM_BASE_URL`,
`SOCRATIC_LLM_MODEL`, `SOCRATIC_LLM_API_KEY`, `SOCRATIC_LLM_TIMEOUT_SECONDS`.

La salida de `--print-env` puede contener secretos (API key). No la guardes en el repositorio.

### Configuración de recuperación

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SOCRATIC_RETRIEVAL_STORAGE` | Ruta del índice vectorial | `data/retrieval/` |
| `SOCRATIC_EMBEDDING_MODEL` | Modelo de embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| `SOCRATIC_RETRIEVAL_LIMIT` | Máx. resultados por búsqueda | `5` |
| `SOCRATIC_RETRIEVAL_CONTEXT_LIMIT_CHARS` | Límite de contexto recuperado | `2000` |

### Configuración del orquestador

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SOCRATIC_ORCHESTRATOR_MAX_TOOL_ITERATIONS` | Máx. iteraciones del bucle de tool calling por Turn | `5` |
| `SOCRATIC_ORCHESTRATOR_HISTORY_MESSAGES` | Mensajes de historial reciente incluidos en el contexto | `10` |

El modelo se descarga la primera vez que se usa y se cachea.
El directorio `data/retrieval/` se excluye de Git.

Tests de la CLI (incluyen integración real con reinicio del servidor):

```bash
cd socratic-cli
python -m pytest tests/ -v
```

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/documents` | Cargar un PDF. Extrae bloques ordenados y los persiste. |
| GET | `/documents` | Listar documentos. |
| GET | `/documents/{id}` | Detalle de un documento y sus bloques. |
| DELETE | `/documents/{id}` | Eliminar un documento y todos sus asociados (bloques, estudios, mensajes). |
| POST | `/studies` | Crear estudio para un documento. |
| GET | `/studies` | Listar estudios. |
| GET | `/studies/{id}` | Consultar estado de un estudio. |
| GET | `/studies/{id}/current-block` | Obtener bloque actual sin avanzar. |
| POST | `/studies/{id}/blocks/{id}/complete` | Marcar bloque como completado y avanzar. |
| GET | `/studies/{id}/messages` | Obtener historial de mensajes. |
| POST | `/studies/{id}/messages` | Crear mensaje en el estudio. |
| POST | `/studies/{id}/ask` | Enviar pregunta al LLM sobre el bloque actual. Devuelve respuesta y guarda mensaje. |
| POST | `/studies/{id}/interact` | Iniciar un Turn conversacional. El orquestador decide qué tools invocar y compone la respuesta final. |
| POST | `/documents/{id}/reindex` | Indexar un documento para recuperación vectorial (202 Accepted). |
| POST | `/documents/{id}/search` | Buscar bloques relevantes en un documento indexado (diagnóstico). |

## Estructura del servidor

```
socratic-server/
├── src/socratic/            # Paquete principal (src-layout)
│   ├── app.py               # Factory create_app(storage_path)
│   ├── domain/              # Modelos (Document, ContentBlock, Study, Message)
│   ├── storage/             # Persistencia SQLite
│   ├── document_processing/ # Parser documental compartido (extractor + adapter)
│   ├── llm/                 # Interfaz LLM + implementación OpenAI (con tools)
│   ├── retrieval/           # Indexación y recuperación documental (txtai)
│   │   ├── models.py        # RetrievedBlock, DocumentRetriever, Context
│   │   ├── txtai_backend.py # TxtaiDocumentRetriever
│   │   └── service.py       # RetrievalService
│   ├── services/            # Servicios de aplicación compartidos por REST y tools
│   │   └── navigation.py    # NavigationService (obtener/completar/retroceder bloque)
│   ├── orchestrator/        # Orquestador conversacional (protocolo-agnóstico)
│   │   ├── registry.py      # @register_tool + ToolRegistry + esquemas desde anotaciones
│   │   ├── tools.py         # 4 tools: dominio (get/complete/previous_block) + recuperación
│   │   └── orchestrator.py  # Turn + bucle de tool calling + persistencia user/assistant
│   ├── api/                 # Endpoints REST
│   │   ├── documents.py     # Documentos
│   │   ├── studies.py       # Estudios y mensajes
│   │   ├── ask.py           # Preguntas contextuales (sin tools)
│   │   ├── interact.py      # Turn conversacional con tools
│   │   └── retrieval.py     # Reindex y búsqueda de diagnóstico
│   └── config/              # Configuración
├── main.py                  # Entry point FastAPI
├── tests/                   # Tests (document, study, persistence, retrieval, orchestrator)
├── data/                    # Base de datos SQLite + índice vectorial
└── pyproject.toml           # Dependencias y configuración
```

## Estado actual

Hito 1 completado: carga y extracción de PDFs con persistencia en SQLite.
Hito 2 completado: creación de estudio y lectura secuencial de bloques.
Hito 3 completado: reinicio y recuperación persistente — cerrar y reabrir servidor y CLI conserva documento, bloques, estudio (bloque actual y último completado) e historial de mensajes.
Hito 4 completado: pregunta contextual al LLM — el servidor compone un contexto mínimo (bloque actual, bloques anteriores, historial breve) y envía la pregunta a un modelo remoto. La respuesta se guarda en el historial sin avanzar la posición de lectura.
Hito 5 completado: validación del flujo completo — la CLI ejecuta el flujo extremo a extremo con un PDF real: cargar PDF → crear estudio → leer bloques → hacer pregunta contextual → recibir respuesta → continuar lectura → cerrar y reiniciar → recuperar posición.

Recuperación documental: módulo `socratic/retrieval/` con indexación vectorial (txtai + sentence-transformers). El contexto de `POST /studies/{id}/ask` incluye ahora 2 bloques anteriores, 2 siguientes y fragmentos recuperados del documento completo.

Orquestador conversacional: módulo `socratic/orchestrator/` con tool calling y un único LLM por Turn. El endpoint `POST /studies/{id}/interact` permite al usuario hablar en lenguaje natural; el LLM decide qué tools invocar (continuar, repetir, retroceder, recuperar contexto) y compone la respuesta final. Solo se persisten los mensajes user/assistant; los tool calls viven en memoria durante el Turn. Plan detallado en [docs/conversational-orchestrator-plan.md](docs/conversational-orchestrator-plan.md).

Plan completo: [docs/implementation-plan.md](docs/implementation-plan.md)
Contexto del producto: [docs/product-context.md](docs/product-context.md)
Metodología de documentación: [docs/documentation-methodology.md](docs/documentation-methodology.md)
API pública: [docs/api.md](docs/api.md)
Arquitectura del servidor: [docs/architecture.md](docs/architecture.md)
