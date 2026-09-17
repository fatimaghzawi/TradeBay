from __future__ import annotations

from typing import Any

from app.modules.procurement.constants import ORDER_STATUS_TRANSITIONS, OrderStatus
from app.modules.procurement.repository import OrderRepository


class OrderService:
    def __init__(self, order_repository: OrderRepository) -> None:
        self._orders = order_repository

    async def list_orders(
        self,
        *,
        business_account_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_doc = {
            "$or": [
                {"buyer_business_account_id": business_account_id},
                {"supplier_business_account_id": business_account_id},
            ]
        }
        total = await self._orders.count(filter_doc)
        items = await self._orders.find_many(filter_doc, skip=skip, limit=limit)
        return items, total

    async def transition_status(self, order_id: str, target: OrderStatus) -> dict[str, Any]:
        _ = ORDER_STATUS_TRANSITIONS
        raise NotImplementedError
