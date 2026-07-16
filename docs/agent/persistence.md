# Dominio y persistencia (agentes)

## Modelos (`socratic-server/src/socratic/domain/models.py`)

Dataclasses con UUID auto-generado y `datetime` UTC:

- **`Document`**: `id`, `filename`, `page_count`, `block_count`, `format`,
  `metadata: dict`, `created_at`, `updated_at`. Método `touch()`.
- **`ContentBlock`**: `id`, `document_id`, `ordinal`, `text`,
  `page_number`, `block_type` (`paragraph` | `heading` | `list` | `unknown`),
  `metadata: dict` (bbox, font, level).
- **`Study`**: `id`, `document_id`, `current_block_id`, `last_completed_block_id`,
  `created_at`, `updated_at`. Método `touch()`.
- **`Message`**: `id`, `study_id`, `content_block_id` (opcional),
  `role` (`user` | `assistant`), `content`, `created_at`.

## SQLite (`socratic-server/src/socratic/storage/database.py`)

- `DB` dataclass: `conn: sqlite3.Connection`, `path: Path`.
- `init_db(path) -> DB`: crea directorio padre, activa `WAL` y
  `foreign_keys=ON`, crea tablas si no existen.
- `check_same_thread=False` (FastAPI).

### Tablas

- `documents` (PK `id`)
- `content_blocks` (PK `id`, FK `document_id` → documents **CASCADE**,
  `UNIQUE(document_id, ordinal)`)
- `studies` (PK `id`, FK `document_id` → documents **CASCADE**)
- `messages` (PK `id`, FK `study_id` → studies **CASCADE**)

### Funciones CRUD

- Documentos: `save_document`, `update_document`, `get_document`,
  `list_documents`, `delete_document` (vía CASCADE, devuelve `bool`).
- Bloques: `save_content_blocks` (batch + actualiza `block_count`),
  `get_content_blocks` (ordenado por `ordinal`),
  `get_content_block`.
- Estudios: `save_study`, `update_study`, `get_study`, `list_studies`.
- Mensajes: `save_message`, `get_messages_for_study` (ordenado por
  `created_at` ASC).

## Invariantes

- `ContentBlock.id` es UUID estable, **no** el ordinal. La posición de
  lectura referencia el id, no el ordinal.
- Borrado de documento → CASCADE a bloques, estudios y mensajes.
- Borrado de estudio → CASCADE a mensajes.
- `block_type` admite `list` (fusión de `list_item` y `list` en el adapter).
- `metadata` se serializa como JSON text en `content_blocks.metadata`.

## Navegación (`socratic-server/src/socratic/services/navigation.py`)

`NavigationService(db)` centraliza operaciones de lectura. Es la única
vía desde las tools (no tocan SQLite directo).

- `get_current_block(study) -> ContentBlock | None`
- `complete_block(study, block_id) -> ContentBlock | None` — valida
  pertenencia al documento, avanza o pone `None` al final, actualiza
  `last_completed_block_id`, persiste y commitea.
- `complete_current_block(study)` — comodín; lanza `NavigationError` si
  no hay bloque actual.
- `previous_block(study) -> ContentBlock` — si está al final
  (`current_block_id=None`) vuelve a `last_completed_block_id`; lanza
  `NavigationError` si no hay a dónde retroceder.

`NavigationError` es la excepción de dominio para operaciones
inválidas (sin bloque actual, primer bloque, bloque ajeno).
