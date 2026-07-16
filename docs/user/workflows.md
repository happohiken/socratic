# Flujos típicos

Esta página recorre los flujos de uso más habituales de Socratic con
comandos copy-paste. Requiere el servidor corriendo
(`cd socratic-server && python -m main`) y la CLI instalada
(`pip install -e .` en `socratic-cli/`).

## 1. Subir y empezar a leer un PDF

```bash
# Subir el PDF
socratic upload ~/Documentos/articulo.pdf
# → document_id  <uuid>

# (Recomendado) Indexar para recuperación documental
socratic reindex <document_id>

# Crear un estudio
socratic create-study <document_id>
# → study_id  <uuid>

# Ver el primer bloque
socratic current-block <study_id>

# Avanzar bloque a bloque
socratic next-block <study_id>
socratic next-block <study_id>
socratic next-block <study_id> --verbose
```

## 2. Repetir y retroceder

```bash
# Volver a leer el bloque actual
socratic current-block <study_id>

# Retroceder al bloque anterior
socratic previous-block <study_id>

# Si estás al final del documento, previous-block vuelve al último
# completado
```

## 3. Preguntar sobre el bloque actual

```bash
socratic ask <study_id> "¿Qué significa este término?"
socratic ask <study_id> "Dame un ejemplo de esto."
socratic ask <study_id> "¿Cómo se relaciona con lo anterior?"
```

El servidor compone un contexto ampliado (bloque actual + 2 anteriores
+ 2 siguientes + fragmentos recuperados del documento + historial
reciente) y llama al LLM. La respuesta se guarda en el historial. La
posición de lectura **no** avanza tras una pregunta.

## 4. Ver el historial de la conversación

```bash
socratic messages <study_id>
```

Formato: `[role] content  (created_at)`.

## 5. Cerrar y reanudar más tarde

El estado se persiste en SQLite. Puedes cerrar el servidor y la CLI:

```bash
# Cerrar con Ctrl+C en la terminal del servidor
# Cerrar la terminal de la CLI
```

Reanudar:

```bash
cd socratic-server
python -m main
# El estado se conserva: documentos, estudios, mensajes.

# En otra terminal
socratic studies                       # ver estudios disponibles
socratic study <study_id>              # ver estado actual
socratic current-block <study_id>      # seguir donde se dejó
```

## 6. Recuperación documental (RAG)

Para que `ask` pueda responder preguntas sobre cualquier parte del
documento (no solo el bloque actual), primero hay que indexarlo:

```bash
# Indexar un documento concreto
socratic reindex <document_id>

# Indexar todos los documentos
socratic reindex
```

El modelo de embeddings (`sentence-transformers/all-MiniLM-L6-v2`) se
descarga la primera vez y se cachea.

### Diagnóstico de recuperación

Para ver qué fragmentos recuperaría el RAG para una consulta:

```bash
socratic search-document <document_id> "machine learning medicina"
socratic search-document <document_id> "resultados principales" --limit 10
```

Salida por cada resultado: `page`, `ordinal`, `type`, `score` y
preview de texto.

## 7. Inspeccionar un PDF antes de subirlo

```bash
# Ver la descomposición documental en texto legible
socratic inspect-pdf ~/Documentos/articulo.pdf

# Solo unas páginas
socratic inspect-pdf ~/Documentos/articulo.pdf --pages 1-5

# Guardar como JSON
socratic inspect-pdf ~/Documentos/articulo.pdf --format json --output parsed.json
```

Útil para diagnosticar problemas de extracción (cabeceras/pies no
filtrados, bloques fusionados, orden incorrecto) antes de subir el PDF
al servidor.

## 8. Gestionar documentos

```bash
# Listar documentos
socratic documents

# Ver detalle con bloques
socratic document <document_id>

# Eliminar un documento (y todos sus estudios y mensajes, en cascada)
socratic delete <document_id>
```

## 9. Usar Socratic desde otra máquina de la LAN

El servidor escucha en `0.0.0.0:8885`. Desde otra máquina:

```bash
# En el servidor
hostname -I    # obtener la IP

# En la otra máquina
SOCRATIC_URL=http://192.168.1.10:8885 socratic documents
# o
socratic --url http://192.168.1.10:8885 documents
```

## 10. Flujo completo recomendado

```bash
# 1. Subir PDF
DOC=$(socratic upload ~/Documentos/articulo.pdf | awk '/document_id/ {print $2}')
# 2. Indexar para RAG
socratic reindex $DOC
# 3. Crear estudio
STUDY=$(socratic create-study $DOC | awk '/study_id/ {print $2}')
# 4. Bucle de lectura
socratic next-block $STUDY
# 5. Preguntar
socratic ask $STUDY "¿Puedes aclarar este punto?"
# 6. Continuar
socratic next-block $STUDY
# 7. Ver historial
socratic messages $STUDY
# 8. Cerrar y reanudar más tarde
# ... reiniciar servidor ...
socratic current-block $STUDY
```

## Ver también

- [cli-reference.md](cli-reference.md) — todos los comandos.
- [configuration.md](configuration.md) — configuración del LLM y
  variables de entorno.
- [troubleshooting.md](troubleshooting.md) — errores frecuentes.
