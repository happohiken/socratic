# Arquitectura del Servidor

`socratic-server/` — servidor FastAPI con persistencia SQLite, siguiendo `src-layout`.

## Estructura

```
socratic-server/
├── src/socratic/            # Paquete principal (src-layout)
│   ├── domain/              # Modelos de dominio
│   │   ├── models.py        # Document, ContentBlock
│   │   └── __init__.py
│   ├── storage/             # Capa de persistencia
│   │   ├── database.py      # Conexión SQLite, CRUD
│   │   └── __init__.py
│   ├── pdf/                 # Procesamiento de PDFs
│   │   ├── parser.py        # Extracción de bloques con pdfplumber
│   │   └── __init__.py
│   ├── api/                 # Endpoints REST
│   │   ├── documents.py     # POST/GET /documents
│   │   └── __init__.py
│   ├── config/              # Configuración
│   │   ├── settings.py      # Pydantic BaseSettings
│   │   └── __init__.py
│   └── __init__.py
├── main.py                  # Entry point, configuración FastAPI
├── tests/
│   ├── test_document.py     # Tests de endpoints
│   └── __init__.py
├── data/                    # Base de datos SQLite (socratic.db)
├── pyproject.toml           # Dependencias y configuración de paquete
└── .gitignore
```

## Layout `src`

El paquete vive dentro de `src/` (estándar en proyectos Python profesionales):

- Evita que tests y herramientas usen el paquete sin instalar.
- Permite múltiples versiones del mismo paquete en el mismo entorno.
- `pyproject.toml` indica `where = ["src"]` para que setuptools lo encuentre.

## Componentes

### `main.py`
Inicializa FastAPI, incluye router de documentos, configura CORS.

### `socratic/domain/models.py`
Modelos Pydantic:
- `Document`: id, filename, size, created_at
- `ContentBlock`: id, document_id, order, content, created_at

### `socratic/storage/database.py`
Conexión SQLite via stdlib `sqlite3`. CRUD para Document y ContentBlock.

### `socratic/pdf/parser.py`
Extracción de texto con `pdfplumber`. Agrupa palabras por coordenada Y (tolerancia 5px) en líneas, luego en bloques.

### `socratic/api/documents.py`
Endpoints REST:
- `POST /documents` — Subida y extracción
- `GET /documents` — Listado
- `GET /documents/{id}` — Detalle con bloques

### `socratic/config/settings.py`
`DATABASE_URL` con default `sqlite:///./data/socratic.db`.

## Decisiones

- **sqlite3 stdlib** en vez de SQLAlchemy: simplicidad para Hito 1.
- **pdfplumber** en vez de PyMuPDF: licencia MIT, bueno para PDFs de una columna.
- **UUID** para identificadores: compatible con API pública y distribuido.
- **Pydantic Settings**: configuración externalizada via环境变量.

## Despliegue

```bash
cd socratic-server
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m main
```

Puerto por defecto: `8885`.
Base de datos por defecto: `socratic-server/data/socratic.db`.
