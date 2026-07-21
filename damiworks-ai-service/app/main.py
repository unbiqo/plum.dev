from __future__ import annotations

import logging

from fastapi import FastAPI

from .api import router
from .booking_provider import DemoBookingProvider, SupabaseAppointmentStore
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
    # Demo booking provider backed by the demo_appointments table. Opt-in via
    # DEMO_BOOKING_PROVIDER_ENABLED; when off, the medical demo keeps its legacy
    # fictional-slot flow. When on and the table is missing, reads degrade to
    # "all free" and writes are declined, so the bot falls back — never a 500.
    app.state.booking_provider = (
        DemoBookingProvider(SupabaseAppointmentStore(app.state.supabase.client))
        if settings.demo_booking_provider_enabled
        else None
    )
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
