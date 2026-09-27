"""FastAPI application factory. Run with: `uvicorn app.main:create_app --factory`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.routers import health, system
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.runtime import apply_process_env, ensure_data_dirs

logger = logging.getLogger(__name__)

API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    apply_process_env(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_data_dirs(settings)
        logger.info(
            "startup",
            extra={
                "app_env": settings.app_env.value,
                "offline_mode": settings.offline_mode,
                "fake_providers": settings.enable_fake_providers,
            },
        )
        yield
        logger.info("shutdown")

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(system.router, prefix=API_PREFIX)
    return app
