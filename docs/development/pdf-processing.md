# Procesamiento de PDFs

`socratic-server/src/socratic/document_processing/` — parser documental
compartido entre `socratic inspect-pdf` (CLI) y `POST /documents`
(servidor).

## Modelo (`model.py`)

```python
@dataclass
class TocEntry:
    title: str
    level: int
    page_number: int | None = None

@dataclass
class FontInfo:
    name: str
    size: float
    bold: bool = False
    italic: bool = False

@dataclass
class ListItem:
    text: str
    marker: str

@dataclass
class DocumentNode:
    id: int                                      # ordinal de aparición durante parsing
    node_type: Literal["heading", "paragraph", "list", "unknown"]
    text: str
    page_number: int
    ordinal: int                                 # orden de lectura
    level: int | None = None
    parent_id: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    font: FontInfo | None = None
    list_items: list[ListItem] | None = None
    is_ordered: bool = False

@dataclass
class ParsedDocument:
    title: str | None = None
    toc: list[TocEntry] = field(default_factory=list)
    nodes: list[DocumentNode] = field(default_factory=list)
```

## Extractor (`extractor.py`)

```python
def parse_pdf(pdf_path: Path, page_range: tuple[int, int] | None = None) -> ParsedDocument: ...
```

Pipeline (729 líneas, las más grandes del servidor):

1. **Extracción cruda** con `pdfplumber`: texto con info de fuentes,
   `bbox`, página. Opcionalmente filtrado por `page_range`.
2. **Detección de TOC**: si `pypdf` está instalado (extra opcional
   `pip install -e ".[pdf]"`), lee `reader.outline` y construye
   `TocEntry`. Si no, se omite.
3. **Detección de cabeceras/pies**: analiza repeticiones en bordes
   superior/inferior de páginas y las elimina.
4. **Fusión de líneas en párrafos**: umbral dinámico basado en fuente
   y posición. Corrige palabras partidas por guiones al final de línea.
5. **Clasificación de nodos** vía `classify_node()`.
6. **Agrupación de `list_item`** en nodos `list` con `list_items` y
   `is_ordered`.
7. **Ordenación** por coordenadas de lectura (top-left a bottom-right
   dentro de cada página).
8. **Asignación de `ordinal`** secuencial tras el ordenamiento.
9. **Construcción de `ParsedDocument`** con `title` (del TOC si existe,
   si no del primer heading), `toc` y `nodes`.

## Clasificador (`classifier.py`)

```python
def classify_node(text: str, font: FontInfo) -> tuple[str, int | None]: ...
```

Reglas (en orden):

1. Si texto vacío → `("paragraph", None)`.
2. Si `font.size > 0 and font.bold` → `("heading", 1)`.
3. Si empieza por prefijo de lista (ver `_LIST_PREFIXES`) →
   `("list_item", None)`.
4. Si `_looks_like_heading` → `("heading", 2)`.
5. Default → `("paragraph", None)`.

`_looks_like_heading`:
- `font.size >= 14` y `len(text) <= 100` → True.
- `len(text) <= 60`, no termina en puntuación y `font.bold` → True.

`_LIST_PREFIXES` incluye viñetas Unicode (`•`, `–`, `—`, `○`, `●`,
`■`, `◦`, `▸`, etc.) y el guion `-`. Los patrones `1.`, `a)`, `IV:`
se detectan con regex.

`_starts_with_list_prefix` y `_is_list_item` exponen la detección para
que el extractor agrupe ítems en nodos `list`.

## Adaptador (`adapter.py`)

```python
def parsed_to_document(parsed: ParsedDocument, filename: str) -> Document: ...
def parsed_to_content_blocks(document_id: str, parsed: ParsedDocument) -> list[ContentBlock]: ...
```

### `parsed_to_document`

- `page_count` = número de páginas distintas en los nodos.
- `block_count` = `len(parsed.nodes)`.
- `metadata` = `{"title": parsed.title, "toc": _toc_to_dict(parsed.toc)}`.

### `parsed_to_content_blocks`

Para cada `DocumentNode`:
- Conserva `bbox` (como lista), `font` (como dict vía `asdict`) y
  `level` en `ContentBlock.metadata`.
- Fusiona `node_type` `"list_item"` y `"list"` en `block_type="list"`.
- Mantiene `ordinal` y `page_number` del nodo.

> **Identificadores**: `DocumentNode.id` es un entero secuencial
> asignado durante el parsing. **No** se reutiliza como
> `ContentBlock.id` (que es UUID). El id del nodo cambia si se
> re-parsea con parámetros distintos; el UUID del bloque es estable
> durante la vida del documento persistido.

## Formatters (`formatters.py`)

```python
def format_text(doc: ParsedDocument) -> str: ...
def format_json(doc: ParsedDocument) -> str: ...
```

Usados por `socratic inspect-pdf` para diagnosticar la descomposición
sin subir el PDF al servidor.

### `format_text`

Salida legible con:
- `Document title: ...` (si existe)
- `TOC:` con entradas y página
- Por cada nodo: `[id] page=N type=T [level=L] [font=...] [bbox=...]`
  seguido del texto.

### `format_json`

JSON con `title`, `toc` y `nodes` (todos los campos del nodo, incluidos
`list_items` e `is_ordered` si aplica).

## Uso

### Desde el servidor (`api/documents.py`)

```python
parsed = parse_pdf(tmp_path)
doc = parsed_to_document(parsed, file.filename)
save_document(db.conn, doc)
blocks = parsed_to_content_blocks(doc.id, parsed)
save_content_blocks(db.conn, doc.id, blocks)
```

### Desde la CLI (`inspect_pdf.py`)

```python
doc = parse_pdf(pdf_path, page_range)
output = format_json(doc) if args.format == "json" else format_text(doc)
```

No requiere servidor corriendo.

## Riesgos conocidos

- PDFs con fuentes embebidas no estándar pueden producir texto
  degradado.
- Layouts de dos columnas pueden mezclar bloques (la ordenación por
  coordenadas ayuda pero no es perfecta).
- PDFs escaneados (imagen) requieren OCR, fuera del MVP.
- Tablas y fórmulas no se procesan específicamente; se tratan como
  texto plano.
