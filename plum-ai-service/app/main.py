from __future__ import annotations

import logging

from fastapi import FastAPI

from .api import router
from .config import get_settings
from .gemini_service import GeminiService
from .supabase_service import SupabaseService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Development Sales Service",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.gemini = GeminiService(settings)
    app.state.supabase = SupabaseService(settings)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
