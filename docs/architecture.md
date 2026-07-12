# Arquitectura del Servidor

`socratic-server/` — servidor FastAPI con persistencia SQLite, siguiendo `src-layout`.

## Estructura

```
socratic-server/
├── src/socratic/            # Paquete principal (src-layout)
│   ├── domain/              # Modelos de dominio
│   │   ├── models.py        # Document, ContentBlock, Study, Message
│   │   └── __init__.py
│   ├── storage/             # Capa de persistencia
│   │   ├── database.py      # Conexión SQLite, CRUD
│   │   └── __init__.py
│   ├── pdf/                 # Procesamiento de PDFs
│   │   ├── parser.py        # Extracción de bloques con pdfplumber
│   │   └── __init__.py
│   ├── api/                 # Endpoints REST
│   │   ├── documents.py     # POST/GET /documents
│   │   ├── studies.py       # Endpoints de estudios y mensajes
│   │   └── __init__.py
│   ├── config/              # Configuración
│   │   ├── settings.py      # Pydantic BaseSettings
│   │   └── __init__.py
│   └── __init__.py
├── main.py                  # Entry point, configuración FastAPI
├── tests/
│   ├── test_document.py     # Tests de documentos
│   ├── test_study.py        # Tests de estudios y mensajes
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
Inicializa FastAPI, incluye routers de documentos y estudios, configura CORS.

### `socratic/domain/models.py`
Modelos de dominio:
- `Document`: id, filename, page_count, block_count, format, created_at, updated_at
- `ContentBlock`: id, document_id, ordinal, text, page_number, block_type, metadata
- `Study`: id, document_id, current_block_id, last_completed_block_id, created_at, updated_at
- `Message`: id, study_id, content_block_id, role, content, created_at

### `socratic/storage/database.py`
Conexión SQLite via stdlib `sqlite3` con `check_same_thread=False` para soporte multi-hilo. CRUD para Document, ContentBlock, Study y Message. Tablas: documents, content_blocks, studies, messages.

### `socratic/pdf/parser.py`
Extracción de texto con `pdfplumber`. Agrupa palabras por coordenada Y (tolerancia 5px) en líneas, luego en bloques. Clasifica bloques como paragraph, heading, list o unknown.

### `socratic/api/documents.py`
Endpoints REST:
- `POST /documents` — Subida y extracción
- `GET /documents` — Listado
- `GET /documents/{id}` — Detalle con bloques

### `socratic/api/studies.py`
Endpoints REST para estudios y mensajes:
- `POST /studies` — Crear estudio para un documento
- `GET /studies` — Listar estudios
- `GET /studies/{id}` — Consultar estado
- `GET /studies/{id}/current-block` — Obtener bloque actual (no avanza)
- `POST /studies/{id}/blocks/{blockId}/complete` — Marcar completado y avanzar
- `GET /studies/{id}/messages` — Obtener historial
- `POST /studies/{id}/messages` — Crear mensaje

### `socratic/config/settings.py`
Configuración de la aplicación:
- `storage_path`: ruta a la base de datos SQLite (default: `data/socratic.db`)
- `host`: interfaz de escucha (default: `0.0.0.0`)
- `port`: puerto (default: `8885`)

## Decisiones

- **sqlite3 stdlib** en vez de SQLAlchemy: simplicidad para Hito 1.
- **pdfplumber** en vez de PyMuPDF: licencia MIT, bueno para PDFs de una columna.
- **UUID** para identificadores: compatible con API pública y distribuido.
- **Pydantic Settings**: configuración externalizada via环境变量.
- **check_same_thread=False**: permite usar la misma conexión SQLite en hilos asíncronos de FastAPI.
- **src-layout**: estándar en proyectos Python profesionales, evita problemas de importación en tests.

## Despliegue

```bash
cd socratic-server
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m main
```

Puerto por defecto: `8885`.
Base de datos por defecto: `socratic-server/data/socratic.db`.
