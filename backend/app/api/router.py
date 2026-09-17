"""Aggregate versioned API routers."""

from fastapi import APIRouter

from app.core.constants import API_V1_PREFIX
from app.modules.identity.business_router import (
    businesses_router,
    members_router,
    permissions_router,
    roles_router,
)
from app.modules.identity.router import router as auth_router

api_router = APIRouter(prefix=API_V1_PREFIX)

api_router.include_router(auth_router)
api_router.include_router(businesses_router)
api_router.include_router(members_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)

# Domain routers are included when modules exist (catalog, procurement, etc.).
# Safe optional imports keep the app startable during incremental scaffolding.


def _include_optional(module_path: str, attr: str = "router") -> None:
    try:
        module = __import__(module_path, fromlist=[attr])
        router = getattr(module, attr)
        api_router.include_router(router)
    except (ImportError, AttributeError):
        pass


_include_optional("app.modules.catalog.router")
_include_optional("app.modules.settings.router")
_include_optional("app.modules.procurement.router")
_include_optional("app.modules.finance.router")
_include_optional("app.modules.platform_money.router")
_include_optional("app.modules.trust.router")
_include_optional("app.modules.ai.router")
_include_optional("app.modules.communication.router")
_include_optional("app.modules.negotiation.router")
_include_optional("app.modules.ai_sourcing.router")
_include_optional("app.modules.business_planner.router")
