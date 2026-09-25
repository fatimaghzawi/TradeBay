
from fastapi import APIRouter

from app.core.constants import API_V1_PREFIX
from app.modules.identity.auth_router import router as auth_router
from app.modules.identity.business_router import businesses_router, companies_router
from app.modules.identity.identity_router import (
    audit_logs_router,
    invitations_router,
    me_router,
    members_router,
    permissions_router,
    platform_router,
    roles_router,
    sessions_router,
    users_router,
)

api_router = APIRouter(prefix=API_V1_PREFIX)

api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(sessions_router)
api_router.include_router(platform_router)
api_router.include_router(businesses_router)
api_router.include_router(companies_router)
api_router.include_router(members_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(invitations_router)
api_router.include_router(users_router)
api_router.include_router(audit_logs_router)

                                                                              
                                                                              

def _include_optional(module_path: str, attr: str = "router") -> None:
    try:
        module = __import__(module_path, fromlist=[attr])
        router = getattr(module, attr)
        api_router.include_router(router)
    except (ImportError, AttributeError):
        pass

_include_optional("app.modules.catalog.router")
_include_optional("app.modules.cart.router")
_include_optional("app.modules.checkout.router")
_include_optional("app.modules.settings.router")
_include_optional("app.modules.procurement.router")
_include_optional("app.modules.finance.router")
_include_optional("app.modules.platform_money.router")
try:
    from app.modules.platform_money.router import (
        supplier_payouts_router as _supplier_payouts_router,
    )

    api_router.include_router(_supplier_payouts_router)
except (ImportError, AttributeError):
    pass
_include_optional("app.modules.trust.router")
_include_optional("app.modules.communication.router")
_include_optional("app.modules.negotiation.router")
_include_optional("app.modules.ai_sourcing.router")
_include_optional("app.modules.business_planner.router")
try:
    from app.modules.business_planner.router import plans_router as _plans_router

    api_router.include_router(_plans_router)
except (ImportError, AttributeError):
    pass
