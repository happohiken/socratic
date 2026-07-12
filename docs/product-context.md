# Contexto del producto

## Propósito

Socratic es una aplicación de estudio interactivo que permite recorrer un documento PDF u otros formatos de forma secuencial, pudiendo leerlo visualmente, escucharlo mediante síntesis de voz o combinar ambas modalidades, e interrumpirla para hacer preguntas, pedir aclaraciones, solicitar ejemplos o volver a escuchar fragmentos anteriores.

Tras resolver una interrupción, la lectura debe poder continuar desde el punto exacto donde se detuvo.

## Arquitectura prevista

El sistema tendrá inicialmente dos componentes:

1. Un servidor que contendrá la lógica principal.
2. Un cliente de desarrollo para macOS.

Cuando el flujo básico sea funcional, se desarrollará una aplicación Android. Desde ese momento, el servidor y el cliente Android evolucionarán en paralelo.

El cliente macOS no es necesariamente el producto final. Su función inicial es facilitar el desarrollo, las pruebas y la validación del protocolo cliente-servidor.

## Responsabilidades iniciales del servidor

- Recibir y procesar documentos PDF.
- Construir una representación estructurada independiente del formato original.
- Identificar capítulos, secciones, párrafos y, cuando sea necesario, otras unidades de lectura.
- Gestionar el estado persistente del estudio de cada documento y construir las sesiones de lectura necesarias para interactuar con el usuario.
- Conservar un puntero estable a la posición actual.
- Atender comandos de lectura, pausa, reanudación y navegación.
- Construir el contexto necesario para responder preguntas.
- Comunicarse con un LLM remoto.
- Permitir reanudar la lectura después de una pregunta.
- Diseñarse para soportar posteriormente un cliente Android.

## Flujo funcional mínimo

1. El usuario carga un documento.
2. El servidor procesa el documento y construye una representación estructurada.
3. El servidor genera los índices necesarios para la navegación y recuperación de contexto.
4. El usuario inicia la lectura.
5. El servidor entrega el siguiente fragmento de lectura.
6. El usuario puede interrumpir para:
   - hacer una pregunta;
   - pedir una aclaración;
   - solicitar un ejemplo;
   - repetir el párrafo actual;
   - repetir el párrafo anterior;
   - continuar la lectura.
7. El servidor responde utilizando el contexto documental pertinente.
8. La lectura se reanuda desde la posición correcta.

## Gestión documental

No debe asumirse que el documento completo cabrá en la ventana de contexto del LLM.

El sistema deberá representar los documentos mediante unidades identificables y estables, como:

- documento;
- capítulo;
- sección;
- párrafo;
- fragmento o span, si fuera necesario.

Cada unidad debe poder referenciarse mediante un identificador estable. La posición de lectura no debe depender únicamente de offsets de caracteres o páginas del PDF.

La estrategia de contexto deberá poder combinar:

- el fragmento actual;
- fragmentos inmediatamente anteriores;
- el contexto estructural del capítulo o sección;
- un resumen acumulado;
- fragmentos relevantes recuperados del documento;
- el historial reciente de la conversación.

La estrategia concreta se decidirá durante el diseño.

## Estado de lectura

El servidor será la fuente de verdad del estado de la sesión.

Como mínimo, una sesión deberá poder representar:

- documento activo;
- posición actual;
- último párrafo leído;
- punto de interrupción;
- estado de lectura;
- historial de preguntas relevante;
- información necesaria para reanudar la lectura.

Siempre que sea posible, el estado persistido deberá contener únicamente la información mínima necesaria para reconstruir el estado completo de una sesión, evitando almacenar datos redundantes.

## Múltiples documentos y conversaciones activas

Socratic debe permitir mantener varios documentos PDF abiertos de forma simultánea.

El usuario debe poder:

- Cargar y conservar varios documentos.
- Cambiar de un documento a otro.
- Mantener una o varias conversaciones asociadas a cada documento.
- Recuperar el historial relevante de cada conversación.
- Reanudar la lectura de cada documento desde el punto exacto donde se dejó.
- Mantener diferentes líneas de estudio sobre un mismo documento sin mezclar su contexto.

