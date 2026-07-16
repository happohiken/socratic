# Modelo de dominio y persistencia

## Modelos (`socratic-server/src/socratic/domain/models.py`)

Dataclasses con UUID auto-generado (`uuid.uuid4()`) y `datetime`
UTC (`datetime.now(timezone.utc)`).

### `Document`

```python
@dataclass
class Document:
    id: str                       # UUID auto
    filename: str = ""
    page_count: int = 0
    block_count: int = 0
    format: str = "pdf"
    metadata: dict = field(default_factory=dict)
    created_at: datetime          # UTC auto
    updated_at: datetime          # UTC auto

    def touch(self) -> None: ...  # actualiza updated_at
```

`metadata` almacena información como `title` y `toc` del PDF (en
`parsed_to_document`).

### `ContentBlock`

```python
@dataclass
class ContentBlock:
    id: str                       # UUID auto
    document_id: str = ""
    ordinal: int = 0              # orden de lectura, NO identificador
    text: str = ""
    page_number: int = 0
    block_type: str = "paragraph" # paragraph | heading | list | unknown
    metadata: dict = field(default_factory=dict)
```

`metadata` guarda `bbox` (lista), `font` (dict con name, size, bold,
italic) y `level` (encabezados) provenientes del parser.

### `Study`

```python
@dataclass
class Study:
    id: str                       # UUID auto
    document_id: str = ""
    current_block_id: Optional[str] = None
    last_completed_block_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    def touch(self) -> None: ...
```

`current_block_id=None` indica fin de documento.
`last_completed_block_id` permite retroceder desde el final.

### `Message`

```python
@dataclass
class Message:
    id: str                       # UUID auto
    study_id: str = ""
    content_block_id: Optional[str] = None  # bloque que originó la pregunta
    role: str = ""                # user | assistant
    content: str = ""
    created_at: datetime
```

## SQLite (`socratic-server/src/socratic/storage/database.py`)

### `DB` dataclass

```python
@dataclass
class DB:
    conn: sqlite3.Connection
    path: Path

    def close(self) -> None: ...
```

### `init_db(path) -> DB`

```python
def init_db(path: Path) -> DB:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    return DB(conn=conn, path=path)
```

- `check_same_thread=False` para FastAPI multi-hilo.
- `WAL` mejora concurrencia de lectura.
- `foreign_keys=ON` activa `ON DELETE CASCADE`.

### Esquema SQL

```sql
CREATE TABLE documents (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    page_count  INTEGER NOT NULL DEFAULT 0,
    block_count INTEGER NOT NULL DEFAULT 0,
    format      TEXT NOT NULL DEFAULT 'pdf',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE content_blocks (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal      INTEGER NOT NULL,
    text         TEXT NOT NULL,
    page_number  INTEGER NOT NULL DEFAULT 0,
    block_type   TEXT NOT NULL DEFAULT 'paragraph',
    metadata     TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, ordinal)
);

CREATE TABLE studies (
    id                      TEXT PRIMARY KEY,
    document_id             TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    current_block_id        TEXT,
    last_completed_block_id TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE messages (
    id               TEXT PRIMARY KEY,
    study_id         TEXT NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    content_block_id TEXT,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
```

`metadata` de `content_blocks` se guarda como JSON text y se parsea al
leer. Las fechas se guardan como ISO 8601 text y se convierten a
`datetime` al leer.

### Funciones CRUD

**Documentos:**
- `save_document(conn, doc)` — INSERT.
- `update_document(conn, doc)` — UPDATE por id.
- `get_document(conn, doc_id) -> Document | None`.
- `list_documents(conn) -> list[Document]` — ordenado por `created_at DESC`.
- `delete_document(conn, doc_id) -> bool` — DELETE que dispara CASCADE;
  devuelve `True` si borró algo.

**Bloques:**
- `save_content_blocks(conn, document_id, blocks)` — batch INSERT con
  `executemany`; actualiza `block_count` del documento.
- `get_content_blocks(conn, document_id) -> list[ContentBlock]` —
  ordenado por `ordinal`.
- `get_content_block(conn, block_id) -> ContentBlock | None`.

**Estudios:**
- `save_study`, `update_study`, `get_study`, `list_studies` (ordenado
  por `created_at DESC`).

**Mensajes:**
- `save_message`.
- `get_messages_for_study(conn, study_id) -> list[Message]` — ordenado
  por `created_at ASC`.

## Invariantes

1. `ContentBlock.id` es **UUID estable**, no el ordinal. La posición
   de lectura referencia el id, no el ordinal.
2. Borrado de documento → CASCADE a bloques, estudios y mensajes.
3. Borrado de estudio → CASCADE a mensajes.
4. `block_type` admite `list` (el adapter fusiona `list_item` y `list`
   en `list`).
5. `metadata` se serializa como JSON text en `content_blocks.metadata`.
6. `current_block_id=None` indica fin de documento (no confundir con
   "no inicializado": al crear el estudio se asigna el primer bloque).
7. `last_completed_block_id` solo se setea al completar un bloque.

## Navegación (`socratic-server/src/socratic/services/navigation.py`)

`NavigationService(db)` centraliza operaciones de lectura. Es la única
vía desde las tools (no tocan SQLite directo). Persiste y commitea en
cada llamada.

```python
class NavigationError(Exception): ...

class NavigationService:
    def __init__(self, db: DB) -> None: ...

    def get_current_block(self, study: Study) -> ContentBlock | None: ...
    def complete_block(self, study: Study, block_id: str) -> ContentBlock | None: ...
    def complete_current_block(self, study: Study) -> ContentBlock | None: ...
    def previous_block(self, study: Study) -> ContentBlock: ...
```

### `complete_block(study, block_id)`

1. Obtiene todos los bloques del documento.
2. Valida que `block_id` pertenezca al documento (si no,
   `NavigationError`).
3. Si no es el último, `current_block_id = block_ids[current_index + 1]`;
   si es el último, `current_block_id = None`.
4. `last_completed_block_id = block_id`.
5. `study.touch()`, `update_study`, `commit`.
6. Devuelve el nuevo `ContentBlock` o `None` si fin de documento.

### `previous_block(study)`

1. Obtiene todos los bloques del documento.
2. Si `current_block_id is None` (fin de documento): si
   `last_completed_block_id is None`, error; si no, vuelve a
   `last_completed_block_id`.
3. Si no está al final: si `current_index == 0`, error ("Ya estás en
   el primer bloque"); si no, retrocede uno.
4. `study.touch()`, `update_study`, `commit`.
5. Devuelve el nuevo `ContentBlock`.

`NavigationError` es la excepción de dominio para operaciones
inválidas (sin bloque actual, primer bloque, bloque ajeno al
documento, sin bloques completados para retroceder).
