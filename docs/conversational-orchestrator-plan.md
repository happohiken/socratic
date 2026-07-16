# Plan del Orquestador Conversacional

> Documento arquitectónico. No contiene código de implementación, salvo
> ejemplos ilustrativos mínimos. No decide detalles de implementación.
> Define responsabilidades, flujos, decisiones, alternativas y riesgos.
>
> Este documento se centra **exclusivamente** en el orquestador
> conversacional. La arquitectura de audio (captura, STT, TTS,
> reproducción, formatos, transporte, buffering) se diseñará en un
> documento posterior. Aquí solo se fija la frontera cliente/servidor,
> sin decidir dónde se ejecutan STT y TTS.

## Objetivo

Evolucionar Socratic desde un sistema basado en **comandos explícitos**
(obtener bloque, completar, preguntar, retroceder…) hacia un
**sistema conversacional** en el que el usuario simplemente habla con
Socratic y es el propio LLM, dentro del servidor, quien decide
continuamente qué acciones invocar para satisfacer la intención del
usuario.

El usuario no debería distinguir entre "hacer una pregunta",
"continuar leyendo", "repetir un párrafo" o "volver atrás": todo se
resuelve mediante **tool calling** sobre mecanismos registrados por el
servidor.

### Principios rectores

1. **Un único LLM por turno.** No existe un segundo LLM de respuesta.
   Las herramientas nunca generan la respuesta al usuario; solo
   recuperan información, modifican el estado o devuelven datos
   estructurados. El LLM compone la respuesta final.
2. **Las tools representan operaciones del dominio o recuperaciones de
   información, no capacidades del LLM.** Las tools existen para
   acceder al mundo exterior o modificar el estado. El LLM ya sabe
   resumir, traducir o razonar; no hay tools para eso. Ejemplos
   correctos: `complete_current_block()`, `previous_block()`,
   `retrieve_document_context(query)`. Ejemplos incorrectos:
   `summarize()`, `translate()`, `answer_question()`, `reason()`.
3. **El servidor es la única fuente de verdad** del estado de lectura y
   de la conversación.
4. **El LLM decide qué tool usar**; el servidor no clasifica
   intenciones con reglas, árboles ni palabras clave.
5. **El cliente no interpreta intención**: es la interfaz con el usuario
   (captura sus interacciones y reproduce la respuesta). La ubicación
   de STT y TTS se decide en otro documento.
6. **Cada tool tiene un propósito concreto**, nunca un
  `execute(command)` genérico.
7. **Las tools no contienen lógica de negocio**: delegan en los
   servicios de aplicación ya existentes. Nunca acceden a la
   persistencia directamente.
8. **El orquestador es independiente del protocolo.** No conoce REST,
   HTTP ni FastAPI. Recibe objetos de dominio (el `Study`, la entrada
   del usuario) y devuelve una respuesta del asistente. Esto permite
   reutilizarlo desde CLI, REST, WebSocket, Android y tests sin tocarlo.
9. **Un único mecanismo de tool calling.** No hay categorías técnicas
   distintas de tools. Todas las tools —de dominio o de recuperación—
   utilizan exactamente el mismo registro, validación y ejecución. La
   diferencia entre categorías es únicamente **semántica**.
10. **Complejidad mínima**: no se introducen capas, módulos ni
    abstracciones sin un problema concreto que resolver. Toda decisión
    que pueda posponerse hasta que aparezca un caso real se pospone.

### Fuera del alcance

- Arquitectura de audio (STT, TTS, captura, formatos, transporte) y
  decisión de dónde se ejecutan STT y TTS.
- Exposición de las tools vía MCP.
- Implementación. Este documento es previo a cualquier código.
- Streaming, multiusuario, escalado distribuido.
- Persistencia detallada del razonamiento del orquestador (tool calls).
- Operaciones multidocumento (listar/cambiar documentos o estudios).

---

## Resumen previo al diseño

### Cómo funciona actualmente el flujo de preguntas

El flujo se inicia con un comando explícito de la CLI
(`socratic ask <study_id> "..."`) que llama a
`POST /studies/{id}/ask` (`socratic-server/src/socratic/api/ask.py`):

1. Obtiene el estudio y el bloque actual (400 si no hay bloque actual).
2. Llama a `RetrievalService.retrieve_context()`, que devuelve un
   `Context` con `local_blocks` (actual + 2 anteriores + 2 siguientes) y
   `retrieved_blocks` (hasta 5 fragmentos por RAG, deduplicados).
