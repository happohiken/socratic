# Resolución de problemas

## El servidor no arranca

### `Address already in use` (puerto ocupado)

Otra proceso está usando el puerto 8885. Cámbialo:

```bash
SOCRATIC_PORT=8886 python -m main
```

O mata el proceso que lo ocupa:

```bash
lsof -i :8885     # identificar el proceso
kill <PID>
```

### `ModuleNotFoundError: No module named 'socratic'`

No instalaste el paquete en el entorno. Desde `socratic-server/`:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### `sqlite3.OperationalError: unable to open database file`

El directorio padre de `SOCRATIC_STORAGE_PATH` no se puede crear.
Verifica permisos o usa una ruta absoluta:

```bash
SOCRATIC_STORAGE_PATH=/tmp/socratic.db python -m main
```

## La CLI no conecta con el servidor

### `ConnectionError` o `httpx.ConnectError`

- Verifica que el servidor está corriendo: `curl http://127.0.0.1:8885/docs`.
- Verifica la URL: `socratic --url http://127.0.0.1:8885 documents`.
- Si usas otra máquina: `SOCRATIC_URL=http://<IP>:8885 socratic documents`.

### `[404] Estudio <id> no encontrado`

El `study_id` no existe o se eliminó. Lista los estudios con
`socratic studies` y copia un id válido.

## El endpoint `/ask` o `/interact` falla

### `[500] ... api_key` o `AuthenticationError`

Falta configurar el LLM. Sin `SOCRATIC_LLM_BASE_URL` y
`SOCRATIC_LLM_API_KEY`, los endpoints que llaman al LLM fallarán en
runtime.

```bash
# Importar desde OpenCode
eval "$(socratic config import-opencode --provider <p> --model <m> --export-shell)"

# Verificar que las variables están
env | grep SOCRATIC_LLM

# Arrancar el servidor con las variables
cd socratic-server && python -m main
```

Ver [configuration.md](configuration.md).

### `[400] El estudio no tiene bloque actual`

El estudio ha llegado al final del documento. Opciones:

```bash
# Retroceder al último bloque completado
socratic previous-block <study_id>

# O crear un estudio nuevo para empezar de cero
socratic create-study <document_id>
```

### `[500] ... timeout` o `ReadTimeout`

El LLM tardó más que `SOCRATIC_LLM_TIMEOUT_SECONDS` (default 120).
Aumenta el timeout:

```bash
SOCRATIC_LLM_TIMEOUT_SECONDS=300 python -m main
```

Si el timeout es por un modelo local lento, considera uno más ligero.

## La recuperación documental (RAG) no devuelve resultados

### `No se encontraron resultados.`

Posibles causas:

1. **El documento no está indexado**:

   ```bash
   socratic reindex <document_id>
   ```

2. **El índice está corrupto** o desactualizado: bórralo y reconstruye:

   ```bash
   rm -rf socratic-server/data/retrieval/
   # Reiniciar el servidor para que cargue índice vacío
   socratic reindex   # indexar todos los documentos
   ```

3. **La consulta no tiene términos relevantes**: prueba con términos
   del propio documento.

### El modelo de embeddings no se descarga

`sentence-transformers/all-MiniLM-L6-v2` se descarga la primera vez
desde Hugging Face. Si no hay internet o hay un firewall:

- Verifica conexión a `https://huggingface.co`.
- Si ya lo tienes descargado en otra máquina, copia
  `~/.cache/huggingface/`.

## La extracción de PDF es incorrecta

### Cabeceras y pies aparecen en los bloques

El extractor detecta automáticamente cabeceras/pies repetidos, pero a
veces falla. Diagnostica con:

```bash
socratic inspect-pdf ~/Documentos/articulo.pdf --pages 1-5
```

Si el problema es consistente, abre un issue o ajusta el extractor
(`socratic-server/src/socratic/document_processing/extractor.py`).

### Texto degradado o caracteres raros

El PDF tiene fuentes embebidas no estándar. pdfplumber no puede
extraer el texto correctamente. Fuera del MVP: necesitaría OCR.

### Bloques en orden incorrecto (PDF de dos columnas)

El extractor ordena por coordenadas, pero en PDFs de dos columnas a
veces mezcla. Diagnostica con `inspect-pdf`. Para PDFs complejos,
considera preprocesarlos.

### Tablas y fórmulas inutilizables

Fuera del MVP. Las tablas se tratan como texto plano; las fórmulas no
se procesan específicamente.

## `socratic inspect-pdf` falla con `ModuleNotFoundError`

`inspect-pdf` importa `parse_pdf` del paquete `socratic-server`. La CLI
debe instalarse en el mismo entorno que el servidor:

```bash
cd socratic-server
source .venv/bin/activate
pip install -e ".[dev]"

cd ../socratic-cli
pip install -e .
```

## `socratic config import-opencode` falla

### `No se encontró el archivo: ~/.config/opencode/opencode.json`

No tienes OpenCode configurado. Configura el LLM manualmente con
variables de entorno (ver [configuration.md](configuration.md)).

### `baseURL no encontrado para el proveedor`

El proveedor en `opencode.json` no tiene `options.baseURL` (o
`base_url`). Edita el archivo o usa otro proveedor.

### `API key no resolvable`

El proveedor no tiene `options.apiKey` ni `options.api_key_env`. Las
variables generadas no contendrán la API key y los endpoints que
llaman al LLM fallarán. Edita `opencode.json` o define
`SOCRATIC_LLM_API_KEY` manualmente.

## La posición de lectura no avanza

- `current-block` **no** avanza la posición; solo la muestra.
- `ask` **no** avanza la posición; solo pregunta.
- Para avanzar, usa `complete-block` o `next-block`.

```bash
socratic current-block <study_id>     # ver, no avanza
socratic next-block <study_id>        # avanza al siguiente
```

## No puedo retroceder más

### `Ya estás en el primer bloque`

El estudio está en el bloque 0. No se puede retroceder más.

### `El estudio no tiene bloques completados para retroceder`

El estudio está al final del documento (`current_block_id=None`) y no
tiene `last_completed_block_id`. Crea un estudio nuevo o usa
`next-block` desde el principio.

## El servidor pierde el estado al reiniciar

No debería: SQLite persiste todo. Si ocurre:

1. Verifica que arrancas el servidor desde el mismo directorio o con
   la misma `SOCRATIC_STORAGE_PATH`.
2. Verifica que `data/socratic.db` existe y tiene contenido:

   ```bash
   ls -lh socratic-server/data/socratic.db
   sqlite3 socratic-server/data/socratic.db "SELECT count(*) FROM documents;"
   ```

3. Si la BD se corrompió, restaura desde backup o empieza de cero
   borrando `data/`.

## Ver también

- [getting-started.md](getting-started.md) — instalación.
- [cli-reference.md](cli-reference.md) — comandos.
- [configuration.md](configuration.md) — variables de entorno.
