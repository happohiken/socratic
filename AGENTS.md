# AGENTS.md

## Estado del proyecto

El repositorio está en fase de planificación. No hay código fuente aún.
Las decisiones pendientes (lenguaje, framework, BD, protocolo, proveedor LLM)
deben analizarse antes de implementar.

## Documentación

- `docs/product-context.md` — especificación completa del producto y arquitectura prevista.
  Fuente de verdad para decisiones de diseño antes de que exista código.
- `docs/documentation-methodology.md` — reglas de documentación mínima.
- La documentación es mínima y on-demand. No cargarla toda al inicio de la sesión.
- Documentar solo lo que no sea evidente leyendo el código.

## Skills (agentic framework)

La lógica de cada skill vive una única vez en `.agentic/skills/<skill>/SKILL.md`.
Los wrappers en `.claude/skills/` y `.opencode/skills/` solo reenvían a ella.
No modificar la lógica desde los wrappers.

Skills instaladas:
- `commit-work`
- `docs-init`
- `docs-update`

## Convenciones

- Idioma de comunicación y documentación: español.
- El servidor y el cliente macOS se desarrollarán en paralelo una vez el flujo básico funcione.
- El cliente macOS es un facilitador de desarrollo/pruebas, no necesariamente el producto final.
- El modelo de dominio debe diseñarse para soportar múltiples documentos, conversaciones y sesiones desde el inicio, aunque la primera iteración sea single-document/single-conversation.
- La interfaz con el LLM debe ser una abstracción propia. No acoplar a un proveedor concreto.
- No adoptar MCP por analogía; elegir el protocolo según necesidades reales.
- El estado persistido debe contener solo la información mínima necesaria para reconstruir el estado completo.

## Flujo de primer ciclo (MVP)

PDF → procesamiento → lectura de un párrafo → pregunta → respuesta → reanudación

## Operaciones

No hay comandos de build/test/lint/configurados aún. Crear la configuración del lenguaje/framework elegido antes de la primera implementación.