3. Construye el prompt **imperativamente y en orden fijo**:
   system → bloque actual → anteriores → siguientes → RAG → historial
   (últimos 4) → pregunta. Inserta mensajes `assistant` ficticios para
   forzar la alternancia user/assistant.
4. Llama **una sola vez** a `LLMClient.complete(messages) -> str`.
5. Persiste dos `Message` (user + assistant) y devuelve el texto.

La posición de lectura no se modifica tras una pregunta.

### Limitaciones del flujo actual

- **Sin tool calling**: `LLMClient.complete(messages) -> str` no acepta
  `tools` ni devuelve `tool_calls`. `OpenAIClient` filtra los kwargs y
  solo pasa `model` y `temperature`.
- **Sin composición de acciones**: "explica esto y luego continúa"
  requiere dos peticiones manuales.
- **Sin estado de turno**: cada `ask` reconstruye el contexto desde cero.
- **Cliente y usuario deben conocer comandos**: cada acción es un
  endpoint distinto.
- **Composición de prompt rígida**: el orden y la estructura del
  contexto viven en el endpoint, no en un componente reutilizable.

### Por qué evolucionar hacia un orquestador basado en herramientas

- **Naturalidad**: el usuario habla libre y el LLM decide qué hacer.
- **Eliminación de comandos especiales** y de toda lógica de intención
  en el cliente.
- **Composición**: el LLM encadena acciones en un mismo turno.
- **Cohesión con la filosofía del producto**: reproduce un profesor
  particular que mantiene el hilo de la explicación.
- **Estabilidad**: el servidor sigue siendo la fuente de verdad; solo
  cambia el protocolo de interacción.

---

## 1. Flujo conversacional completo

### El concepto de Turn

Toda la lógica del orquestador gira en torno al concepto de **Turn**
(turno). Un `Turn` es la unidad de interacción completa entre el
usuario y el asistente. No se persiste; vive solo en memoria mientras
se ejecuta. Conceptualmente:

```
Turn
  ├── entrada del usuario (texto)
  ├── tool calls solicitados por el LLM (0..N)
  ├── resultados de esos tool calls (datos estructurados)
  └── respuesta final del asistente (texto)
```

El orquestador construye un `Turn`, lo ejecuta, persiste únicamente la
entrada del usuario y la respuesta final, y descarta el resto.

### Turno de extremo a extremo

```
Entrada del usuario (texto)
  → Orquestador construye el contexto inicial del Turn:
      system prompt + estado + bloque actual + historial reciente + tools
  → LLM razona
  → ¿Solicita tools?
      Sí → orquestador valida argumentos y ejecuta
         → la tool devuelve datos estructurados
         → los datos se inyectan en el Turn
         → LLM razona de nuevo
      No → genera respuesta textual final
  → Orquestador persiste únicamente los mensajes user y assistant
  → Devuelve la respuesta final
```

### Dos categorías semánticas de tools

Todas las tools utilizan **exactamente el mismo mecanismo técnico** de
registro, validación y ejecución. La diferencia entre categorías es
únicamente semántica:

1. **Tools de dominio**: representan operaciones del dominio. Consultan
   o modifican el estado del estudio.
   - `get_current_block()`
   - `complete_current_block()`
   - `previous_block()`

2. **Tools de recuperación**: permiten al LLM recuperar información
   externa a su contexto inmediato **sin modificar el dominio**.
   - `retrieve_document_context(query)`

En el futuro podrán existir otras tools de recuperación (búsqueda web,
calendario, etc.), pero no se diseñan todavía.

### Flujo en turnos de navegación

El usuario dice "continúa". El LLM sabe que no necesita contexto
documental: llama directamente a la tool de dominio y responde.

```
LLM
  ↓
complete_current_block()
  ↓
resultado estructurado (nuevo bloque actual)
  ↓
LLM genera la respuesta final
```

No se ejecuta RAG. El Turn es muy corto.

### Flujo en turnos de pregunta

El usuario pregunta "¿qué significa odds ratio?". El LLM detecta que
necesita contexto documental y lo solicita mediante la tool de
recuperación.

```
LLM
  ↓
retrieve_document_context(query="¿qué significa odds ratio?")
  ↓
fragmentos documentales estructurados
  ↓
el mismo LLM genera la respuesta final
```

Un único LLM durante todo el Turn. La tool de recuperación no responde,
no construye narrativa, no llama a ningún LLM: solo devuelve fragmentos.

### Flujo en turnos combinados

El usuario dice "explícamelo y luego continúa". El LLM encadena una
tool de recuperación y una tool de dominio en el mismo Turn.

