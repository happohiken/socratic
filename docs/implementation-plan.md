# Plan: Primer Hito Funcional de Socratic

## Objetivo

Validar el flujo completo en una primera versión pequeña:

1. Cargar un PDF.
2. Extraer su contenido como bloques ordenados.
3. Persistir el documento y sus bloques en SQLite.
4. Crear un estudio asociado al documento.
5. Solicitar el siguiente bloque.
6. Mostrar o leer el bloque en el cliente.
7. Confirmar que el bloque ha sido completado.
8. Hacer una pregunta sobre el bloque actual.
9. Enviar al LLM únicamente: bloque actual, pocos bloques anteriores, pregunta, historial reciente mínimo.
10. Recibir la respuesta.
11. Continuar la lectura desde la posición correcta.
12. Cerrar y reiniciar cliente y servidor, conservando el progreso.

---

## 1. Decisiones ya adoptadas

* Servidor en Python.
* API pública REST (sin WebSocket, SSE, gRPC ni streaming hasta que REST no pueda resolverlo).
* Cliente macOS inicial: CLI en Python que consume exclusivamente la API pública.
* Futuro cliente Android en Kotlin, consume la misma API.
* Flet descartado.
* SQLite desde la primera versión persistente (sin fase memoria → JSON).
* El servidor es la fuente de verdad del estado.
* TTS ejecutado en el cliente, no en el servidor.
* El servidor envía texto estructurado; el cliente sintetiza y reproduce.
* El cliente notifica al servidor cuándo ha completado la lectura de un bloque.
* Reanudación a nivel de bloque o párrafo completo (no a mitad de frase).
* LLM remoto detrás de una interfaz mínima propia.
* Primera versión: un único documento activo, una única conversación, un único estado de estudio.
* El modelo no debe impedir una ampliación posterior.

---

## 2. Hipótesis que aún requieren validación

1. **Librería de extracción de PDFs**: pdfplumber, PyMuPDF u otra. Se validará con 3-5 PDFs representativos (uno sencillo, uno académico de dos columnas, uno con listas/tablas/fórmulas, uno escaneado para confirmar que requiere OCR, y un documento real). Se registrarán errores concretos: orden incorrecto, encabezados/pies incluidos, palabras partidas, columnas mezcladas, bloques fusionados o divididos, fórmulas degradadas, tablas inutilizables.

2. **Estrategia de contexto del LLM**: El contexto inicial contiene solo instrucciones del sistema, bloque actual, dos o tres bloques anteriores, la pregunta y el historial reciente mínimo. Solo se añadirán resúmenes acumulados, estructura completa del documento o recuperación semántica si pruebas reales muestran que son necesarios.

3. **Proveedor LLM concreto**: OpenAI, Anthropic u otro. La interfaz mínima propia permite cambiarlo sin tocar la lógica de dominio.

4. **Tipo y tamaño de PDFs objetivo**: ¿Académicos? ¿Técnicos? ¿Textbooks largos? Esto afecta la elección de librería y la estrategia de contexto.

5. **Experiencia del equipo**: Confirma Python como lenguaje principal y afecta la velocidad de implementación.

---

## 3. Modelo conceptual mínimo

Entidades:

* **Document** — el PDF procesado.
  - id (estable, generada por el servidor).
  - filename.
  - pageCount.
  - formato (pdf inicialmente).
  - createdAt, updatedAt.

* **ContentBlock** — unidad mínima de lectura.
  - id (estable durante la vida de la representación persistida del documento, propia, independiente del ordinal).
  - documentId.
  - ordinal (para ordenar, no para identificar).
  - text.
  - pageNumber (del PDF original).
  - tipoAproximado: heading | paragraph | list | unknown.
  - metadata opcionales: coordenadas si la librería las proporciona, versión del parser.
  - Nota: no es necesario conservar el id si el documento se reprocesa con otra versión del parser.

* **Study** — estado de estudio de un documento.
  - id (estable).
  - documentId.
  - currentBlockId (identificador del bloque actual de lectura).
  - lastCompletedBlockId (último bloque marcado como completado).
  - createdAt, updatedAt.

* **Message** — mensaje de la conversación.
  - id.
  - studyId.
  - contentBlockId (opcional, asociado al bloque que originó la pregunta).
  - role: user | assistant.
  - content.
  - timestamp.

Relaciones:
- Document 1:N ContentBlock
- Document 1:1 Study (primera versión)
- Study 1:N Message

---

## 4. Arquitectura inicial mínima

