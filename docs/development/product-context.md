# Contexto del producto

## Propósito

Socratic es una aplicación de estudio interactivo que permite recorrer
un documento PDF u otros formatos de forma secuencial, pudiendo leerlo
visualmente, escucharlo mediante síntesis de voz o combinar ambas
modalidades, e interrumpirla para hacer preguntas, pedir aclaraciones,
solicitar ejemplos o volver a escuchar fragmentos anteriores.

Tras resolver una interrupción, la lectura debe poder continuar desde
el punto exacto donde se detuvo.

## Filosofía

Socratic **no** pretende responder preguntas sobre un documento de
forma aislada. Su objetivo es reproducir la experiencia de estudiar
con un profesor particular que explica un texto de forma secuencial,
permite interrupciones naturales y mantiene el hilo de la explicación
durante toda la sesión.

El sistema prioriza la continuidad de la lectura y la comprensión
progresiva frente a responder preguntas descontextualizadas sobre
cualquier parte del documento.

## Arquitectura prevista

El sistema tendrá inicialmente dos componentes:

1. Un **servidor** que contendrá la lógica principal.
2. Un **cliente de desarrollo para macOS** (actualmente sustituido por
   la CLI en Python como facilitador de desarrollo y pruebas).

Cuando el flujo básico sea funcional, se desarrollará una aplicación
Android. Desde ese momento, el servidor y el cliente Android
evolucionarán en paralelo.

El cliente macOS/CLI **no** es necesariamente el producto final. Su
función inicial es facilitar el desarrollo, las pruebas y la
validación del protocolo cliente-servidor.

## Responsabilidades del servidor

- Recibir y procesar documentos PDF.
- Construir una representación estructurada independiente del formato.
- Identificar capítulos, secciones, párrafos y, cuando sea necesario,
  otras unidades de lectura.
- Gestionar el estado persistente del estudio de cada documento.
- Conservar un puntero estable a la posición actual.
- Atender comandos de lectura, pausa, reanudación y navegación.
- Construir el contexto necesario para responder preguntas.
- Comunicarse con un LLM remoto detrás de una abstracción propia.
- Permitir reanudar la lectura después de una pregunta.
- Diseñarse para soportar posteriormente un cliente Android.

## Flujo funcional mínimo

1. El usuario carga un documento.
2. El servidor procesa el documento y construye una representación
   estructurada.
3. El servidor genera los índices necesarios para la navegación y
   recuperación de contexto.
4. El usuario inicia la lectura.
5. El servidor entrega el siguiente fragmento de lectura.
6. El usuario puede interrumpir para: hacer una pregunta, pedir
   aclaración, solicitar un ejemplo, repetir el párrafo actual,
   repetir el párrafo anterior o continuar la lectura.
7. El servidor responde utilizando el contexto documental pertinente.
8. La lectura se reanuda desde la posición correcta.

## Gestión documental

No debe asumirse que el documento completo cabrá en la ventana de
contexto del LLM.

El sistema representa los documentos mediante unidades identificables y
estables (documento, capítulo, sección, párrafo, fragmento). Cada
unidad puede referenciarse mediante un identificador estable. La
posición de lectura **no** depende únicamente de offsets de caracteres
o páginas del PDF.

La estrategia de contexto combina:

- el fragmento actual;
- fragmentos inmediatamente anteriores y siguientes;
- el contexto estructural del capítulo o sección;
- un resumen acumulado;
- fragmentos relevantes recuperados del documento (RAG);
- el historial reciente de la conversación.

La estrategia concreta se decide durante el diseño y evoluciona con el
sistema.

## Estado de lectura

El servidor es la fuente de verdad del estado de la sesión. Como
mínimo, una sesión debe poder representar: documento activo, posición
actual, último párrafo leído, punto de interrupción, estado de lectura,
historial de preguntas relevante e información necesaria para
reanudar.

Siempre que sea posible, el estado persistido contiene únicamente la
información mínima necesaria para reconstruir el estado completo,
evitando datos redundantes.

## Múltiples documentos y conversaciones activas

Socratic debe permitir mantener varios documentos PDF abiertos de forma
simultánea. El usuario debe poder:

