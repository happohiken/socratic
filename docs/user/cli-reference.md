# Referencia de comandos de la CLI

La CLI se instala como `socratic` (`pip install -e .` en `socratic-cli/`).
Requiere el servidor corriendo (`python -m main` en `socratic-server/`).

## Opciones globales

| Opción | Descripción |
|---|---|
| `--url <URL>` | URL base del servidor. Default: `SOCRATIC_URL` o `http://127.0.0.1:8885`. |

También configurable con la variable de entorno `SOCRATIC_URL`.

## Documentos

### `socratic upload <pdf>`

Sube un PDF al servidor. Extrae bloques ordenados y los persiste.

```bash
socratic upload ~/Documentos/articulo.pdf
```

Salida: `document_id`, `filename`, `block_count`, `page_count`.

### `socratic documents`

Lista todos los documentos.

### `socratic document <document_id>`

Detalle de un documento y sus bloques (con preview de texto).

### `socratic delete <document_id>`

Elimina un documento y todos sus asociados (bloques, estudios,
mensajes) en cascada.

## Estudios

### `socratic create-study <document_id>`

Crea un estudio para un documento. Inicializa la posición en el primer
bloque.

Salida: `study_id`, `document_id`, `current_block_id`,
`last_completed_block_id`.

### `socratic studies`

Lista todos los estudios.

### `socratic study <study_id>`

Estado de un estudio: `id`, `document_id`, `current_block_id`,
`last_completed_block_id`, `updated_at`.

## Lectura

### `socratic current-block <study_id>`

Obtiene el bloque actual **sin avanzar** la posición. Útil para repetir
la lectura.

Salida: `block_id`, `ordinal`, `page`, `type` y texto del bloque.

### `socratic complete-block <study_id> <block_id>`

Marca un bloque como completado y avanza al siguiente.

> Normalmente se usa `next-block` (que obtiene, imprime y completa el
> actual en un solo comando).

### `socratic next-block <study_id> [--verbose]`

Obtiene el bloque actual, lo imprime y lo completa. Avanza
automáticamente al siguiente.

```bash
socratic next-block <study_id>
socratic next-block <study_id> --verbose   # muestra block_id, ordinal, página, tipo
```

Si el estudio ha llegado al final del documento, avisa y termina sin
error.

### `socratic previous-block <study_id> [--verbose]`

Retrocede al bloque anterior. Actualiza `current_block_id` al bloque
anterior. Si `current_block_id` es `None` (fin del documento), vuelve
al último bloque completado.

```bash
socratic previous-block <study_id>
socratic previous-block <study_id> --verbose
```

Errores:
- "Ya estás en el primer bloque."
- "El estudio no tiene bloques completados para retroceder."

## Mensajes

### `socratic messages <study_id>`

Lista los mensajes de un estudio, ordenados por fecha de creación.

Formato: `[role] content  (created_at)`.

### `socratic message <study_id> <content> [--role ROLE] [--block-id ID]`

Crea un mensaje en el estudio. Normalmente no se usa directamente: los
mensajes los crea el servidor al responder a `ask`.

```bash
socratic message <study_id> "Nota personal" --role user
```

## Preguntas

### `socratic ask <study_id> <question>`

Hace una pregunta al LLM sobre el bloque actual de lectura. El
servidor compone un contexto ampliado (bloque actual + anteriores +
siguientes + fragmentos recuperados del documento + historial reciente)
y devuelve la respuesta.

```bash
socratic ask <study_id> "¿Qué significa este término?"
```

La respuesta se guarda en el historial. La posición de lectura **no**
avanza tras una pregunta.

> **Pendiente**: la CLI aún no expone `interact`, la vía conversacional
> con tools del orquestador. Mientras tanto, `ask` es la forma de
> preguntar.

## Recuperación documental

### `socratic reindex [<document_id>]`

Indexa los bloques de un documento (o de todos si se omite el id) para
recuperación vectorial con txtai. Necesario para que `ask` pueda
recuperar fragmentos de cualquier parte del documento.

```bash
socratic reindex                          # indexar todos los documentos
socratic reindex <document_id>            # indexar uno concreto
```

Salida: número de bloques indexados por documento.

### `socratic search-document <document_id> <query> [--limit N]`

Busca bloques relevantes en un documento indexado. Útil para
diagnóstico: ver qué fragmentos recuperaría el RAG para una consulta.

```bash
socratic search-document <id> "machine learning medicina"
socratic search-document <id> "resultados" --limit 10
```

Salida por cada resultado: `page`, `ordinal`, `type`, `score` y
preview de texto (200 caracteres).

## Inspección de PDFs

### `socratic inspect-pdf <pdf> [--format text|json] [--pages N-M] [--output FILE]`

Inspecciona la descomposición documental de un PDF **sin subirlo al
servidor**. Útil para diagnosticar cómo se extraen los bloques antes de
subirlo.

```bash
socratic inspect-pdf ~/Documentos/articulo.pdf
socratic inspect-pdf ~/Documentos/articulo.pdf --format json --output parsed.json
socratic inspect-pdf ~/Documentos/articulo.pdf --pages 1-5
```

Requiere el paquete `socratic-server` instalado en el entorno (la CLI
importa `parse_pdf`).

## Configuración

### `socratic config import-opencode --provider P --model M (--export-shell|--print-env)`

Genera variables `SOCRATIC_LLM_*` a partir de la configuración de
OpenCode en `~/.config/opencode/opencode.json`.

```bash
# Vista previa (formato systemd)
socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --print-env

# Exportar variables para la sesión actual
eval "$(socratic config import-opencode --provider zcube-local --model qwen3.6-35b-a3b --export-shell)"

# Arrancar el servidor con las variables
cd socratic-server && python -m main
```

Variables generadas: `SOCRATIC_LLM_PROVIDER`, `SOCRATIC_LLM_BASE_URL`,
`SOCRATIC_LLM_MODEL`, `SOCRATIC_LLM_API_KEY`,
`SOCRATIC_LLM_TIMEOUT_SECONDS`.

> **Advertencia**: la salida de `--print-env` puede contener secretos
> (API key). No la guardes en el repositorio ni en logs compartidos.

Ver [configuration.md](configuration.md) para más detalle.
