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
from app.api.routers import (
    assets,
    characters,
    consents,
    health,
    jobs,
    models,
    products,
    projects,
    properties,
    system,
)
from app.api.routers import (
    settings as settings_router,
)
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.runtime import apply_process_env, ensure_data_dirs
from app.db.migrations import upgrade_to_head
from app.db.session import create_db_engine, create_session_factory
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    apply_process_env(settings)

    assert settings.database_url is not None
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_data_dirs(settings)
        if settings.auto_migrate:
            upgrade_to_head(settings.database_url)  # type: ignore[arg-type]
        logger.info(
            "startup",
            extra={
                "app_env": settings.app_env.value,
                "offline_mode": settings.offline_mode,
                "fake_providers": settings.enable_fake_providers,
            },
        )
        yield
        engine.dispose()
        logger.info("shutdown")

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.storage = StorageService(settings.data_dir)

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

    for router in (
        health.router,
        system.router,
        assets.router,
        consents.router,
        characters.router,
        products.router,
        properties.router,
        projects.router,
        jobs.router,
        models.router,
        settings_router.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app
