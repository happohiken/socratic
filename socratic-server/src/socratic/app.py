from __future__ import annotations

from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socratic.api.ask import get_llm, router as ask_router
from socratic.api.documents import router as documents_router
from socratic.api.retrieval import router as retrieval_router
from socratic.api.studies import router as studies_router
from socratic.config.settings import Settings
from socratic.llm.base import LLMClient
from socratic.llm.openai_client import OpenAIClient
from socratic.retrieval import RetrievalService, TxtaiDocumentRetriever
from socratic.storage.database import init_db

settings = Settings()


def create_app(
    storage_path: Path | None = None,
    llm_client: LLMClient | None = None,
    **kwargs: Any,
) -> FastAPI:
    """Construye una instancia de FastAPI con persistencia en `storage_path`.

    La BD se inicializa al construir la app para que `app.state.db` esté
    disponible sin depender de que el lifespan startup se ejecute (los tests
    con ASGITransport no disparan el lifespan). El shutdown cierra la conexión.
    Permite simular reinicios creando una nueva app apuntando al mismo archivo.
    """
    db_path = storage_path or settings.storage_path
    db = init_db(db_path)

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
    app.state.llm = llm_client or OpenAIClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )

    # Crear y configurar el servicio de recuperación
    retriever = TxtaiDocumentRetriever(
        storage_path=settings.retrieval_storage,
        embedding_model=settings.embedding_model,
    )
    retriever.load()
    retrieval_service = RetrievalService(retriever=retriever, db=db)
    app.state.retrieval = retrieval_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(documents_router)
    app.include_router(studies_router)
    app.include_router(ask_router)
    app.include_router(retrieval_router)
    return app
