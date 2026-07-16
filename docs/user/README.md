# Documentación de usuario

Capa completa para instalar, configurar y utilizar Socratic sin
necesitar consultar documentación técnica.

## Índice

| Documento | Contenido |
|---|---|
| [getting-started.md](getting-started.md) | Instalación del servidor y la CLI, primer PDF, primer estudio. |
| [cli-reference.md](cli-reference.md) | Referencia completa de comandos de la CLI. |
| [configuration.md](configuration.md) | Variables de entorno y configuración del LLM. |
| [workflows.md](workflows.md) | Flujos típicos: leer, preguntar, reanudar, recuperar. |
| [troubleshooting.md](troubleshooting.md) | Errores frecuentes y recuperación. |

## Qué es Socratic

Socratic transforma cualquier documento PDF en una conversación guiada.
Mientras recorres un PDF, puedes interrumpir la lectura para hacer
preguntas, pedir aclaraciones, solicitar ejemplos o repetir fragmentos,
y continuar exactamente donde te quedaste.

## Componentes

- **Servidor** (`socratic-server/`): procesa los PDFs, guarda el
  estado, habla con el LLM y ofrece la API REST.
- **CLI** (`socratic-cli/`): cliente de línea de comandos que consume
  la API. Es la forma más rápida de empezar a usar Socratic.

No existe todavía un cliente gráfico nativo; la CLI es la interfaz
principal de uso y desarrollo.
