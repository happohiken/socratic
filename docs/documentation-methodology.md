# Metodología de documentación mínima para agentes

## Objetivo

Mantener una documentación pequeña, útil y cargable bajo demanda por agentes de coding y desarrolladores humanos.

La documentación no debe intentar explicarlo todo. Debe guardar solo el conocimiento que no es evidente leyendo el código.

## Principios

1. Documentar solo lo útil:
   - arquitectura general;
   - APIs o interfaces entre partes;
   - despliegue y operación;
   - decisiones importantes si afectan al mantenimiento.

2. No duplicar código:
   si algo se entiende leyendo el código, no se documenta.

3. No cargar toda la documentación por defecto:
   los arneses deben consultar solo los documentos necesarios para la tarea actual.

4. Referenciar documentación mediante rutas del repositorio:
   la documentación común y las skills comunes deben referenciar documentos mediante rutas normales del repositorio, por ejemplo:

   ```text
   docs/architecture.md
   docs/api.md
   docs/operations.md
   ```

   No usar sintaxis específica de un arnés, como `@docs/architecture.md`, dentro de documentación o skills comunes.

5. Mantener pocos documentos.

   Estructura recomendada para un repositorio pequeño:

   ```text
   docs/
   ├── README.md
   ├── architecture.md
   ├── api.md
   ├── operations.md
   └── notes/
   ```

6. Actualizar la documentación junto con el código:

   Si cambia la arquitectura, la API o el despliegue, se actualiza el documento correspondiente en la misma sesión.

## Uso por agentes

Los agentes deben:

- leer solo los documentos necesarios para la tarea;
- no cargar toda la documentación al iniciar la sesión;
- utilizar rutas normales del repositorio para consultar documentación;
- avisar si un cambio de código requiere actualizar documentación;
- proponer cambios documentales, no inventarlos.

## Skills comunes

Las acciones reutilizables viven en:

```text
.agentic/skills/<skill>/SKILL.md
```

Cada arnés implementa un wrapper mínimo:

```text
.claude/skills/<skill>/SKILL.md
.opencode/skills/<skill>/SKILL.md
```

La lógica de cada skill vive una única vez en `.agentic/skills/`.

Los wrappers no deben contener lógica de negocio; únicamente deben invocar la implementación común.

## README principal

El `README.md` de la raíz debe mantenerse como resumen actualizado del estado del proyecto.

Debe incluir, como mínimo:

- qué es el proyecto;
- qué problema resuelve;
- funcionalidades disponibles;
- cómo instalar o usar lo básico;
- enlaces a la documentación detallada en `docs/`.

No debe duplicar toda la documentación interna. Debe actuar como puerta de entrada.

El `README.md` no se considera correcto solo por no contener afirmaciones falsas.

   Debe describir de forma útil el estado actual del proyecto:
   - qué es el proyecto;
   - qué problema resuelve;
   - qué funcionalidades principales tiene;
   - cómo se instala o sincroniza en un repo consumidor;
   - qué skills core existen;
   - cómo se usa el flujo básico;
   - dónde está la documentación detallada.
   Si el `README.md` es demasiado pobre, genérico o no refleja funcionalidades visibles para usuarios, actualízalo aunque no contenga errores factuales.