
from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.procurement.constants import ORDER_TRANSITIONS, OrderStatus, assert_transition
from app.modules.trust.constants import DisputeStatus
from app.shared.services.audit import AuditService
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


class DisputeNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Dispute not found")

async def _next_dispute_number() -> str:
    year = utc_now().year
    head = f"DSP-{year}-"
    count = await mongo_manager.collection(CollectionName.DISPUTES).count_documents(
        {"dispute_number": {"$regex": f"^{head}"}}
    )
    return f"{head}{count + 1:04d}"

class TrustService:
    def __init__(self) -> None:
        self.audit = AuditService()

    async def open_dispute(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        order_id: str,
        reason: str,
        description: str | None = None,
        evidence_url: str | None = None,
        evidence_type: str = "note",
        ip: str | None = None,
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        order = await mongo_manager.collection(CollectionName.ORDERS).find_one(
            {"_id": parse_object_id(order_id)}
        )
        if order is None:
            raise NotFoundError("Order not found")
        bid = str(business["_id"])
        if bid not in {
            str(order.get("buyer_business_id")),
            str(order.get("supplier_business_id")),
        }:
            raise ForbiddenError("Not a party to this order")
        if not reason or not reason.strip():
            raise BadRequestError("Dispute reason is required")

        open_existing = await mongo_manager.collection(CollectionName.DISPUTES).find_one(
            {
                "order_id": order["_id"],
                "status": {"$in": [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]},
            }
        )
        if open_existing:
            return self._serialize(open_existing)

        now = utc_now()
        evidence = []
        if evidence_url:
            evidence.append(
                {
                    "evidence_type": evidence_type,
                    "url": evidence_url,
                    "description": description,
                    "submitted_by_business_id": parse_object_id(bid),
                    "submitted_at": now,
                }
            )

        dispute = {
            "_id": ObjectId(),
            "dispute_number": await _next_dispute_number(),
            "order_id": order["_id"],
            "opened_by_business_id": parse_object_id(bid),
            "buyer_business_id": order["buyer_business_id"],
            "supplier_business_id": order["supplier_business_id"],
            "reason": reason.strip(),
            "description": description,
            "status": DisputeStatus.OPEN,
            "resolution": None,
            "resolution_notes": None,
            "resolved_by": None,
            "resolved_at": None,
            "evidence": evidence,
            "created_at": now,
            "updated_at": now,
        }
        await mongo_manager.collection(CollectionName.DISPUTES).insert_one(dispute)

                                                    
        status = order.get("status")
        if status in ORDER_TRANSITIONS and OrderStatus.DISPUTED in ORDER_TRANSITIONS.get(status, set()):
            assert_transition(ORDER_TRANSITIONS, status, OrderStatus.DISPUTED)
            history = list(order.get("status_history") or [])
            history.append(
                {
                    "status": OrderStatus.DISPUTED,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": f"Dispute opened: {reason.strip()}",
                    "changed_at": now,
                }
            )
            await mongo_manager.collection(CollectionName.ORDERS).update_one(
                {"_id": order["_id"]},
                {
                    "$set": {
                        "status": OrderStatus.DISPUTED,
                        "status_history": history,
                        "updated_at": now,
                    }
                },
            )

        await self.audit.log(
            action="DISPUTE_OPENED",
            resource_type="dispute",
            resource_id=dispute["_id"],
            business_account_id=bid,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={"reason": reason.strip(), "order_id": order_id},
        )

                                 
        from app.modules.trust.constants import NotificationType
        from app.modules.trust.notify import notify

        other = (
            order["supplier_business_id"]
            if bid == str(order.get("buyer_business_id"))
            else order["buyer_business_id"]
        )
        await notify(
            recipient_business_id=other,
            type=NotificationType.DISPUTE_OPENED,
            title=f"Dispute {dispute['dispute_number']} opened",
            message=reason.strip(),
            reference_type="dispute",
            reference_id=dispute["_id"],
        )

        return self._serialize(dispute)

    async def list_for_business(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        bid = parse_object_id(str(business["_id"]))
        query = {
            "$or": [
                {"buyer_business_id": bid},
                {"supplier_business_id": bid},
                {"opened_by_business_id": bid},
            ]
        }
        col = mongo_manager.collection(CollectionName.DISPUTES)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize(r) for r in rows], total

    async def has_open_dispute(self, order_id: str | ObjectId) -> bool:
        oid = parse_object_id(str(order_id))
        found = await mongo_manager.collection(CollectionName.DISPUTES).find_one(
            {
                "order_id": oid,
                "status": {"$in": [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]},
            }
        )
        return found is not None

    async def list_all(
        self, *, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        col = mongo_manager.collection(CollectionName.DISPUTES)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize(r) for r in rows], total

    async def resolve_dispute(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        dispute_id: str,
        resolution: str,
        resolution_notes: str | None = None,
        close: bool = True,
        restore_order_status: str | None = "delivered",
        ip: str | None = None,
    ) -> dict[str, Any]:
        if not business or str(business.get("type")) != "platform":
            raise ForbiddenError("Platform context required to resolve disputes")
        col = mongo_manager.collection(CollectionName.DISPUTES)
        dispute = await col.find_one({"_id": parse_object_id(dispute_id)})
        if dispute is None:
            raise DisputeNotFoundError()
        if dispute.get("status") not in {DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW}:
            raise BadRequestError("Dispute is not open for resolution")
        if not resolution or not resolution.strip():
            raise BadRequestError("Resolution is required")

        now = utc_now()
        target = DisputeStatus.CLOSED if close else DisputeStatus.RESOLVED
        await col.update_one(
            {"_id": dispute["_id"]},
            {
                "$set": {
                    "status": target,
                    "resolution": resolution.strip(),
                    "resolution_notes": resolution_notes,
                    "resolved_by": parse_object_id(user_id),
                    "resolved_at": now,
                    "updated_at": now,
                }
            },
        )

                                                     
        order = await mongo_manager.collection(CollectionName.ORDERS).find_one(
            {"_id": dispute["order_id"]}
        )
        if (
            order
            and order.get("status") == OrderStatus.DISPUTED
            and restore_order_status
            and restore_order_status in ORDER_TRANSITIONS.get(OrderStatus.DISPUTED, set())
        ):
            assert_transition(ORDER_TRANSITIONS, OrderStatus.DISPUTED, restore_order_status)
            history = list(order.get("status_history") or [])
            history.append(
                {
                    "status": restore_order_status,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": f"Dispute resolved: {resolution.strip()}",
                    "changed_at": now,
                }
            )
            await mongo_manager.collection(CollectionName.ORDERS).update_one(
                {"_id": order["_id"]},
                {
                    "$set": {
                        "status": restore_order_status,
                        "status_history": history,
                        "updated_at": now,
                    }
                },
            )

        await self.audit.log(
            action="DISPUTE_RESOLVED",
            resource_type="dispute",
            resource_id=dispute["_id"],
            business_account_id=str(business["_id"]),
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={"resolution": resolution.strip(), "status": target},
        )

        from app.modules.trust.constants import NotificationType
        from app.modules.trust.notify import notify

        for party in (dispute.get("buyer_business_id"), dispute.get("supplier_business_id")):
            if party:
                await notify(
                    recipient_business_id=party,
                    type=NotificationType.DISPUTE_RESOLVED,
                    title=f"Dispute {dispute.get('dispute_number')} resolved",
                    message=resolution.strip(),
                    reference_type="dispute",
                    reference_id=dispute["_id"],
                )

        refreshed = await col.find_one({"_id": dispute["_id"]})
        assert refreshed is not None
        return self._serialize(refreshed)

    async def create_review(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        order_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        from app.modules.trust.constants import ReviewStatus

        if not business or str(business.get("type")) != "buyer":
            raise ForbiddenError("Only the buyer can leave a review")
        if rating < 1 or rating > 5:
            raise BadRequestError("Rating must be between 1 and 5")
        order = await mongo_manager.collection(CollectionName.ORDERS).find_one(
            {"_id": parse_object_id(order_id)}
        )
        if order is None:
            raise NotFoundError("Order not found")
        if str(order.get("buyer_business_id")) != str(business["_id"]):
            raise ForbiddenError("Not your order")
        if order.get("status") != OrderStatus.COMPLETED:
            raise BadRequestError("Reviews are only allowed on completed orders")

        existing = await mongo_manager.collection(CollectionName.REVIEWS).find_one(
            {"order_id": order["_id"]}
        )
        if existing:
            return self._serialize_review(existing)

        now = utc_now()
        doc = {
            "_id": ObjectId(),
            "order_id": order["_id"],
            "buyer_business_id": order["buyer_business_id"],
            "supplier_business_id": order["supplier_business_id"],
            "rating": int(rating),
            "comment": (comment or "").strip() or None,
            "status": ReviewStatus.PUBLISHED,
            "created_by_user_id": parse_object_id(user_id),
            "created_at": now,
            "updated_at": now,
        }
        try:
            await mongo_manager.collection(CollectionName.REVIEWS).insert_one(doc)
        except Exception:
            again = await mongo_manager.collection(CollectionName.REVIEWS).find_one(
                {"order_id": order["_id"]}
            )
            if again:
                return self._serialize_review(again)
            raise
        return self._serialize_review(doc)

    async def get_review_for_order(
        self, *, business: dict[str, Any] | None, order_id: str
    ) -> dict[str, Any] | None:
        if not business:
            raise ForbiddenError("Select a company to continue")
        order = await mongo_manager.collection(CollectionName.ORDERS).find_one(
            {"_id": parse_object_id(order_id)}
        )
        if order is None:
            raise NotFoundError("Order not found")
        bid = str(business["_id"])
        if bid not in {
            str(order.get("buyer_business_id")),
            str(order.get("supplier_business_id")),
        }:
            raise ForbiddenError("Not a party to this order")
        row = await mongo_manager.collection(CollectionName.REVIEWS).find_one(
            {"order_id": order["_id"]}
        )
        return self._serialize_review(row) if row else None

    def _serialize_review(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "buyer_business_id": str(doc["buyer_business_id"])
            if doc.get("buyer_business_id")
            else None,
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "rating": doc.get("rating"),
            "comment": doc.get("comment"),
            "status": doc.get("status"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        }

    def _serialize(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "dispute_number": doc.get("dispute_number"),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "opened_by_business_id": str(doc["opened_by_business_id"])
            if doc.get("opened_by_business_id")
            else None,
            "buyer_business_id": str(doc["buyer_business_id"]) if doc.get("buyer_business_id") else None,
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "reason": doc.get("reason"),
            "description": doc.get("description"),
            "status": doc.get("status"),
            "resolution": doc.get("resolution"),
            "resolution_notes": doc.get("resolution_notes"),
            "resolved_at": doc.get("resolved_at").isoformat() if doc.get("resolved_at") else None,
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        }
