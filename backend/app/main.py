"""Application entrypoint.

Built as a factory rather than a module-level singleton so tests can construct
isolated instances with overridden dependencies instead of mutating global state.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Own startup and shutdown for process-wide resources."""
    configure_logging(debug=settings.debug, json_output=settings.is_production)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "application_starting",
        extra={"environment": settings.environment, "version": settings.app_version},
    )

    yield

    from app.db.session import dispose_engine

    await dispose_engine()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Construct and configure the ASGI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend for a Signal-style secure messaging platform. "
            "REST for state changes, WebSockets for live delivery."
        ),
        lifespan=lifespan,
        # Interactive docs are a development affordance, not a production surface.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # refresh token travels in an httpOnly cookie
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