Cambiar de documento no debe destruir ni sobrescribir el estado del documento anterior.

Cada conversación deberá conservar, como mínimo:

- El documento asociado.
- La posición actual de lectura.
- El último fragmento leído.
- El punto de interrupción.
- El historial conversacional.
- Los resúmenes o contexto acumulado.
- El estado de lectura.
- La fecha de la última actividad.

El servidor será la fuente de verdad de este estado persistente.

El modelo conceptual deberá distinguir claramente entre las siguientes entidades:

- **Document**: el PDF procesado y su estructura.
- **Conversation**: una conversación de estudio asociada a un documento.
- **Reading Session**: el estado de lectura dentro de una conversación.
- **Reading Position**: una referencia estable al punto actual del documento.

Un mismo documento podrá tener varias conversaciones independientes. Esto permitirá, por ejemplo, estudiar el mismo PDF desde perspectivas distintas o reiniciar el estudio desde el principio sin perder el progreso de una conversación anterior.

La interfaz deberá permitir listar los documentos y conversaciones recientes, cambiar entre ellos y reanudar cada uno exactamente donde se dejó.

## Integración con el LLM

El LLM será remoto y se accederá a él mediante una abstracción propia.

La lógica de dominio no debe depender directamente de:

- un proveedor concreto;
- un modelo concreto;
- una API propietaria concreta.

El servidor deberá controlar qué contexto se envía al modelo.
El LLM nunca debe considerarse el almacenamiento principal del documento.
El servidor será responsable de construir dinámicamente el contexto que se envía al modelo para cada interacción.

## Comunicación cliente-servidor

Todavía no se ha decidido el protocolo definitivo.

Se evaluarán, entre otras posibilidades:

- HTTP/REST;
- WebSocket;
- streaming sobre HTTP;
- gRPC;
- MCP, si aporta una ventaja concreta.

No debe adoptarse MCP únicamente por analogía con otros sistemas de agentes. El protocolo debe escogerse de acuerdo con las necesidades reales de interacción, streaming, audio, estado y compatibilidad con Android.

## Alcance inicial

Para reducir la complejidad inicial, la primera versión implementará únicamente:

- Un único documento activo.
- Una única conversación asociada al documento.
- Una única sesión de lectura.

El modelo de dominio deberá, no obstante, diseñarse de forma que la incorporación futura de múltiples documentos, conversaciones y sesiones no requiera rediseñar las entidades principales.

La primera versión debe validar únicamente este ciclo:

PDF → procesamiento → lectura de un párrafo → pregunta → respuesta → reanudación

Quedan fuera de la primera iteración, salvo que sean imprescindibles:

- aplicación Android;
- interfaz gráfica compleja;
- soporte multiusuario;
- escalado distribuido;
- autenticación avanzada;
- múltiples proveedores de almacenamiento;
- optimizaciones prematuras;
- RAG complejo;
- procesamiento perfecto de cualquier PDF;
- despliegue en producción.

## No objetivos

En esta fase no se pretende:

- construir un sistema RAG genérico;
- implementar un chatbot sobre PDFs;
- resolver preguntas sobre documentos arbitrarios sin seguir el flujo de lectura;
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
- Mantener el repositorio comprensible tanto para humanos como para agentes de desarrollo.

## Estado actual

El repositorio está recién creado.

Todavía no se han decidido:

- lenguaje y framework del servidor;
- tecnología del cliente macOS;
- base de datos;
- almacenamiento de documentos;
- librería de extracción de PDFs;
- protocolo cliente-servidor;
- protocolo de streaming;
- proveedor o API concreta del LLM;
- sistema de síntesis de voz;
- estrategia definitiva de indexación y recuperación;
- formato del modelo de estado.

Estas decisiones deben analizarse antes de implementar código.

## Filosofía del producto

Socratic no pretende responder preguntas sobre un documento de forma aislada.

Su objetivo es reproducir la experiencia de estudiar con un profesor particular que explica un texto de forma secuencial, permite interrupciones naturales y mantiene el hilo de la explicación durante toda la sesión de estudio.

El sistema debe priorizar la continuidad de la lectura y la comprensión progresiva frente a responder preguntas descontextualizadas sobre cualquier parte del documento.