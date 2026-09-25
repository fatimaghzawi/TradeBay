
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import Settings
from app.core.constants import SENSITIVE_LOG_FIELDS

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
business_id_ctx: ContextVar[str | None] = ContextVar("business_account_id", default=None)
route_ctx: ContextVar[str | None] = ContextVar("route", default=None)
method_ctx: ContextVar[str | None] = ContextVar("method", default=None)

def _drop_sensitive(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_LOG_FIELDS:
            event_dict[key] = "[redacted]"
    return event_dict

def _bind_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    request_id = request_id_ctx.get()
    user_id = user_id_ctx.get()
    business_id = business_id_ctx.get()
    route = route_ctx.get()
    method = method_ctx.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    if user_id:
        event_dict.setdefault("user_id", user_id)
    if business_id:
        event_dict.setdefault("business_account_id", business_id)
    if route:
        event_dict.setdefault("route", route)
    if method:
        event_dict.setdefault("method", method)
    return event_dict

def configure_logging(settings: Settings) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _bind_context,
        _drop_sensitive,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=settings.log_level.upper(), stream=sys.stdout)

def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)

                                                                  
                                                             
                                                                        
                                                                        
