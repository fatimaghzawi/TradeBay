
from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.modules.procurement.constants import OrderStatus
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class RFQRepository(BaseRepository):
    collection_name = CollectionName.RFQS

    async def list_for_buyer(
        self,
        business_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        rfq_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"buyer_business_id": parse_object_id(business_id)}
        if status:
            query["status"] = status
        if rfq_type:
            query["rfq_type"] = rfq_type
        return await self.find_many(query, skip=skip, limit=limit, sort=[("updated_at", -1)])

    async def count_for_buyer(
        self,
        business_id: str,
        *,
        status: str | None = None,
        rfq_type: str | None = None,
    ) -> int:
        query: dict[str, Any] = {"buyer_business_id": parse_object_id(business_id)}
        if status:
            query["status"] = status
        if rfq_type:
            query["rfq_type"] = rfq_type
        return await self.count(query)

    async def list_invited_for_supplier(
        self, supplier_business_id: str, *, skip: int = 0, limit: int = 20
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"supplier_invites.supplier_business_id": parse_object_id(supplier_business_id)},
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )

    async def count_by_number_prefix(self, prefix: str) -> int:
        return await self.count({"rfq_number": {"$regex": f"^{prefix}"}})

class RFQItemRepository(BaseRepository):
    collection_name = CollectionName.RFQ_ITEMS

    async def list_for_rfq(self, rfq_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"rfq_id": parse_object_id(str(rfq_id))},
            limit=200,
            sort=[("sort_order", 1)],
        )

    async def delete_for_rfq(self, rfq_id: str | ObjectId, *, session: MongoSession = None) -> int:
        result = await self.collection.delete_many(
            {"rfq_id": parse_object_id(str(rfq_id))},
            session=session,
        )
        return int(result.deleted_count)

class QuotationRepository(BaseRepository):
    collection_name = CollectionName.QUOTATIONS

    async def get_for_rfq_supplier(self, rfq_id: str, supplier_id: str) -> dict[str, Any] | None:
        return await self.find_one(
            {
                "rfq_id": parse_object_id(rfq_id),
                "supplier_id": parse_object_id(supplier_id),
            }
        )

    async def list_for_rfq(self, rfq_id: str) -> list[dict[str, Any]]:
        return await self.find_many(
            {"rfq_id": parse_object_id(rfq_id)},
            limit=100,
            sort=[("updated_at", -1)],
        )

    async def list_for_supplier(
        self, supplier_id: str, *, skip: int = 0, limit: int = 20
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"supplier_id": parse_object_id(supplier_id)},
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )

class QuotationItemRepository(BaseRepository):
    collection_name = CollectionName.QUOTATION_ITEMS

    async def list_for_quotation(
        self, quotation_id: str | ObjectId, *, version: int | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"quotation_id": parse_object_id(str(quotation_id))}
        if version is not None:
            query["version"] = version
        return await self.find_many(query, limit=200, sort=[("rfq_item_id", 1)])

class OrderRepository(BaseRepository):
    collection_name = CollectionName.ORDERS

    @staticmethod
    def _business_query(
        business_id: str | None, *, as_buyer: bool, status: str | None, include_unpaid: bool | None
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if business_id is not None:
            field = "buyer_business_id" if as_buyer else "supplier_business_id"
            query[field] = parse_object_id(business_id)
                                                                                
        hide_unpaid = (not as_buyer) if include_unpaid is None else not include_unpaid
        if hide_unpaid:
            if status == OrderStatus.AWAITING_PAYMENT:
                query["status"] = {"$in": []}
            elif status:
                query["status"] = status
            else:
                query["status"] = {"$ne": OrderStatus.AWAITING_PAYMENT}
        elif status:
            query["status"] = status
        return query

    async def list_for_business(
        self,
        business_id: str | None,
        *,
        as_buyer: bool = True,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        include_unpaid: bool | None = None,
    ) -> list[dict[str, Any]]:
        query = self._business_query(
            business_id, as_buyer=as_buyer, status=status, include_unpaid=include_unpaid
        )
        return await self.find_many(query, skip=skip, limit=limit, sort=[("updated_at", -1)])

    async def count_for_business(
        self,
        business_id: str | None,
        *,
        as_buyer: bool = True,
        status: str | None = None,
        include_unpaid: bool | None = None,
    ) -> int:
        query = self._business_query(
            business_id, as_buyer=as_buyer, status=status, include_unpaid=include_unpaid
        )
        return await self.count(query)

class OrderItemRepository(BaseRepository):
    collection_name = CollectionName.ORDER_ITEMS

    async def list_for_order(self, order_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"order_id": parse_object_id(str(order_id))},
            limit=200,
            sort=[("product_name_snapshot", 1)],
        )

class ShipmentRepository(BaseRepository):
    collection_name = CollectionName.SHIPMENTS

    async def list_for_order(self, order_id: str) -> list[dict[str, Any]]:
        return await self.find_many(
            {"order_id": parse_object_id(order_id)},
            limit=50,
            sort=[("created_at", 1)],
        )

    async def find_by_tracking(self, tracking_number: str) -> dict[str, Any] | None:
        return await self.find_one({"tracking_number": tracking_number})

class ShipmentItemRepository(BaseRepository):
    collection_name = CollectionName.SHIPMENT_ITEMS

    async def list_for_shipment(self, shipment_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"shipment_id": parse_object_id(str(shipment_id))},
            limit=200,
        )

    async def list_for_order(self, order_id: str) -> list[dict[str, Any]]:
        return await self.find_many(
            {"order_id": parse_object_id(order_id)},
            limit=500,
        )
