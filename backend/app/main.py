"""TradeBay FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import NotReadyError, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.health import mongodb_is_healthy
from app.db.mongodb import mongo_manager
from app.shared.schemas.response import success

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger.info("application_starting", env=settings.app_env, app=settings.app_name)
    from app.modules.identity.email import configure_email_sender

    configure_email_sender(settings)
    await mongo_manager.connect(settings)
    yield
    await mongo_manager.disconnect()
    logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "TradeBay modular monolith API. "
            "Domains: Identity, Catalog, Procurement, Finance, Platform Money, Trust, AI."
        ),
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> dict[str, Any]:
        return success(
            {
                "status": "ok",
                "app": settings.app_name,
                "env": settings.app_env,
            }
        )

    @app.get("/ready", tags=["Health"], summary="Readiness probe (MongoDB)")
    async def ready() -> dict[str, Any]:
        healthy = await mongodb_is_healthy()
        if not healthy:
            raise NotReadyError("MongoDB is not reachable")
        return success({"status": "ready", "mongodb": True})

    return app


app = create_app()
