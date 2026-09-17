"""Backward-compatible export of the authentication router."""

from app.modules.identity.auth_router import router

__all__ = ["router"]