```
socratic-server/
├── api/              # endpoints REST (FastAPI)
├── domain/           # modelos Document, ContentBlock, Study, Message
├── application/      # servicios de aplicación que coordinan API, persistencia, parser y LLM
├── storage/          # capa sencilla de persistencia SQLite (organización concreta al implementar)
├── pdf/              # extracción y construcción de bloques
├── llm/              # interfaz mínima + implementación concreta
└── config/           # configuración (SQLite path, LLM provider, etc.)

socratic-cli/
├── commands/         # cada comando mapea a una llamada API
└── main.py           # entry point (Typer o similar)
```

Capas:
1. **API** — expone REST, valida inputs, maneja errores. No contiene lógica de dominio.
2. **Dominio** — modelos y reglas. No sabe cómo se persiste ni cómo se comunica con el LLM.
3. **Application** — servicios de aplicación que coordinan API, persistencia, parser y LLM.
4. **Storage** — capa sencilla de persistencia SQLite, organizada según convenga al implementar.
5. **PDF** — extrae bloques del PDF y los convierte en entidades de dominio.
6. **LLM** — interfaz mínima (una clase `LLMClient` con un método `respond(context, question) -> str`) + implementación concreta.

Principios:
- El cliente es un thin view: solo envía comandos y muestra respuestas.
- El servidor es la fuente de verdad del estado.
- Los bloques tienen identificador estable propio (el ordinal ordena, pero no identifica).
- La posición de lectura referencia el identificador del bloque, no su ordinal.

---

## 5. API REST inicial

Endpoints necesarios (nombres provisionales, sujetos a cambio):

**Documentos:**
- `POST /documents` — cargar un PDF. Procesa y persiste bloques.
- `GET /documents` — listar documentos.
- `GET /documents/{id}` — consultar un documento (metadata, número de bloques).

**Estudios:**
- `POST /studies` — crear un estudio para un documento.
- `GET /studies` — listar estudios.
- `GET /studies/{id}` — consultar estado de un estudio (posición actual, último bloque completado).

**Lectura:**
- `GET /studies/{id}/current-block` — obtener el bloque actual pendiente de leer. No avanza la posición.
- `POST /studies/{id}/blocks/{blockId}/complete` — confirmar que el bloque actual ha sido completado. Avanza la posición al siguiente bloque.
- `GET /studies/{id}/current-block` — volver a obtener el bloque actual para repetir su contenido.

**Preguntas:**
- `POST /studies/{id}/ask` — enviar una pregunta sobre el bloque actual. El servidor compone contexto mínimo y llama al LLM.

Comportamiento:
- Los bloques se devuelven completos, no en chunks.
- El bloque actual no cambia al entregarlo.
- Una pregunta se formula sobre el bloque actual.
- Después de la respuesta, el bloque actual sigue siendo el mismo.
- La posición avanza únicamente cuando el cliente confirma que terminó de leer o reproducir el bloque.
- Después de una pregunta, el estudio permanece en el bloque interrogado hasta que se confirma la continuación.

---

## 6. Hitos pequeños y secuenciales

### Hito 1: Carga y extracción de PDF
Construir la estructura del servidor con FastAPI, definir los modelos de dominio, y crear la capa de persistencia SQLite. Integrar una librería PDF para extraer bloques ordenados de un PDF real y sencillo (una columna) y persistirlos. Endpoint `POST /documents` que acepte un PDF real, lo procese y lo guarde.

### Hito 2: Creación de estudio y lectura secuencial
Implementar los endpoints de estudio (crear, listar, consultar) y lectura (obtener bloque actual, confirmar completado, repetir bloque). La CLI debe poder: crear un estudio para un documento, obtener bloques secuenciales, marcarlos como completados, y repetir bloques.

### Hito 3: Reinicio y recuperación persistente
Verificar que cerrar y reiniciar servidor y CLI conserva el progreso:documento, bloques, estudio, bloque actual y último bloque completado.
Cuando ya existan mensajes, también deberá conservarse su historial.

### Hito 4: Pregunta contextual al LLM
Definir la interfaz mínima del LLM y una implementación concreta. Implementar el endpoint de pregunta que componga contexto mínimo (instrucciones del sistema, bloque actual, dos o tres bloques anteriores, pregunta, historial reciente breve) y devuelva la respuesta. La pregunta se formula sobre el bloque actual, que no cambia tras la respuesta.

### Hito 5: Validación del flujo completo
La CLI ejecuta el flujo completo con un PDF real: cargar PDF → crear estudio → leer bloques secuenciales → hacer una pregunta sobre el bloque actual → recibir respuesta → continuar lectura → cerrar y reiniciar → recuperar posición.

**Estado: completado.** Test en `socratic-cli/tests/test_full_flow.py`.

---

## 7. Criterios verificables para completar cada hito

**Hito 1**: Un PDF real y sencillo (una columna) se carga mediante `POST /documents`, se extraen bloques ordenados y se persisten en SQLite con texto legible y ordinal correcto.

