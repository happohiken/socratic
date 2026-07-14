# Socratic Server

Servidor de Socratic para la gestión de documentos PDF y estudio secuencial.

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -e .

# Instalar dependencias de desarrollo
pip install -e ".[dev]"
```

## Uso

```bash
# Ejecutar el servidor
python -m main

# El servidor estará disponible en http://localhost:8885
# Documentación interactiva en http://localhost:8885/docs
```

## Pruebas

```bash
# Ejecutar todos los tests
pytest tests/

# Ejecutar tests con salida detallida
pytest tests/ -v
```

## Endpoints principales

- `POST /documents` — Subir documento PDF
- `GET /documents` — Listar documentos
- `GET /documents/{id}` — Obtener documento con bloques
- `POST /studies` — Crear estudio para un documento
- `GET /studies` — Listar estudios
- `GET /studies/{id}` — Consultar estado de un estudio
- `GET /studies/{id}/current-block` — Obtener bloque actual
- `POST /studies/{id}/blocks/{blockId}/complete` — Marcar bloque como completado
- `GET /studies/{id}/messages` — Obtener historial de mensajes
- `POST /studies/{id}/messages` — Crear mensaje
- `POST /studies/{id}/ask` — Pregunta contextual con contexto ampliado
- `POST /documents/{id}/reindex` — Indexar documento para recuperación (202)
- `POST /documents/{id}/search` — Buscar bloques relevantes (diagnóstico)

## Acceso por LAN

El servidor escucha en `0.0.0.0:8885`, permitiendo acceso desde otras máquinas en la red local.

Accede desde otro equipo en la misma red usando:
```
http://<IP_DEL_SERVIDOR>:8885
```

La dirección IP la puedes obtener con `hostname -I` o `ifconfig`.

## Documentación

- [Documentación de la API](../docs/api.md) — Especificación completa de endpoints.
- [Arquitectura](../docs/architecture.md) — Descripción de la estructura del código.

## Estructura del proyecto

```
src/socratic/
├── app.py                # Factory create_app(storage_path)
├── api/
│   ├── documents.py      # Endpoints de documentos
│   ├── studies.py        # Endpoints de estudios y mensajes
│   ├── ask.py            # Preguntas contextuales (contexto ampliado)
│   └── retrieval.py      # Indexación y búsqueda de diagnóstico
├── config/
│   └── settings.py       # Configuración de la aplicación
├── domain/
│   └── models.py         # Modelos de dominio
├── pdf/
│   └── parser.py         # Parser de PDFs con pdfplumber
├── document_processing/  # Parser documental (extractor + adapter)
├── llm/                  # Interfaz LLM + implementación OpenAI
├── retrieval/            # Indexación y recuperación documental (txtai)
│   ├── models.py         # RetrievedBlock, DocumentRetriever, Context
│   ├── txtai_backend.py  # TxtaiDocumentRetriever
│   └── service.py        # RetrievalService
└── storage/
    └── database.py       # Acceso a base de datos SQLite
```

## Licencia

Propiedad de Socratic. Todos los derechos reservados.
