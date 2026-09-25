
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.constants import REQUEST_ID_HEADER
from app.core.logging import (
    get_logger,
    method_ctx,
    request_id_ctx,
    route_ctx,
)
from app.shared.utils.datetime import utc_now

logger = get_logger(__name__)

def _set_scope_state(scope: Scope, key: str, value: str) -> None:
    state = scope.setdefault("state", {})
    if isinstance(state, dict):
        state[key] = value
    else:
        setattr(state, key, value)

class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming else str(uuid.uuid4())
        _set_scope_state(scope, "request_id", request_id)

        request_id_token = request_id_ctx.set(request_id)
        method_token = method_ctx.set(str(scope.get("method", "")))
        route_token = route_ctx.set(str(scope.get("path", "")))
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                headers[REQUEST_ID_HEADER] = request_id
                message["headers"] = headers.raw
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(request_id_token)
            method_ctx.reset(method_token)
            route_ctx.reset(route_token)
            logger.info(
                "http_request",
                method=scope.get("method"),
                route=scope.get("path"),
                status_code=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                request_id=request_id,
            )

class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, settings: Settings | None = None) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("X-XSS-Protection", "0")
                headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
                if self.settings is not None and self.settings.is_production:
                    headers.setdefault(
                        "Strict-Transport-Security",
                        "max-age=31536000; includeSubDomains",
                    )
                message["headers"] = headers.raw
            await send(message)

        await self.app(scope, receive, send_wrapper)

class _InProcessRateLimiter:

    def __init__(self, *, max_hits: int, window_seconds: int = 60) -> None:
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = utc_now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        recent = [stamp for stamp in self._hits[key] if stamp > cutoff]
        if len(recent) >= self.max_hits:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True

class RateLimitMiddleware:

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self._enabled = settings.rate_limit_enabled
        self._limiter = _InProcessRateLimiter(max_hits=max(1, settings.rate_limit_per_minute))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._enabled:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path in {"/health", "/ready"}:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        host = client[0] if client else "unknown"
        if not self._limiter.allow(host):
            body = b'{"error":{"code":"RATE_LIMITED","message":"Too many requests"}}'
            headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", b"60"),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)
