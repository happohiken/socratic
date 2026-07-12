from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socratic.api.documents import router as documents_router
from socratic.config.settings import Settings
from socratic.storage.database import DB, init_db

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = init_db(settings.storage_path)
    app.state.db = db
    yield
    db.close()


app = FastAPI(
    title="Socratic Server",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