```
LLM
  ↓
retrieve_document_context(...)
  ↓
contexto documental
  ↓
complete_current_block()
  ↓
nuevo bloque actual
  ↓
el mismo LLM genera la respuesta final
```

### Características clave del flujo

- **Un único LLM** durante todo el Turn.
- **Las tools no responden al usuario**: devuelven datos estructurados.
  El LLM redacta la respuesta final a partir de esos datos y del
  contexto.
- **Un único mecanismo de tool calling** para todas las tools, de
  dominio o de recuperación.
- **El RAG no es una tool especial**: es una tool de recuperación que
  utiliza el mismo pipeline que las demás.
- **Los tool calls no se persisten**: viven solo en el `Turn` y, si
  resulta útil, en logging estructurado (sección 7).

### Casos representativos

- **Pregunta sobre el bloque actual o sobre el documento**: el LLM llama
  a `retrieve_document_context(query)` y responde con los fragmentos
  recuperados. El estado no cambia.
- **Petición de continuar**: el LLM llama a `complete_current_block()`.
  La tool avanza la posición y devuelve el nuevo bloque. El LLM puede
  relatar su texto en la respuesta final. Sin RAG.
- **Petición de repetir**: el LLM llama a `get_current_block()` y
  devuelve su texto. La posición no cambia. Sin RAG.
- **Petición de volver atrás**: el LLM llama a `previous_block()`. La
  tool retrocede y devuelve el nuevo bloque actual. Sin RAG.
- **Petición combinada ("explica esto y luego continúa")**: el LLM
  llama a `retrieve_document_context(...)` y responde la pregunta; a
  continuación llama a `complete_current_block()` para avanzar. Todo en
  el mismo `Turn`.
- **Intervención no comprensible**: el LLM no solicita tools y pide
  reformulación. El estado no se altera.

### Interrupciones y reanudación

- La interrupción de reproducción es responsabilidad del cliente; para
  el servidor simplemente empieza un nuevo `Turn`.
- Si cae el cliente, el estado del estudio queda intacto en el servidor
  y se reanuda al reconectarse.
- Si cae el servidor a mitad de `Turn`, los mensajes ya persistidos
  permanecen; el `Turn` interrumpido se considera abortado y el cliente
  puede reintentar. No hay garantía de exactly-once en esta versión.

### Límites del Turn

- Máximo de iteraciones del bucle por `Turn`: **configurable**.
- Detección de bucle infinito (misma tool con mismos argumentos
  repetida sin progreso).
- Timeout global heredado del LLM.

---

## 2. Registro de herramientas

### Requisitos

- Registrar herramientas Python sin escribir esquemas JSON a mano.
- Generar automáticamente nombre, descripción y esquema de argumentos.
- Validar en runtime los argumentos que devuelve el LLM.
- Serializar el resultado a JSON.
- Superficie mínima: un decorador y un registro central.
- **Un único mecanismo** para todas las tools, sin distinción técnica
  entre tools de dominio y de recuperación.

### Alternativas evaluadas

| Enfoque | Ventajas | Inconvenientes |
|---|---|---|
| **Decorador + introspección de firma + Pydantic en runtime** | Mínimo boilerplate; esquema derivado de anotaciones; validación robusta | Requiere anotaciones consistentes |
| Un modelo Pydantic por tool | Validación muy robusta | Más clases, más boilerplate |
| Dataclasses como esquema | Ligero, stdlib | Tipado pobre; validación manual |
| Registro manual de esquemas JSON | Control total | Error-prone; se desincroniza con la firma |

### Recomendación

**Decorador + introspección de firma + validación Pydantic en runtime.**

- El decorador `@register_tool(name=..., description=...)` registra la
  función en un diccionario central.
- El esquema de argumentos se deriva de las anotaciones de tipo.
- La validación se realiza con Pydantic antes de ejecutar la función.
- El resultado se serializa: `dict` tal cual; modelo Pydantic con
  `model_dump()`; `str` envuelto en `{"text": ...}`.

Es la opción que minimiza la superficie sin renunciar a validación.
Pydantic ya está presente en el servidor (FastAPI, settings). Los
modelos Pydantic por tool se descartan: la validación en runtime cubre
el mismo problema con menos código.

### Restricciones comunes a todas las tools

- Cada tool tiene un propósito concreto (operación del dominio o
  recuperación de información).
- Las tools no contienen lógica de negocio: delegan en servicios de
  aplicación.
- Las tools no acceden a la persistencia directamente.
- Las tools no generan respuestas para el usuario: devuelven datos
  estructurados.
- Las tools no llaman al LLM.
- Las tools no exponen credenciales ni datos sensibles.
- El docstring alimenta la descripción que el LLM usa para decidir.