**Hito 2**: La CLI puede crear un estudio, obtener bloques secuenciales, marcarlos como completados, y repetir bloques. La posición avanza únicamente al confirmar completado.

**Hito 3**: Cerrar y reiniciar servidor y CLI, consultar el estudio y confirmar que el bloque actual, último bloque completado e historial de mensajes se conservan.

**Hito 4**: La CLI puede enviar una pregunta sobre el bloque actual y recibir una respuesta relevante del LLM. El bloque actual no cambia tras la respuesta.

**Hito 5**: La CLI ejecuta el flujo completo con un PDF real: cargar PDF → crear estudio → leer bloques → hacer una pregunta sobre el bloque actual → recibir respuesta → continuar lectura → cerrar y reiniciar → recuperar posición.

---

## 8. Riesgos reales del primer flujo

1. **Calidad de extracción de PDFs reales**: pdfplumber/PyMuPDF pueden fallar en PDFs con fuentes embebidas no estándar, layouts complejos o documentos escaneados. Se validará con 3-5 PDFs representativos antes de fijar la librería.

2. **Identificación estable de bloques**: Los bloques detectados pueden no coincidir con los "lógicos" del documento. La reanudación puede parar en medio de un bloque. Se usa identificador estable propio, no el ordinal, para referenciar la posición.

3. **Contexto limitado del LLM**: Si el documento es largo, las preguntas sobre material lejano pueden no tener suficiente contexto. Se empieza con contexto mínimo (bloque actual + pocos anteriores + historial breve). Solo se ampliará si pruebas reales lo requieren.

4. **Reanudación después de interrupción**: Si el estado no se gestiona bien, la reanudación puede empezar en el bloque incorrecto. El servidor es la fuente de verdad y la posición se actualiza solo tras confirmar la continuación.

5. **Licencias de librerías PDF**: pdfplumber (MIT), PyMuPDF (AGPL o licencia comercial, no MIT), Marker (GPL-3.0, descartado). Se verifica la licencia antes de usar cualquier librería en producción.

---

## 9. Funcionalidades explícitamente aplazadas

* Aplicación Android.
* Interfaz gráfica (Flet descartado, CLI inicial).
* WebSocket, SSE, gRPC, streaming de texto/audio.
* TTS en el servidor, STT.
* RAG, embeddings, búsqueda vectorial.
* Resúmenes acumulados por párrafo.
* OCR.
* Procesamiento perfecto de tablas, capítulos y secciones.
* Múltiples conversaciones por documento, múltiples sesiones abiertas.
* Soporte multiusuario, autenticación avanzada, escalado distribuido.
* Múltiples proveedores de almacenamiento.
* CQRS, event buses, arquitectura basada en eventos.
* Abstracciones especulativas.
* Soporte de todos los formatos documentales.

---

## Reglas de simplicidad aplicadas

1. No crear una abstracción sin dos implementaciones reales o una necesidad demostrada.
2. No añadir infraestructura para una funcionalidad aplazada.
3. No introducir streaming hasta que exista un caso de uso que REST no pueda resolver.
4. No diseñar para escalado multiusuario antes de que exista esa necesidad.
5. No intentar resolver PDFs complejos antes de que funcione un PDF normal.
6. No añadir RAG hasta demostrar que el contexto local es insuficiente.
7. Cada hito debe producir un flujo utilizable de extremo a extremo.
8. Toda nueva capa debe explicar qué problema concreto resuelve.
9. Si una funcionalidad no es necesaria para completar el flujo PDF → leer → preguntar → continuar, queda fuera.

---

## Configuración del LLM

El servidor lee la configuración del LLM desde variables de entorno con prefijo `SOCRATIC_`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SOCRATIC_LLM_PROVIDER` | Proveedor (siempre `openai-compatible`) | `openai-compatible` |
| `SOCRATIC_LLM_BASE_URL` | URL del endpoint de completado | — (requerido) |
| `SOCRATIC_LLM_MODEL` | Nombre del modelo | `gpt-4o-mini` |
| `SOCRATIC_LLM_API_KEY` | Clave API del proveedor | — (requerido) |
| `SOCRATIC_LLM_TIMEOUT_SECONDS` | Timeout en segundos | `120` |

La CLI proporciona `socratic config import-opencode` para importar la configuración
desde `~/.config/opencode/opencode.json`:

- `--export-shell`: genera `export KEY='value'` para usar con `eval`.
- `--print-env`: genera `KEY=value` para copiar en systemd.
- `--provider <nombre>` y `--model <nombre>` para selección no interactiva.

Los dos modos son mutuamente excluyentes. Si falta alguno de los dos, la orden falla.

La API key se extrae directamente del campo `options.apiKey` de opencode.json.
Si no está disponible, se genera el resto de variables y se muestra un error por stderr.
