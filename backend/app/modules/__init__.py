"""TradeBay domain modules."""

from app.modules.ai.router import router as ai_router
from app.modules.catalog.router import router as catalog_router
from app.modules.finance.router import router as finance_router
from app.modules.platform_money.router import router as platform_money_router
from app.modules.procurement.router import router as procurement_router
from app.modules.trust.router import router as trust_router

__all__ = [
    "ai_router",
    "catalog_router",
    "finance_router",
    "platform_money_router",
    "procurement_router",
    "trust_router",
]
