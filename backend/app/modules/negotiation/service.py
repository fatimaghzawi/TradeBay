
from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import BusinessAccountType
from app.modules.negotiation.constants import (
    NEGOTIATION_TRANSITIONS,
    NegotiationOfferStatus,
    NegotiationStatus,
)
from app.modules.procurement.commercial import compute_document_totals, compute_line
from app.modules.procurement.constants import (
    QUOTATION_TRANSITIONS,
    QuotationStatus,
    RFQStatus,
    assert_transition,
)
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


def _assert_neg_transition(current: str, target: str) -> None:
    allowed = NEGOTIATION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise BadRequestError("This action isn't available for the current negotiation status")

class NegotiationService:
    async def open(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        quotation_id: str,
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        rfq = await mongo_manager.collection(CollectionName.RFQS).find_one(
            {"_id": parse_object_id(rfq_id)}
        )
        quote = await mongo_manager.collection(CollectionName.QUOTATIONS).find_one(
            {"_id": parse_object_id(quotation_id)}
        )
        if rfq is None or quote is None:
            raise NotFoundError("We couldn't find that request or quotation.")
        if str(quote.get("rfq_id")) != rfq_id:
            raise BadRequestError("This quotation was sent for a different request.")
        bid = str(business["_id"])
        if bid not in {str(rfq.get("buyer_business_id")), str(quote.get("supplier_id"))}:
            raise ForbiddenError("Only the buyer and the quoting supplier can negotiate this deal.")
        if str(quote.get("status")) == QuotationStatus.DRAFT:
            raise BadRequestError("This quotation hasn't been sent yet, so it can't be negotiated.")
        if str(rfq.get("status")) == RFQStatus.AWARDED:
            raise BadRequestError("This RFQ has been awarded—negotiation is no longer available")
        await self._ensure_quotation_bargainable(quote)

        existing = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {
                "rfq_id": rfq["_id"],
                "quotation_id": quote["_id"],
                "status": {"$in": [NegotiationStatus.OPEN, NegotiationStatus.IN_PROGRESS]},
            }
        )
        if existing:
            return await self.get(negotiation_id=str(existing["_id"]), business=business)

        closed = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {
                "rfq_id": rfq["_id"],
                "quotation_id": quote["_id"],
                "status": {
                    "$in": [
                        NegotiationStatus.AGREED,
                        NegotiationStatus.REJECTED,
                        NegotiationStatus.CANCELLED,
                        NegotiationStatus.EXPIRED,
                    ]
                },
            }
        )
        if closed:
            if str(closed.get("status")) == NegotiationStatus.AGREED:
                raise BadRequestError("This quotation is already agreed — no further counters")
            raise BadRequestError("Negotiation on this quotation has ended.")

        now = utc_now()
        doc = {
            "_id": ObjectId(),
            "rfq_id": rfq["_id"],
            "quotation_id": quote["_id"],
            "conversation_id": None,
            "buyer_business_id": rfq["buyer_business_id"],
            "supplier_business_id": quote["supplier_id"],
            "started_by_user_id": parse_object_id(user_id),
            "status": NegotiationStatus.OPEN,
            "agreed_at": None,
            "agreed_offer_id": None,
            "expires_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await mongo_manager.collection(CollectionName.NEGOTIATIONS).insert_one(doc)
        await mongo_manager.collection(CollectionName.QUOTATIONS).update_one(
            {"_id": quote["_id"]},
            {"$set": {"status": QuotationStatus.NEGOTIATING, "updated_at": now}},
        )
        if rfq.get("status") in {RFQStatus.PUBLISHED, RFQStatus.RESPONDING}:
            await mongo_manager.collection(CollectionName.RFQS).update_one(
                {"_id": rfq["_id"]},
                {"$set": {"status": RFQStatus.NEGOTIATING, "updated_at": now}},
            )
        try:
            await self._notify_counterparty(
                neg=doc,
                actor_business_id=bid,
                type_="NEGOTIATION_OPENED",
                title=f"Negotiation opened — {rfq.get('rfq_number')}",
                message="A commercial negotiation was opened on this quotation. Review offers on the RFQ.",
            )
        except Exception:
            pass
        return await self.get(negotiation_id=str(doc["_id"]), business=business)

    async def list_for_rfq(
        self, *, business: dict[str, Any] | None, rfq_id: str
    ) -> list[dict[str, Any]]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        bid = str(business["_id"])
        rows = (
            await mongo_manager.collection(CollectionName.NEGOTIATIONS)
            .find(
                {
                    "rfq_id": parse_object_id(rfq_id),
                    "$or": [
                        {"buyer_business_id": parse_object_id(bid)},
                        {"supplier_business_id": parse_object_id(bid)},
                    ],
                }
            )
            .sort("updated_at", -1)
            .to_list(length=20)
        )
        out = []
        for row in rows:
            out.append(await self.get(negotiation_id=str(row["_id"]), business=business))
        return out

    async def get(self, *, negotiation_id: str, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        neg = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {"_id": parse_object_id(negotiation_id)}
        )
        if neg is None:
            raise NotFoundError("We couldn't find that negotiation.")
        self._assert_access(neg, business)
        offers = (
            await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS)
            .find({"negotiation_id": neg["_id"]})
            .sort("created_at", 1)
            .to_list(length=100)
        )
        offer_out = []
        for offer in offers:
            items = await mongo_manager.collection(CollectionName.NEGOTIATION_OFFER_ITEMS).find(
                {"offer_id": offer["_id"]}
            ).to_list(length=200)
            offer_out.append(self._serialize_offer(offer, items))

        baseline_lines: list[dict[str, Any]] = []
        payment_terms = None
        if neg.get("quotation_id"):
            quote = await mongo_manager.collection(CollectionName.QUOTATIONS).find_one(
                {"_id": neg["quotation_id"]}
            )
            payment_terms = quote.get("payment_terms") if quote else None
            q_items = await mongo_manager.collection(CollectionName.QUOTATION_ITEMS).find(
                {"quotation_id": neg["quotation_id"]}
            ).to_list(length=200)
            for qi in q_items:
                baseline_lines.append(
                    {
                        "rfq_item_id": str(qi["rfq_item_id"]) if qi.get("rfq_item_id") else None,
                        "product_name_snapshot": qi.get("product_name_snapshot"),
                        "quantity": format(Decimal(str(qi["quantity"])), "f"),
                        "unit_price": format(Decimal(str(qi["unit_price"])), "f"),
                        "line_total": format(Decimal(str(qi["line_total"])), "f")
                        if qi.get("line_total") is not None
                        else None,
                    }
                )

        buyer = await self._business_card(neg.get("buyer_business_id"))
        supplier = await self._business_card(neg.get("supplier_business_id"))
        return {
            "id": str(neg["_id"]),
            "rfq_id": str(neg["rfq_id"]) if neg.get("rfq_id") else None,
            "quotation_id": str(neg["quotation_id"]) if neg.get("quotation_id") else None,
            "status": neg.get("status"),
            "buyer_business_id": str(neg["buyer_business_id"]) if neg.get("buyer_business_id") else None,
            "supplier_business_id": str(neg["supplier_business_id"])
            if neg.get("supplier_business_id")
            else None,
            "buyer_name": buyer["name"],
            "supplier_name": supplier["name"],
            "buyer_logo_url": buyer["logo_url"],
            "supplier_logo_url": supplier["logo_url"],
            "agreed_offer_id": str(neg["agreed_offer_id"]) if neg.get("agreed_offer_id") else None,
            "payment_terms": payment_terms,
            "baseline_lines": baseline_lines,
            "offers": offer_out,
            "created_at": neg.get("created_at").isoformat() if neg.get("created_at") else None,
        }

    async def _ensure_quotation_bargainable(self, quote: dict[str, Any]) -> None:
        status = str(quote.get("status") or "")
        if status in {
            QuotationStatus.ACCEPTED,
            QuotationStatus.WITHDRAWN,
            QuotationStatus.EXPIRED,
        }:
            raise BadRequestError("This quote is finalized and can no longer be changed")
        if status != QuotationStatus.REJECTED:
            return
        assert_transition(QUOTATION_TRANSITIONS, status, QuotationStatus.NEGOTIATING)
        now = utc_now()
        await mongo_manager.collection(CollectionName.QUOTATIONS).update_one(
            {"_id": quote["_id"]},
            {"$set": {"status": QuotationStatus.NEGOTIATING, "updated_at": now}},
        )
        quote["status"] = QuotationStatus.NEGOTIATING

    def _assert_access(self, neg: dict[str, Any], business: dict[str, Any]) -> None:
        bid = str(business["_id"])
        if bid not in {
            str(neg.get("buyer_business_id")),
            str(neg.get("supplier_business_id")),
        }:
            raise ForbiddenError("Only the buyer and the quoting supplier can view this negotiation.")

    async def _business_card(self, business_id: Any) -> dict[str, str | None]:
        empty = {"name": None, "logo_url": None}
        if not business_id:
            return empty
        raw = str(business_id)
        if raw in {"None", "null"} or not ObjectId.is_valid(raw):
            return empty
        doc = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": parse_object_id(raw)},
            {"name": 1, "logo_url": 1},
        )
        if not doc:
            return empty
        return {"name": doc.get("name"), "logo_url": doc.get("logo_url")}

    async def _business_name(self, business_id: Any) -> str | None:
        return (await self._business_card(business_id))["name"]

    async def _notify_counterparty(
        self,
        *,
        neg: dict[str, Any],
        actor_business_id: str,
        type_: str,
        title: str,
        message: str,
    ) -> None:
        from app.modules.trust.notify import notify

        buyer = str(neg.get("buyer_business_id") or "")
        supplier = str(neg.get("supplier_business_id") or "")
        other = supplier if actor_business_id == buyer else buyer
        if not other:
            return
        await notify(
            recipient_business_id=other,
            type=type_,
            title=title,
            message=message,
            reference_type="rfq",
            reference_id=neg.get("rfq_id"),
        )

    def _serialize_offer(self, offer: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": str(offer["_id"]),
            "status": offer.get("status"),
            "currency": offer.get("currency"),
            "payment_terms": offer.get("payment_terms"),
            "total_price": format(Decimal(str(offer["total_price"])), "f")
            if offer.get("total_price") is not None
            else None,
            "parent_offer_id": str(offer["parent_offer_id"]) if offer.get("parent_offer_id") else None,
            "created_by_business_id": str(offer["created_by_business_id"])
            if offer.get("created_by_business_id")
            else None,
            "created_at": offer.get("created_at").isoformat() if offer.get("created_at") else None,
            "items": [
                {
                    "rfq_item_id": str(i["rfq_item_id"]) if i.get("rfq_item_id") else None,
                    "product_name_snapshot": i.get("product_name_snapshot"),
                    "quantity": format(Decimal(str(i["quantity"])), "f"),
                    "unit_price": format(Decimal(str(i["unit_price"])), "f"),
                    "line_total": format(Decimal(str(i["line_total"])), "f")
                    if i.get("line_total") is not None
                    else None,
                }
                for i in items
            ],
        }

    async def propose_offer(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        negotiation_id: str,
        lines: list[dict[str, Any]],
        payment_terms: str | None = None,
        parent_offer_id: str | None = None,
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        neg = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {"_id": parse_object_id(negotiation_id)}
        )
        if neg is None:
            raise NotFoundError("We couldn't find that negotiation.")
        self._assert_access(neg, business)
        if neg.get("status") not in {NegotiationStatus.OPEN, NegotiationStatus.IN_PROGRESS}:
            raise BadRequestError("This negotiation has ended, so offers can no longer change.")
        if neg.get("rfq_id"):
            rfq = await mongo_manager.collection(CollectionName.RFQS).find_one(
                {"_id": neg["rfq_id"]}, {"status": 1}
            )
            if rfq and str(rfq.get("status")) == "awarded":
                raise BadRequestError("This RFQ has been awarded—negotiation is no longer available")
        if not lines:
            raise BadRequestError("Add at least one item to your offer.")
        quote = None
        if neg.get("quotation_id"):
            quote = await mongo_manager.collection(CollectionName.QUOTATIONS).find_one(
                {"_id": neg["quotation_id"]}
            )
            if quote is not None:
                await self._ensure_quotation_bargainable(quote)

        rfq_items = {
            str(item["_id"]): item
            for item in await mongo_manager.collection(CollectionName.RFQ_ITEMS)
            .find({"rfq_id": neg.get("rfq_id")})
            .to_list(length=500)
        }
        seen: set[str] = set()
        for raw in lines:
            item_id = str(raw.get("rfq_item_id") or "")
            if item_id not in rfq_items:
                raise BadRequestError("Each offer line must match an item on this RFQ.")
            if item_id in seen:
                raise BadRequestError("Each requested item can only appear once in an offer.")
            seen.add(item_id)
            item = rfq_items[item_id]
            raw["product_name"] = item.get("product_name") or raw.get("product_name")
            raw["unit"] = item.get("unit") or raw.get("unit")

        computed = []
        for raw in lines:
            line = compute_line(
                quantity=raw["quantity"],
                unit_price=raw["unit_price"],
                discount=raw.get("discount") or "0",
            )
            computed.append((raw, line))
        totals = compute_document_totals([c[1] for c in computed])
        now = utc_now()
        offer = {
            "_id": ObjectId(),
            "negotiation_id": neg["_id"],
            "created_by_user_id": parse_object_id(user_id),
            "created_by_business_id": parse_object_id(str(business["_id"])),
            "parent_offer_id": parse_object_id(parent_offer_id) if parent_offer_id else None,
            "quantity": None,
            "unit_price": None,
            "total_price": to_decimal128(totals.total),
            "currency": (quote or {}).get("currency") or "USD",
            "delivery_location": None,
            "delivery_date": None,
            "payment_terms": payment_terms,
            "additional_terms": None,
            "status": NegotiationOfferStatus.PROPOSED,
            "expires_at": None,
            "responded_at": None,
            "created_at": now,
        }
        await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS).insert_one(offer)
        for raw, line in computed:
            await mongo_manager.collection(CollectionName.NEGOTIATION_OFFER_ITEMS).insert_one(
                {
                    "_id": ObjectId(),
                    "offer_id": offer["_id"],
                    "negotiation_id": neg["_id"],
                    "rfq_item_id": parse_object_id(raw["rfq_item_id"]) if raw.get("rfq_item_id") else None,
                    "quotation_item_id": None,
                    "product_id": None,
                    "product_name_snapshot": raw.get("product_name"),
                    "sku_snapshot": raw.get("sku"),
                    "quantity": to_decimal128(line.quantity),
                    "unit": raw.get("unit") or "unit",
                    "unit_price": to_decimal128(line.unit_price),
                    "discount": to_decimal128(line.discount),
                    "line_total": to_decimal128(line.line_total),
                    "lead_time_days": raw.get("lead_time_days"),
                    "notes": raw.get("notes"),
                    "created_at": now,
                }
            )
        if neg.get("status") == NegotiationStatus.OPEN:
            _assert_neg_transition(NegotiationStatus.OPEN, NegotiationStatus.IN_PROGRESS)
            await mongo_manager.collection(CollectionName.NEGOTIATIONS).update_one(
                {"_id": neg["_id"]},
                {"$set": {"status": NegotiationStatus.IN_PROGRESS, "updated_at": now}},
            )
        try:
            await self._notify_counterparty(
                neg=neg,
                actor_business_id=str(business["_id"]),
                type_="NEGOTIATION_OFFER",
                title="New negotiation offer",
                message="A new commercial offer was proposed. Open the RFQ to review offer history.",
            )
        except Exception:
            pass
        return await self.get(negotiation_id=negotiation_id, business=business)

    async def accept_offer(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        negotiation_id: str,
        offer_id: str,
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        if str(business.get("type")) not in {
            BusinessAccountType.BUYER,
            BusinessAccountType.SUPPLIER,
        }:
            raise ForbiddenError("Only the buyer or supplier can accept a counter")
        neg = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {"_id": parse_object_id(negotiation_id)}
        )
        if neg is None:
            raise NotFoundError("We couldn't find that negotiation.")
        self._assert_access(neg, business)
        if neg.get("status") not in {NegotiationStatus.OPEN, NegotiationStatus.IN_PROGRESS}:
            raise BadRequestError("This negotiation has ended, so offers can no longer change.")
        if neg.get("rfq_id"):
            rfq = await mongo_manager.collection(CollectionName.RFQS).find_one(
                {"_id": neg["rfq_id"]}, {"status": 1}
            )
            if rfq and str(rfq.get("status")) == "awarded":
                raise BadRequestError("This RFQ has been awarded—offers can no longer be accepted")

        now = utc_now()
        offers = mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS)
        actor_oid = parse_object_id(str(business["_id"]))
        target = await offers.find_one(
            {"_id": parse_object_id(offer_id), "negotiation_id": neg["_id"]},
            {"created_by_business_id": 1},
        )
        if target is not None and target.get("created_by_business_id") == actor_oid:
            raise BadRequestError("You cannot accept your own counter — wait for the other side")
                                                                                         
        claimed = await offers.find_one_and_update(
            {
                "_id": parse_object_id(offer_id),
                "negotiation_id": neg["_id"],
                "status": NegotiationOfferStatus.PROPOSED,
                "created_by_business_id": {"$ne": actor_oid},
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": now}},
                ],
            },
            {"$set": {"status": NegotiationOfferStatus.ACCEPTED, "responded_at": now}},
        )
        if claimed is None:
            raise BadRequestError("This offer was already answered or has expired.")
        try:
            return await self._apply_accepted_offer(
                neg=neg, claimed=claimed, business=business, user_id=user_id, now=now
            )
        except Exception:
                                                                                   
            await offers.update_one(
                {"_id": claimed["_id"], "status": NegotiationOfferStatus.ACCEPTED},
                {"$set": {"status": NegotiationOfferStatus.PROPOSED, "responded_at": None}},
            )
            raise

    async def _apply_accepted_offer(
        self,
        *,
        neg: dict[str, Any],
        claimed: dict[str, Any],
        business: dict[str, Any],
        user_id: str,
        now: Any,
    ) -> dict[str, Any]:
        negotiation_id = str(neg["_id"])
        items = await mongo_manager.collection(CollectionName.NEGOTIATION_OFFER_ITEMS).find(
            {"offer_id": claimed["_id"]}
        ).to_list(length=200)
        quote = await mongo_manager.collection(CollectionName.QUOTATIONS).find_one(
            {"_id": neg["quotation_id"]}
        )
        if quote is None:
            raise NotFoundError("We couldn't find that quotation.")

        from app.modules.procurement.service import ProcurementService

        lines_payload = []
        for item in items:
            if not item.get("rfq_item_id"):
                continue
            lines_payload.append(
                {
                    "rfq_item_id": str(item["rfq_item_id"]),
                    "quantity": format(Decimal(str(item["quantity"])), "f"),
                    "unit_price": format(Decimal(str(item["unit_price"])), "f"),
                    "discount": format(Decimal(str(item.get("discount") or 0)), "f"),
                    "tax": "0",
                    "shipping_allocation": "0",
                    "lead_time_days": item.get("lead_time_days"),
                    "notes": item.get("notes"),
                }
            )
        if not lines_payload:
            raise BadRequestError("This offer doesn't include any of the requested items.")

        supplier_biz = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": quote["supplier_id"]}
        )
        if supplier_biz is None:
            raise NotFoundError("We couldn't find the supplier for this quotation.")

        await ProcurementService().upsert_quotation(
            user_id=str(quote.get("created_by_user_id") or user_id),
            business=supplier_biz,
            rfq_id=str(neg["rfq_id"]),
            payload={
                "payment_terms": claimed.get("payment_terms") or quote.get("payment_terms"),
                "delivery_terms": quote.get("delivery_terms"),
                "currency": quote.get("currency") or claimed.get("currency") or "USD",
                "document_discount": "0",
                "document_shipping": "0",
                "document_tax": "0",
                "lines": lines_payload,
            },
            submit=True,
            allow_revision=True,
        )

        current = str(neg.get("status") or NegotiationStatus.IN_PROGRESS)
        if current != NegotiationStatus.AGREED:
            _assert_neg_transition(current, NegotiationStatus.AGREED)
        await mongo_manager.collection(CollectionName.NEGOTIATIONS).update_one(
            {"_id": neg["_id"]},
            {
                "$set": {
                    "status": NegotiationStatus.AGREED,
                    "agreed_at": now,
                    "agreed_offer_id": claimed["_id"],
                    "updated_at": now,
                }
            },
        )
        await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS).update_many(
            {
                "negotiation_id": neg["_id"],
                "_id": {"$ne": claimed["_id"]},
                "status": NegotiationOfferStatus.PROPOSED,
            },
            {"$set": {"status": NegotiationOfferStatus.REJECTED, "responded_at": now}},
        )
        return await self.get(negotiation_id=negotiation_id, business=business)

    async def reject_offer(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        negotiation_id: str,
        offer_id: str,
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        neg = await mongo_manager.collection(CollectionName.NEGOTIATIONS).find_one(
            {"_id": parse_object_id(negotiation_id)}
        )
        if neg is None:
            raise NotFoundError("We couldn't find that negotiation.")
        self._assert_access(neg, business)
        if neg.get("status") not in {NegotiationStatus.OPEN, NegotiationStatus.IN_PROGRESS}:
            raise BadRequestError("This negotiation has ended, so offers can no longer change.")
        if neg.get("rfq_id"):
            rfq = await mongo_manager.collection(CollectionName.RFQS).find_one(
                {"_id": neg["rfq_id"]}, {"status": 1}
            )
            if rfq and str(rfq.get("status")) == "awarded":
                raise BadRequestError("This RFQ has been awarded—offers can no longer be rejected")

        now = utc_now()
        claimed = await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS).find_one_and_update(
            {
                "_id": parse_object_id(offer_id),
                "negotiation_id": neg["_id"],
                "status": NegotiationOfferStatus.PROPOSED,
            },
            {"$set": {"status": NegotiationOfferStatus.REJECTED, "responded_at": now}},
        )
        if claimed is None:
            raise BadRequestError("This offer was already answered or has expired.")
                                                                                            
        if claimed.get("parent_offer_id"):
            await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS).update_one(
                {"_id": claimed["parent_offer_id"], "status": NegotiationOfferStatus.PROPOSED},
                {"$set": {"status": NegotiationOfferStatus.COUNTERED, "responded_at": now}},
            )
        _ = user_id
        return await self.get(negotiation_id=negotiation_id, business=business)