- Cargar y conservar varios documentos.
- Cambiar de un documento a otro.
- Mantener una o varias conversaciones asociadas a cada documento.
- Recuperar el historial relevante de cada conversación.
- Reanudar la lectura de cada documento desde el punto exacto.
- Mantener diferentes líneas de estudio sobre un mismo documento sin
  mezclar su contexto.

El modelo conceptual distingue entre `Document`, `Conversation`,
`Reading Session` y `Reading Position`. Un mismo documento podrá tener
varias conversaciones independientes (estudiar el mismo PDF desde
perspectivas distintas, reiniciar el estudio sin perder progreso).

> **Estado actual**: el modelo implementado tiene `Document`, `Study`
> (asumido 1:1 con conversación por ahora), `ContentBlock` y `Message`.
> La generalización a múltiples conversaciones/sesiones por documento
> queda como evolución futura.

## Integración con el LLM

El LLM es remoto y se accede a él mediante una abstracción propia
(`LLMClient` Protocol en `socratic/llm/base.py`).

La lógica de dominio **no** depende directamente de un proveedor
concreto, un modelo concreto ni una API propietaria concreta. El
servidor controla qué contexto se envía al modelo. El LLM nunca se
considera el almacenamiento principal del documento; el servidor
construye dinámicamente el contexto para cada interacción.

## Comunicación cliente-servidor

Protocolo actual: **HTTP/REST** (sin WebSocket, SSE, gRPC ni streaming
hasta que REST no pueda resolverlo).

La decisión se tomó en base a las necesidades reales de interacción,
estado y compatibilidad. No se adopta MCP por analogía; se eligió
según necesidades reales. El streaming queda aplazado hasta que
aparezca un caso de uso que lo justifique (audio, cancelación,
latencia perceptible).

## Alcance inicial

Para reducir la complejidad inicial, la primera versión implementa
únicamente:

- Un único documento activo.
- Una única conversación asociada al documento.
- Una única sesión de lectura.

El modelo de dominio se diseña para que la incorporación futura de
múltiples documentos, conversaciones y sesiones no requiera rediseñar
las entidades principales.

La primera versión valida el ciclo:

```
PDF → procesamiento → lectura de un párrafo → pregunta → respuesta → reanudación
```

## No objetivos

En esta fase no se pretende:

- construir un sistema RAG genérico;
- implementar un chatbot sobre PDFs;
- responder preguntas sobre documentos arbitrarios sin seguir el flujo
  de lectura;
- optimizar el rendimiento antes de disponer de métricas;
- soportar todos los formatos documentales existentes.

## Principios de desarrollo

- Desarrollo incremental.
- Arquitectura sencilla antes que arquitectura especulativa.
- Separación clara entre dominio, infraestructura e interfaces.
- Dependencias externas aisladas detrás de interfaces propias.
- Módulos pequeños y responsabilidades explícitas.
- Tipado estático siempre que sea razonable.
- Pruebas automatizadas desde las primeras funcionalidades.
- Documentar las decisiones arquitectónicas importantes.
- No implementar una decisión que todavía deba validarse.
- No añadir abstracciones sin un caso de uso concreto.
- Mantener el repositorio comprensible tanto para humanos como para
  agentes de desarrollo.

## Estado actual (verificado en código)

Implementados y operativos:

- **Lenguaje y framework**: Python 3.11+, FastAPI.
- **Base de datos**: SQLite (stdlib `sqlite3`).
- **Librería PDF**: pdfplumber (con extracción opcional de TOC vía
  pypdf).
- **Protocolo cliente-servidor**: HTTP/REST.
- **Cliente macOS/CLI**: Python con argparse + httpx sync.
- **LLM**: interfaz propia `LLMClient` con implementación
  `OpenAIClient` (compatible con cualquier API OpenAI-compatible).
- **Recuperación documental**: txtai + sentence-transformers
  (`socratic/retrieval/`).
- **Orquestador conversacional**: tool calling con un único LLM por
  Turn (`socratic/orchestrator/`).

## Pendiente / fuera de MVP

- Cliente macOS nativo.
- Aplicación Android.
- Audio: STT, TTS, captura, formatos, transporte, buffering.
- Streaming.
- Soporte multiusuario, autenticación, escalado distribuido.
- OCR.
- Procesamiento perfecto de tablas, capítulos y secciones.
- Múltiples conversaciones por documento, múltiples sesiones abiertas.
- Persistencia detallada de tool calls.
- Operaciones multidocumento desde el orquestador.
