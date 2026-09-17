"""Request helpers. Client IP comes from the ASGI connection, not a client-supplied header.

If TradeBay sits behind a reverse proxy, configure Uvicorn/Starlette
`proxy_headers` / `forwarded_allow_ips` so `request.client.host` is the
real client address. Application code must not read `X-Forwarded-For`
directly — that header is client-controlled unless the proxy overwrites it.
"""

from __future__ import annotations

from fastapi import Request


def client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host
