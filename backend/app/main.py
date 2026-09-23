"""TradeBay FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

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
from app.modules.catalog.storage import CATEGORY_UPLOAD_DIR, PRODUCT_UPLOAD_DIR
from app.modules.identity.storage import BUSINESS_UPLOAD_DIR
from app.core.paths import UPLOAD_ROOT
from app.shared.schemas.response import success

logger = get_logger(__name__)


def _configure_sentry(settings: Settings) -> None:
    dsn = (settings.sentry_dsn or "").strip().strip("\"'")
    # Render often sets SENTRY_DSN="" — treat blank / placeholder as disabled.
    if not dsn or dsn.lower() in {"none", "null", "undefined"}:
        return
    if "://" not in dsn:
        logger.warning("sentry_dsn_invalid", reason="missing_scheme")
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry_sdk_missing")
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=str(settings.app_env),
            traces_sample_rate=0.1 if settings.is_production else 0.0,
            send_default_pii=False,
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
            ],
        )
    except Exception:
        logger.exception("sentry_init_failed")
        return
    logger.info("sentry_configured", environment=str(settings.app_env))


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
    _configure_sentry(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "TradeBay modular monolith API. "
            "Domains: Identity, Catalog, Procurement, Finance, Platform Money, AI."
        ),
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # Outermost first for responses: CORS must wrap everything so browser
    # errors (incl. 401/500) still get Access-Control-Allow-Origin.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=(
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
            if not settings.is_production
            else None
        ),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    # Public catalog product + category images only. Delivery evidence is served via
    # authenticated procurement routes — never mount the whole uploads tree.
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CATEGORY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BUSINESS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/uploads/products",
        StaticFiles(directory=str(PRODUCT_UPLOAD_DIR)),
        name="product_uploads",
    )
    app.mount(
        "/uploads/categories",
        StaticFiles(directory=str(CATEGORY_UPLOAD_DIR)),
        name="category_uploads",
    )
    app.mount(
        "/uploads/businesses",
        StaticFiles(directory=str(BUSINESS_UPLOAD_DIR)),
        name="business_uploads",
    )
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
