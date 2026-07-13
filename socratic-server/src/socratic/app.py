from __future__ import annotations

from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socratic.api.documents import router as documents_router
from socratic.api.studies import router as studies_router
from socratic.storage.database import init_db


def create_app(storage_path: Path) -> FastAPI:
    """Construye una instancia de FastAPI con persistencia en `storage_path`.

    La BD se inicializa al construir la app para que `app.state.db` esté
    disponible sin depender de que el lifespan startup se ejecute (los tests
    con ASGITransport no disparan el lifespan). El shutdown cierra la conexión.
    Permite simular reinicios creando una nueva app apuntando al mismo archivo.
    """
    db = init_db(storage_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            db.close()

    app = FastAPI(
        title="Socratic Server",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(documents_router)
    app.include_router(studies_router)
    return app
