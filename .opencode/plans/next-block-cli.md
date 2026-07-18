# Plan: Comandos `next-block` y `previous-block`

## Resumen

Añadir dos comandos CLI de conveniencia para avanzar/retroceder bloques durante pruebas manuales:

- `socratic next-block <study-id>` — obtiene bloque actual, imprime texto, lo completa
- `socratic previous-block <study-id>` — retrocede al bloque anterior sin modificar estado

## Componentes existentes reutilizados

### Para `next-block`

| Componente | Archivo:linea | Uso |
|---|---|---|
| `SocraticClient.get_current_block()` | `client.py:75` | GET bloque actual |
| `SocraticClient.complete_block()` | `client.py:78` | POST completar bloque |
| `_client(args)` | `main.py:16` | Crear cliente desde args/env |
| `_err(msg)` | `main.py:27` | Imprimir a stderr |
| `_print_kv()` | `main.py:21` | Metadatos en --verbose |
| `SocraticAPIError` | `client.py:108` | Manejo de errores |

### Para `previous-block`

| Componente | Archivo:linea | Uso |
|---|---|---|
| `SocraticClient.get_study()` | `client.py:72` | GET study → current_block_id + document_id |
| `SocraticClient.get_document()` | `client.py:61` | GET document → lista de bloques con texto |
| `_client(args)` | `main.py:16` | Crear cliente desde args/env |
| `_err(msg)` | `main.py:27` | Imprimir a stderr |
| `_print_kv()` | `main.py:21` | Metadatos en --verbose |
| `SocraticAPIError` | `client.py:108` | Manejo de errores |

### Tests (compartidos)

| Componente | Archivo:linea | Uso |
|---|---|---|
| `_StubLLM` | `test_full_flow.py:24` | Stub LLM para tests |
| `_Server` + `_free_port()` | `test_full_flow.py:34` | Servidor de pruebas |
| `_create_sample_pdf()` | `test_full_flow.py:73` | PDF de prueba |
| `cli_main()` | `main.py:549` | Entry point para tests |

**No se modifica:** cliente HTTP, servidor, persistencia, ni lógica de lectura.

## `next-block`

### Semántica

GET current-block → imprimir texto → POST complete-block

### `cmd_next_block()`

1. `c.get_current_block(study_id)` → captura `SocraticAPIError`
2. Si error 400 con "no tiene bloque actual" → stderr `"El estudio ha llegado al final del documento."` → return 0
3. Si otro error → stderr detalle → return 1
4. Imprime `block_data["text"]` a stdout (única salida en modo normal)
5. Si `args.verbose` → imprime metadatos con `_print_kv()`
6. `c.complete_block(study_id, block_data["id"])` → captura error → stderr + return 1
7. return 0

### Parser

```
p = sub.add_parser("next-block", help="Avanzar al siguiente bloque de lectura")
p.add_argument("study_id")
p.add_argument("--verbose", action="store_true", help="Mostrar metadatos del bloque")
p.set_defaults(func=cmd_next_block)
```

### Fin de documento

Cuando `current-block` devuelve 400 "no tiene bloque actual":
- stderr: "El estudio ha llegado al final del documento."
- return 0 (distinguible de fallo técnico por el mensaje)

## `previous-block`

### Semántica

GET study → GET document → encontrar bloque anterior por ordinal → imprimir texto

No modifica el estado del estudio. Es navegación de solo lectura.

### `cmd_previous_block()`

1. `c.get_study(study_id)` → obtengo `current_block_id` y `document_id`
2. Si error → stderr + return 1
3. `c.get_document(document_id)` → obtengo todos los bloques del documento
4. Si error → stderr + return 1
5. Encuentro el bloque actual en la lista por `id`
6. Si índice == 0 → stderr `"Ya estás en el primer bloque."` → return 1
7. Obtengo bloque en `índice - 1`
8. Imprime `block["text"]` a stdout
9. Si `args.verbose` → imprime metadatos con `_print_kv()`
10. return 0

### Parser

```
p = sub.add_parser("previous-block", help="Retroceder al bloque anterior")
p.add_argument("study_id")
p.add_argument("--verbose", action="store_true", help="Mostrar metadatos del bloque")
p.set_defaults(func=cmd_previous_block)
```

### Comportamiento

- No completa ningún bloque
- No modifica `current_block_id` del estudio
- Muestra el bloque con ordinal anterior al actual
- Si ya está en el primer bloque → error en stderr, return 1

## Tests

### `socratic-cli/tests/test_next_block.py` (nuevo)

7 tests para `next-block` usando el patrón `_Server` + `_create_sample_pdf` + `cli_main` + `SocraticClient`:

1. **test_next_block_gets_prints_and_completes** — Crea estudio, llama next-block, verifica stdout contiene texto, verifica con cliente que se completó
2. **test_next_block_uses_correct_block_id** — Verifica que el block_id usado en complete-block es el devuelto por current-block
3. **test_next_block_consecutive_returns_different_blocks** — Dos llamadas consecutivas devuelven bloques distintos
4. **test_next_block_get_error_no_complete** — Study inexistente (404) no llama a complete-block
5. **test_next_block_complete_error** — Simular error en POST complete-block (block_id inválido → 400)
6. **test_next_block_end_of_document** — Estudio de 1 bloque: primera llamada OK, segunda devuelve mensaje de fin
7. **test_next_block_stdout_only_text** — Verificar que stdout en modo normal contiene SOLO el texto del bloque

### `socratic-cli/tests/test_previous_block.py` (nuevo)

7 tests para `previous-block` usando el mismo patrón:

1. **test_previous_block_moves_back** — Crea estudio, completa bloque 1, previous-block muestra bloque 0
2. **test_previous_block_uses_previous_ordinal** — Verifica que se usa el bloque anterior por ordinal, no por ID
3. **test_previous_block_consecutive_moves_back_twice** — Dos llamadas consecutivas retroceden bloques distintos
4. **test_previous_block_first_block_error** — Ya en primer bloque → stderr "Ya estás en el primer bloque." → return 1
5. **test_previous_block_study_not_found** — Study inexistente (404) → error → return 1
6. **test_previous_block_no_state_change** — Previous-block no modifica current_block_id del estudio
7. **test_previous_block_stdout_only_text** — Verificar que stdout en modo normal contiene SOLO el texto del bloque

## Ejemplos de uso

```bash
# Avanzar: obtiene bloque, imprime texto, lo completa
socratic next-block <study-id>

# Retroceder: muestra bloque anterior sin modificar estado
socratic previous-block <study-id>

# Con metadatos
socratic next-block --verbose <study-id>
socratic previous-block --verbose <study-id>
```

## Ejecución de pruebas

```bash
cd socratic-cli && python -m pytest tests/test_next_block.py tests/test_previous_block.py -v
    ```
