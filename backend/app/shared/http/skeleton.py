"""Shared 501 stub response for domains that are models-only skeletons."""

from __future__ import annotations

from fastapi.responses import JSONResponse


def not_implemented(domain: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": f"{domain} domain is not implemented yet",
            }
        },
    )