---

## 3. Herramientas iniciales

### Set inicial de tools

La primera versión incluye cuatro tools, distribuidas en dos categorías
semánticas. Todas comparten el mismo mecanismo técnico.

#### Tools de dominio

Operaciones que consultan o modifican el estado del estudio.

| Tool | Descripción | Justificación |
|---|---|---|
| `get_current_block()` | Devuelve texto y metadatos del bloque actual. | Permite repetir o referenciar el bloque en curso sin avanzar. |
| `complete_current_block()` | Marca el bloque actual como completado y avanza al siguiente. | Permite continuar la lectura. |
| `previous_block()` | Retrocede al bloque anterior. | Permite revisar contenido previo. |

#### Tools de recuperación

Recuperan información externa al contexto inmediato del LLM sin
modificar el dominio.

| Tool | Descripción | Justificación |
|---|---|---|
| `retrieve_document_context(query)` | Recupera fragmentos documentales relevantes para la consulta. | Permite al LLM acceder a contenido del documento más allá del bloque actual. Reutiliza el `RetrievalService` existente. |

### Nombres declarativos

Los nombres de las tools de dominio son **declarativos respecto a la
unidad de lectura actual** (bloque), no atan a una unidad fija: si en
el futuro la unidad de lectura pasa a ser span, frase o sección, los
nombres siguen expresando la intención ("current", "complete",
"previous") sin presuponer un tamaño concreto.

### Sin parámetros innecesarios

Las tools de dominio **no reciben identificadores internos** (`block_id`,
`current_block_id`, `last_completed_block_id`). El contexto del Turn ya
conoce el estudio activo y el bloque actual; el orquestador se los
proporciona a la tool al ejecutarla. El LLM ve tools sin argumentos
requeridos:

```
get_current_block()
complete_current_block()
previous_block()
```

La tool de recuperación recibe **únicamente** la consulta del usuario:

```
retrieve_document_context(query: str)
```

El estudio activo y el documento no son argumentos generados por el
LLM: el orquestador los obtiene del contexto de ejecución. La tool
recibe solo la `query`.

### Qué devuelven

- `get_current_block()` → el bloque actual (id, ordinal, texto, página,
  tipo).
- `complete_current_block()` → el nuevo bloque actual tras avanzar (o
  una indicación de fin de documento si no hay más bloques).
- `previous_block()` → el nuevo bloque actual tras retroceder (o un
  error si ya se está en el primero).
- `retrieve_document_context(query)` → los fragmentos documentales
  recuperados por `RetrievalService`, como datos estructurados (id de
  bloque, ordinal, página, texto, score).

Todas devuelven **datos estructurados**, nunca texto dirigido al
usuario. El LLM decide qué hacer con esos datos al componer la
respuesta final.

### Requisitos específicos de `retrieve_document_context`

Arquitectónicamente, esta tool:

- recibe **únicamente** la consulta (`query`) como argumento del LLM;
- obtiene el estudio activo y el documento desde el **contexto de
  ejecución** del orquestador, no desde argumentos generados por el LLM;
- devuelve **datos estructurados** (fragmentos documentales);
- reutiliza el `RetrievalService` existente, sin modificarlo;
- **no modifica** el estado del estudio;
- **no persiste** nada;
- **no construye narrativa** ni responde al usuario;
- **no llama al LLM**.

### Tools descartadas para la primera versión

