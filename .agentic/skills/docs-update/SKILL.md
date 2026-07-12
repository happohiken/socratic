---
name: docs-update
description: Revisa cambios desde el último commit documentado y actualiza documentación si procede.
---

# docs-update

Revisa si los cambios del repositorio desde el último commit documentado requieren actualizar documentación.

Primero lee:

docs/documentation-methodology.md

Después lee:

.agentic.lock.json

Si no existe `.agentic.lock.json`, o no contiene `documentation.last_reviewed_commit`:

- si no existe documentación básica, recomienda ejecutar `/docs-init`;
- si ya existe documentación, ayuda al usuario a elegir un commit base usando `git log --oneline -- docs`;
- no actualices documentación todavía sin baseline claro.

Si existe `documentation.last_reviewed_commit`:

1. El `README.md` raíz se valida siempre, incluso si el rango de commits no parece afectarlo.
La validación del README no depende del diff.
Debe ejecutarse en cada invocación de docs-update.

2. Obtén el commit base desde `documentation.last_reviewed_commit`.

3. Revisa los cambios desde ese commit hasta `HEAD`:
   - `git log --oneline <base>..HEAD`
   - `git diff --name-status <base>..HEAD`
   - `git diff <base>..HEAD`

4. Deriva automáticamente qué áreas han cambiado a partir del diff y del árbol actual del repositorio. No uses una lista fija de rutas a revisar.

   Ten en cuenta especialmente:
   - ficheros añadidos;
   - ficheros borrados;
   - ficheros movidos;
   - ficheros modificados;
   - nuevas convenciones de directorios;
   - cambios en scripts ejecutables;
   - cambios en manifiestos o configuración;
   - cambios en skills o wrappers;
   - cambios en documentación existente.

5. Revisa la documentación existente y busca afirmaciones relacionadas con las áreas cambiadas.

6. Valida esas afirmaciones contra el estado actual del repositorio:
   - rutas mencionadas existen o han sido movidas;
   - listas de componentes coinciden con el árbol real;
   - comandos documentados coinciden con los scripts reales;
   - formatos descritos coinciden con los ficheros reales;
   - elementos movidos, renombrados o eliminados no siguen documentados como activos;
   - nuevas piezas relevantes del framework están documentadas si afectan al uso o mantenimiento.

7. Actualiza solo los documentos necesarios.

8. Antes de dar la documentación por válida, realiza una auditoría basada en evidencias contra el estado actual del repositorio.

   Para cada documento que consideres afectado por el rango revisado:

   1. Extrae las afirmaciones técnicas relevantes que contiene.
      Por ejemplo:
      - listas de skills, comandos, hooks o componentes;
      - rutas de ficheros o directorios;
      - formatos de lockfiles, manifests o configuración;
      - comandos de uso;
      - flujos de instalación, sincronización o actualización;
      - comportamiento descrito de scripts o herramientas.

   2. Para cada afirmación, identifica su fuente de verdad en el repositorio.
      Por ejemplo:
      - árbol actual de directorios;
      - contenido real de ficheros;
      - scripts ejecutables;
      - manifests;
      - lockfiles;
      - configuración;
      - salida de comandos de inspección.

   3. Comprueba la fuente de verdad antes de aceptar la afirmación como correcta.

   4. Si una afirmación no puede verificarse, no la des por válida:
      - corrígela si el estado real del repo es claro;
      - o márcala como pendiente de verificar si no puedes comprobarla.

   5. No concluyas que un documento está actualizado solo porque "parece coherente".
      Debes poder explicar qué evidencia del repositorio confirma las afirmaciones relevantes.

   La documentación debe describir el estado actual del proyecto, no solo cubrir el diff revisado.

9. Valida siempre el `README.md` raíz como documento obligatorio de entrada al proyecto.

   El README no se considera válido solo por no contener errores. Debe pasar esta checklist:

   1. Describe qué es el proyecto en 1-3 frases.
   2. Explica qué problema resuelve.
   3. Enumera las funcionalidades visibles para usuarios/desarrolladores.
   4. Explica el flujo básico de uso.
   5. Explica el flujo básico de instalación, ejecución o sincronización, si el proyecto tiene alguno.
   6. Lista los comandos, scripts, herramientas o puntos de entrada principales que el usuario puede ejecutar.
   7. Muestra la estructura mínima relevante del repositorio.
   8. Enlaza a la documentación detallada en `docs/`.

   Para validar la checklist, deriva primero la superficie pública del repositorio.

   Inspecciona el árbol actual y detecta, si existen:
   - scripts ejecutables;
   - comandos o herramientas CLI;
   - skills, hooks, plugins, workflows o integraciones de agentes;
   - manifests, lockfiles o ficheros de configuración relevantes;
   - servicios, entrypoints, APIs o interfaces públicas;
   - documentación existente en `docs/`.

   Regla sobre "No aplica":

   No marques un punto como "No aplica" solo porque el README actual no lo mencione.

   Solo puedes marcarlo como "No aplica" después de haber inspeccionado la superficie pública del repositorio y haber comprobado que no existe ningún elemento real que corresponda a ese punto.

   Si existe una funcionalidad pública, comando, script, skill, servicio, API, workflow o mecanismo de instalación/sincronización, el README debe mencionarlo de forma resumida.

   Si el README no menciona una funcionalidad pública existente, actualízalo.

   Si el README menciona una funcionalidad que ya no existe, corrígelo.

   Si el README es genérico, pobre o no permite a un usuario entender cómo usar el proyecto, actualízalo aunque no contenga afirmaciones falsas.

   No seas escueto ni perezoso en el README, es un fichero muy importante, mantenlo actualizado por pequeñas que sean las modifciaciones necesarias.

10. Al terminar correctamente, actualiza `.agentic.lock.json`:
   - `documentation.last_reviewed_commit` = commit actual de `HEAD`;
   - `documentation.last_reviewed_at` = fecha/hora actual real en formato ISO 8601.
   - Si no puedes obtener la fecha/hora real, deja `documentation.last_reviewed_at` en `null` y avisa.

Reglas:

- No inventes información.
- No actualices documentación si no hace falta.
- No modifiques código.
- Mantén los documentos cortos.
- No hardcodees en la revisión una lista fija de documentos o rutas; deriva lo afectado desde el diff, el árbol actual y las referencias existentes en la documentación.
- Si el diff muestra cambios relevantes no documentados, actualiza la documentación correspondiente.
- Explica al final:
  - qué rango de commits revisaste;
  - qué documentación se actualizó;
  - qué documentación no necesitó cambios;
  - si quedó algo pendiente de validar.