# Socratic

Socratic es una aplicación de estudio interactivo que transforma cualquier documento PDF en una conversación guiada. Mientras recorres un PDF, puedes interrumpir la lectura para hacer preguntas, pedir aclaraciones, solicitar ejemplos o repetir fragmentos, y continuar exactamente donde te quedaste.

El sistema está formado por:

- **`socratic-server/`** — servidor FastAPI con la lógica de dominio, persistencia SQLite y extracción de PDFs.
- **`socratic-cli/`** — cliente CLI en Python que consume la API pública (pendiente).

## Flujo básico

PDF → procesamiento → lectura de bloques → pregunta contextual → respuesta → reanudación

## Instalación y ejecución

### Requisitos

- Python 3.12+
- pip

### Pasos

```bash
# 1. Entrar en el directorio del servidor
cd socratic-server

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 4. Instalar dependencias (incluye dev)
pip install -e ".[dev]"

# 5. Ejecutar servidor
python -m main
```

El servidor estará disponible en `http://127.0.0.1:8880`.

Documentación interactiva: `http://127.0.0.1:8880/docs` (Swagger UI).

### Ejecutar tests

```bash
cd socratic-server
python -m pytest tests/ -v
```

Los tests cubren:
- Subida de documentos PDF
- Listado de documentos
- Recuperación de detalle
- Manejo de errores (archivos no PDF, nombres vacíos)
- Persistencia en SQLite

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/documents` | Cargar un PDF. Extrae bloques ordenados y los persiste. |
| GET | `/documents` | Listar documentos. |
| GET | `/documents/{id}` | Detalle de un documento y sus bloques. |

## Estructura del servidor

```
socratic-server/
├── src/socratic/            # Paquete principal (src-layout)
│   ├── domain/              # Modelos (Document, ContentBlock)
│   ├── storage/             # Persistencia SQLite
│   ├── pdf/                 # Extracción de bloques (pdfplumber)
│   ├── api/                 # Endpoints REST
│   └── config/              # Configuración
├── main.py                  # Entry point FastAPI
├── tests/                   # Tests
├── data/                    # Base de datos SQLite
└── pyproject.toml           # Dependencias y configuración
```

## Estado actual

Hito 1 completado: carga y extracción de PDFs con persistencia en SQLite.
Hito 2 en plan: creación de estudio y lectura secuencial de bloques.

Plan completo: [docs/implementation-plan.md](docs/implementation-plan.md)
Contexto del producto: [docs/product-context.md](docs/product-context.md)
Metodología de documentación: [docs/documentation-methodology.md](docs/documentation-methodology.md)
API pública: [docs/api.md](docs/api.md)
Arquitectura del servidor: [docs/architecture.md](docs/architecture.md)
