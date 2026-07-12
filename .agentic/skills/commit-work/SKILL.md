---
name: commit-work
description: Revisa cambios, actualiza documentación si procede y prepara un commit descriptivo.
---

# commit-work

Prepara un commit de trabajo con una descripción clara y completa.

Proceso obligatorio:

1. Revisa el estado del repositorio:
   - git status --short
   - git diff --stat
   - git diff

2. Ejecuta siempre la lógica de `.agentic/skills/docs-update/SKILL.md` antes de preparar el commit.

3. Si `docs-update` modifica documentación, vuelve a revisar:
   - git status --short
   - git diff --stat

4. Propón el conjunto final de ficheros a incluir en el commit.

5. Propón un mensaje de commit con:
   - título corto;
   - cuerpo largo explicando qué cambió;
   - motivo del cambio;
   - impacto funcional;
   - notas de validación realizadas.

6. Antes de ejecutar `git add` o `git commit`, pide confirmación explícita al usuario.

7. Si el usuario confirma:
   - ejecuta git add sobre los ficheros aprobados;
   - ejecuta git commit con el mensaje propuesto.

8. No hagas `git push` salvo que el usuario lo pida explícitamente.

9. Si el usuario pide push:
   - muestra primero la rama actual;
   - muestra el remote/upstream configurado;
   - ejecuta `git push` solo tras confirmación explícita.

Reglas:

- No inventes cambios.
- No incluyas ficheros no revisados.
- No hagas commit si hay conflictos, secretos, binarios inesperados o cambios dudosos.
- Si el estado del repo no está claro, para y pregunta.
