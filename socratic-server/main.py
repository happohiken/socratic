from __future__ import annotations

import uvicorn

from socratic.app import create_app
from socratic.config.settings import Settings

settings = Settings()
app = create_app(settings.storage_path)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