| Operación | Decisión | Razón |
|---|---|---|
| `ask_question` | Eliminada | Implicaba un segundo LLM de respuesta. El LLM único responde directamente usando el contexto recuperado por `retrieve_document_context`. |
| `list_documents`, `list_studies`, `switch_study` | Aplazadas | Pertenecen a una futura versión multidocumento. |
| `next_block` (obtener + completar) | No es tool | Se compone: el LLM llama a `complete_current_block()` y usa el bloque devuelto. |
| `summarize`, `translate`, `reason` | No son tools | Son capacidades del LLM, no operaciones del dominio ni recuperaciones de información (principio #2). |
| `reindex`, `search`, `create_study`, `upload_document` | No son tools | Son operaciones de mantenimiento/configuración; se mantienen como endpoints REST. |

---

## 4. Organización del código

### Estructura mínima

```
socratic-server/
└── src/socratic/
    ├── domain/              # Sin cambios
    ├── storage/             # Sin cambios
    ├── llm/                 # Refactor: ampliar interfaz para tools
    ├── retrieval/           # Sin cambios (usado por retrieve_document_context)
    ├── document_processing/ # Sin cambios
    ├── config/              # Sin cambios
    ├── api/                 # Endpoints de gestión sin cambios
    │   ├── documents.py
    │   ├── studies.py
    │   ├── ask.py           # Se mantiene durante la transición
    │   ├── retrieval.py
    │   └── interact.py      # NUEVO (si se adopta /interact)
    ├── orchestrator/        # NUEVO
    │   ├── orchestrator.py  # Fachada: contexto + bucle + persistencia
    │   ├── registry.py      # @register_tool + catálogo + esquemas
    │   └── tools.py         # Las 4 tools (dominio + recuperación)
    └── app.py               # Monta el orquestador en app.state
```

### Responsabilidades

- **`registry.py`**: decorador `@register_tool`, diccionario central y
  funciones de consulta (`list_tools()`, `get_tool(name)`). No conoce
  lógica de dominio. No distingue técnicamente entre categorías de
  tools.
- **`tools.py`**: implementaciones de las cuatro tools. Son adaptadores
  finos que delegan en servicios de aplicación (`RetrievalService`, y el
  servicio de navegación extraído de `api/studies.py`). No contienen
  lógica de negocio.
- **`orchestrator.py`**: fachada. Construye el `Turn` (contexto
  inicial), ejecuta el bucle de tool calling, inyecta resultados,
  persiste los mensajes user/assistant y devuelve la respuesta final.
  Es el único punto de entrada del orquestador.

### El orquestador es independiente del protocolo

El orquestador **no conoce REST, HTTP ni FastAPI**. No recibe
`Request` ni devuelve `Response`. Recibe objetos de dominio (el
`Study`, la entrada del usuario como texto) y devuelve una respuesta
del asistente (texto +, opcionalmente, metadatos). Toda la lógica de
HTTP, validación de entrada HTTP, serialization JSON y manejo de
errores de transporte vive en la capa `api/`, no en el orquestador.

Esto permite reutilizar el orquestador desde CLI, REST, WebSocket,
Android y tests sin tocar una línea de su código.

### Por qué solo tres módulos

La construcción del contexto, el bucle de tools y la persistencia viven
en `orchestrator.py`. No se extraen a `context.py`, `loop.py` o
`dispatcher.py` hasta que un problema concreto lo justifique. Si
`orchestrator.py` crece hasta dejar de ser navegable, se podrá extraer
la pieza responsable; no antes. Ídem para un hipotético `dispatcher.py`:
la validación y ejecución de tools puede vivir en `orchestrator.py`
mientras el número de tools sea cuatro.

### Integración en `app.state`

`app.state` ya contiene `db`, `llm`, `retrieval`. Se añade:

- `app.state.orchestrator` — instancia del orquestador.

El orquestador recibe en su constructor las dependencias (`db`, `llm`,
`retrieval`) y las reenvía a las tools en cada ejecución junto con el
contexto del Turn (estudio activo, bloque actual). Las tools no leen
`app.state` directamente: reciben lo que necesitan.

### Las tools delegan en servicios de aplicación

Flujo correcto:

```
LLM → Tool → Application Service → Domain → Storage
```

Nunca:

```
LLM → Tool → SQLite
```

- **Recuperación documental**: `retrieve_document_context` reutiliza
  `RetrievalService.retrieve_context()` tal cual. No se modifica
  `RetrievalService`.
- **Navegación** (obtener/completar/retroceder bloque): la lógica hoy
  vive inline en `api/studies.py`. Se extrae a pequeñas funciones de
  servicio reutilizadas **tanto por los endpoints REST como por las
  tools**. Esto evita duplicar lógica y garantiza que las tools no toquen
  la persistencia directamente.

La extracción de ese servicio de navegación es la única refactorización
de dominio necesaria. No se introduce una capa de servicios genérica:
solo las funciones concretas que las tools necesitan.

---

## 5. Construcción del contexto

### Qué recibe el LLM en cada Turn

El contexto se construye en `orchestrator.py` y se envía como una lista
de mensajes:

1. **System prompt del orquestador**: rol (profesor particular que guía
   la lectura), reglas (no inventar tools, no repetir la misma tool sin
   progreso, usar `retrieve_document_context` solo cuando la pregunta
   requiera contexto más allá del bloque actual) y las tools
   disponibles (nombre, descripción, esquema de argumentos).
2. **Estado del estudio**: documento activo, bloque actual (texto +
   metadatos mínimos), posición de lectura.
3. **Historial conversacional reciente**: últimos N mensajes user /
   assistant del estudio (recomendado N=10).
4. **Intervención actual**: el texto del usuario.
5. **Definición de tools**: pasada como parámetro `tools` de la llamada
   al LLM, no como texto del system prompt.
6. **Resultados de tools anteriores del mismo Turn**: cada resultado se
   añade como mensaje `tool` con el nombre de la tool y el resultado
   serializado. Estos mensajes viven solo en memoria del Turn; no se
   persisten.

### El RAG se ejecuta a petición del LLM, vía tool calling

El RAG no se ejecuta siempre. El LLM decide si necesita contexto
documental y, en caso afirmativo, llama a
`retrieve_document_context(query)`. El orquestador ejecuta la tool, que
invoca a `RetrievalService.retrieve_context(study, current_block,
query)` y devuelve los fragmentos recuperados como datos estructurados.

**No hay clasificador externo.** El LLM es quien enruta, de forma
natural, mediante su razonamiento. Esto:

- evita recuperaciones inútiles en turnos de pura navegación
  ("continúa", "repite", "vuelve atrás");
- no introduce reglas, árboles ni palabras clave en el servidor;
- mantiene el RAG como una tool más, sin mecanismo técnico especial.

### Cómo se ejecuta `retrieve_document_context`

1. El LLM llama a `retrieve_document_context(query=...)`.
2. El orquestador obtiene el estudio activo y el documento desde el
   contexto de ejecución (no son argumentos del LLM).
3. La tool invoca
   `RetrievalService.retrieve_context(study, current_block, query)`.
4. Los fragmentos recuperados (locales + RAG, deduplicados por
   `block_id`) se devuelven como datos estructurados al LLM.
5. El LLM continúa razonando con ese contexto y produce la respuesta
   final.

`RetrievalService` no se modifica: se reutiliza tal cual. El
orquestador no duplica su lógica de deduplicación ni de ventana de
bloques.

### Cómo continúa el bucle después de una tool

1. El orquestador valida los argumentos y ejecuta la tool (de dominio o
   de recuperación, indistintamente).
2. El resultado se añade al `Turn` como mensaje `tool`.
3. Se reenvía al LLM el contexto actualizado (system + estado +
   historial del estudio + resultados de tools del Turn).
4. El LLM decide: más tools, o respuesta final.

### Cuándo termina el Turn

- El LLM genera una respuesta textual sin solicitar más tools.
- Se alcanza el límite máximo de iteraciones (configurable).
- Se detecta un bucle infinito.
- Se agota el timeout global.

### Límites aplicados

- Máximo de llamadas a tools por Turn: **configurable**.
- Máximo de mensajes de historial: recomendado 10.
- Límite de caracteres de fragmentos RAG: el ya existente
  (`retrieval_context_limit_chars`, hoy hardcoded; debería leerse de
  settings).
- Timeout global: el ya existente del LLM.

### Deduplicación

- El bloque actual se incluye una sola vez en el contexto inicial.
- Los fragmentos devueltos por `retrieve_document_context` se
  deduplican por `block_id` respecto a los bloques locales
  (comportamiento ya existente en `RetrievalService`).
- El historial se trunca a los últimos N mensajes.

---

## 6. API pública

Se comparan alternativas. **No se decide aún.** La entrada al
orquestador es texto (el audio queda fuera de este documento).

### Alternativa A: mantener `/ask` y añadir `/interact`

- Se conserva `POST /studies/{id}/ask` para compatibilidad con la CLI
  textual.
- Se añade `POST /studies/{id}/interact` para el flujo conversacional
  con tools.

**Ventajas**: transición gradual; la CLI sigue funcionando sin cambios.
**Inconvenientes**: dos vías para "preguntar"; riesgo de
desincronización; mantenimiento dual.

### Alternativa B: sustituir por `/interact` unificado

- Se elimina o delega `/ask`.
- Un único `POST /studies/{id}/interact` recibe el texto del usuario y
  devuelve la respuesta final del orquestador.

**Ventajas**: un solo punto de entrada; cliente más simple; alineado con
"el usuario no distingue acciones".
**Inconvenientes**: rompe la CLI existente; mayor latencia por Turn.

### Alternativa C: esquema separado envío/consulta

- `POST /studies/{id}/interact` inicia el Turn y devuelve un
  `turn_id`.
- `GET /studies/{id}/interact/{turn_id}` consulta el resultado.

**Ventajas**: turnos largos sin bloquear; compatible con streaming
futuro.
**Inconvenientes**: más endpoints; el cliente gestiona polling.

### Comparativa

| Criterio | A (coexistencia) | B (unificado) | C (separado) |
|---|---|---|---|
| Simplicidad para el cliente | Media | Alta | Baja |
| Latencia percibida | Baja | Alta | Media |
| Idempotencia | Buena | Media | Buena |
| Cancelación | Buena | Media | Buena |
| Compatibilidad con CLI actual | Muy buena | Baja | Media |
| Evolución a streaming | Buena | Muy buena | Muy buena |
| Coste de mantenimiento | Alto | Bajo | Medio |

### Decisiones pendientes

- Si la CLI textual mantiene `/ask` o migra a `/interact`.
- Si se introduce streaming (recomendable aplazar, según `AGENTS.md`).

---

## 7. Relación con el sistema actual

### Componentes que se reutilizan directamente

| Componente | Estado | Notas |
|---|---|---|
| `domain/models.py` (`Document`, `ContentBlock`, `Study`, `Message`) | Reutilizar directo | Sin cambios. `Message` sigue con `role` user/assistant. |
| `storage/database.py` | Reutilizar directo | Sin cambios. No se persisten tool calls. |
| `retrieval/service.py` (`RetrievalService.retrieve_context`) | Reutilizar directo | `retrieve_document_context` lo invoca tal cual. |
| `retrieval/txtai_backend.py` | Reutilizar directo | Sin cambios. |
| `document_processing/` | Reutilizar directo | Sin cambios. |
| `api/documents.py`, `api/retrieval.py` | Reutilizar directo | Sin cambios. |
| `config/settings.py` | Reutilizar directo | Posibles nuevas settings de límites. |

### Componentes que se refactorizan

| Componente | Cambio | Razón |
|---|---|---|
| `llm/base.py` (`LLMClient`) | Ampliar la interfaz para aceptar `tools` y devolver `tool_calls` | La interfaz actual no soporta tool calling. |
| `llm/openai_client.py` (`OpenAIClient`) | Pasar `tools`/`tool_choice` y procesar `tool_calls` en la respuesta | Hoy filtra kwargs y solo lee `content`. |
| `api/studies.py` | Extraer la lógica de `complete_block`/`previous_block`/`current-block` a funciones de servicio reutilizables | Para que las tools las invoquen sin tocar SQLite y sin duplicar lógica. |
| `api/ask.py` | La composición del prompt pasa al orquestador; `/ask` puede delegar en el orquestador o mantenerse durante la transición | El orquestador asume la composición del contexto. |

### Componentes que desaparecen o quedan obsoletos

| Componente | Destino | Razón |
|---|---|---|
| `pdf/parser.py` (legacy) | Eliminar | Ya marcado como pendiente de eliminación. |
| Composición imperativa del prompt en `ask.py` | Sustituida por el orquestador | El orquestador construye el contexto. |
| Mensajes `assistant` ficticios en el prompt | Desaparecen | Eran un truco para forzar alternancia; el orquestador no los necesita. |

### Componentes nuevos

| Componente | Rol |
|---|---|
| `orchestrator/orchestrator.py` | Fachada: contexto + bucle + persistencia. Protocolo-agnóstico. |
| `orchestrator/registry.py` | Registro de tools (único mecanismo para todas). |
| `orchestrator/tools.py` | Las 4 tools (dominio + recuperación): adaptadores finos sobre servicios. |
| Servicio de navegación (extraído de `api/studies.py`) | Lógica de obtener/completar/retroceder bloque, compartida por REST y tools. |
| `api/interact.py` (si se adopta `/interact`) | Endpoint conversacional; traduce HTTP ↔ orquestador. |

### Sobre la persistencia de tool calls

**No se modifica el modelo de persistencia en esta versión.** Solo se
persisten los mensajes `user` y `assistant` finales del Turn, igual que
hoy. Los `tool_calls`, sus argumentos y sus resultados viven solo en
memoria durante el Turn y, si resulta útil para depuración, se
registran mediante **logging estructurado**. La persistencia detallada
del razonamiento del orquestador podrá estudiarse más adelante, cuando
existan casos reales que la necesiten (depuración profunda, auditoría,
reproducción de turnos).

---

## 8. Frontera cliente/servidor

Este documento **no decide dónde se ejecutan STT y TTS.** La única
frontera fijada en esta fase es:

- el **cliente** captura las interacciones del usuario y reproduce la
  respuesta;
- el **servidor** contiene el estado, el orquestador, el LLM, el RAG y
  las tools.

La ubicación definitiva de STT y TTS se decidirá en un documento
específico de arquitectura de audio.

### Qué viaja por la red en el nivel de texto

- Cliente → servidor: texto de la intervención del usuario + identificador
  del estudio.
- Servidor → cliente: texto de la respuesta final.

El resto (captura, transcripción, síntesis, reproducción, formatos,
transporte de audio) queda fuera de este documento.

---

## 9. Decisiones pendientes, riesgos y criterios de aceptación

### Decisiones pendientes

1. **Endpoint API**: `/ask` + `/interact` (A), `/interact` unificado (B)
   o esquema separado (C). Ver sección 6.
2. **CLI textual**: si mantiene `/ask` o migra a `/interact`.
3. **Límites configurables**: valor concreto del máximo de tools por
   Turn, del número de mensajes de historial y de si las políticas hoy
   hardcoded (ventana de bloques, límite de RAG) se mueven a settings.
4. **Extracción de módulos del orquestador**: `context`/`loop`/
  `dispatcher` se extraen de `orchestrator.py` solo si este deja de ser
   navegable. No antes.
5. **Streaming**: aplazado según `AGENTS.md`; reabrir si la latencia lo
   exige.
6. **Persistencia detallada de tool calls**: aplazada (ver sección 7).
7. **Arquitectura de audio y ubicación de STT/TTS**: aplazada a otro
   documento.

### Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El LLM llama a tools en bucle o sin progreso | Turn infinito, coste elevado | Límite de iteraciones configurable; detección de repetición; tests |
| El LLM responde sin llamar a `retrieve_document_context` cuando lo necesitaba | Respuestas poco fundadas | System prompt claro; tests de comportamiento |
| El LLM llama a `retrieve_document_context` en turnos de navegación | Recuperaciones innecesarias | Aceptable; el coste es bajo y el LLM aprende del prompt; no se añade gating externo |
| Regresión en `/ask` al refactorizar `LLMClient` | CLI existente rota | Mantener `/ask` operativo; tests de regresión |
| Duplicación entre endpoints REST y tools | Mantenimiento doble | Extraer lógica común al servicio de navegación compartido |

### Criterios de aceptación

- Un usuario puede hacer una pregunta sobre el bloque actual y recibir
  respuesta sin invocar ningún comando explícito.
- Un usuario puede pedir continuar, repetir o retroceder con lenguaje
  natural; el LLM invoca la tool adecuada.
- Un usuario puede encadenar dos acciones ("explica esto y luego
  continúa") en un único Turn.
- El estado del estudio se actualiza exclusivamente a través de tools de
  dominio, y nunca de forma inconsistente con el flujo REST existente.
- El historial de mensajes user/assistant persiste tras reiniciar el
  servidor.
- El orquestador respeta el límite máximo de iteraciones y detecta
  bucles infinitos.
- Las tools se registran mediante decorador, sin escribir esquemas JSON
  a mano.
- Las tools no importan de `storage/`: delegan en servicios de
  aplicación.
- Todas las tools (dominio y recuperación) utilizan el mismo mecanismo
  de registro, validación y ejecución.
- El orquestador no importa de FastAPI ni de `starlette`: es
  independiente del protocolo.
- `retrieve_document_context` no modifica el estado, no persiste, no
  construye narrativa y no llama al LLM.
- Solo se persisten mensajes user y assistant; los tool calls no se
  persisten.

---

## Resumen

Este documento propone una evolución arquitectónica de Socratic hacia
un **orquestador conversacional basado en tool calling con un único
LLM por Turn**. Las tools representan **operaciones del dominio o
recuperaciones de información, no capacidades del LLM**: solo consultan
o modifican el estado, o devuelven datos estructurados. El LLM compone
la respuesta final.

Hay dos categorías semánticas de tools, que comparten **exactamente el
mismo mecanismo técnico**:

- **Tools de dominio**: `get_current_block`, `complete_current_block`,
  `previous_block`.
- **Tools de recuperación**: `retrieve_document_context(query)`.

La recuperación documental (RAG) no es un mecanismo especial: es una
tool de recuperación que el LLM invoca cuando juzga que necesita
contexto más allá del bloque actual. No se ejecuta siempre, ni por un
clasificador externo: el propio LLM decide.

El orquestador vive en tres módulos (`orchestrator.py`, `registry.py`,
`tools.py`), es **independiente del protocolo** (no conoce REST, HTTP
ni FastAPI) y delega en los servicios de aplicación ya existentes, sin
tocar la persistencia directamente. Toda su lógica gira en torno al
concepto de **Turn**, una unidad transitoria (no persistida) que
modela la entrada del usuario, los tool calls, sus resultados y la
respuesta final. No se persisten tool calls: solo mensajes
user/assistant. El diseño de audio y la ubicación de STT/TTS quedan
fuera; solo se fija la frontera cliente/servidor.
