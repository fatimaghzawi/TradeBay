
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.ai.eligibility import decide_eligibility
from app.modules.ai.provider import AIProvider, get_ai_provider
from app.modules.ai.quota import consume_ai_quota
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai.retrieval import (
    CatalogRetriever,
    MongoHybridRetriever,
    schedule_embedding_sync,
)
from app.modules.ai_sourcing.constants import (
    RECOMMENDATION_LIMIT,
    SourcingRequestStatus,
)
from app.modules.ai_sourcing.exceptions import (
    BuyerBusinessRequiredError,
    SourcingNotOwnedError,
    SourcingRequestNotFoundError,
    SourcingRequirementsMissingError,
)
from app.modules.ai_sourcing.recommendation import RecommendationEngine, relevance_label
from app.modules.ai_sourcing.repository import (
    BusinessProcurementProfileRepository,
    SourcingRecommendationRepository,
    SourcingRequestItemRepository,
    SourcingRequestRepository,
)
from app.modules.identity.constants import BusinessAccountType
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

logger = logging.getLogger(__name__)

def _now() -> datetime:
    return utc_now()

def _rfq_quantity(requirements: ProcurementRequirements, row: dict[str, Any]) -> int:
    moq_raw = row.get("moq")
    try:
        moq = max(1, int(moq_raw)) if moq_raw is not None else 1
    except (TypeError, ValueError):
        moq = 1

    product_name = str(row.get("product_name") or "").lower()
    requested: float | None = None
    for qty in requirements.quantities:
        if qty.quantity is None or qty.quantity <= 0:
            continue
                                                                                     
        if qty.product and qty.product.lower() in product_name:
            requested = float(qty.quantity)
            break
        if requested is None:
            requested = float(qty.quantity)
    if requested is None:
        return moq
    return max(int(requested), moq)

def _clarification(requirements: ProcurementRequirements) -> str | None:
    missing = requirements.missing_information
    if not missing:
        return None
    readable = ", ".join(missing[:4])
    return (
        f"I can search once you confirm. It would help to know {readable}. "
        "You can add that above, or continue with what you already shared."
    )

def _oid_str(value: Any) -> str:
    return str(value)

def _serialize_request(
    doc: dict[str, Any],
    *,
    item_count: int = 0,
    recommendation_count: int = 0,
) -> dict[str, Any]:
    return {
        "id": _oid_str(doc["_id"]),
        "status": doc.get("status"),
        "original_prompt": doc.get("original_prompt"),
        "requirements": doc.get("requirements"),
        "ai_summary": doc.get("ai_summary"),
        "destination": doc.get("destination"),
        "item_count": item_count,
        "recommendation_count": recommendation_count,
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }

def _money_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

class AISourcingService:
    def __init__(
        self,
        *,
        requests: SourcingRequestRepository | None = None,
        items: SourcingRequestItemRepository | None = None,
        recommendations: SourcingRecommendationRepository | None = None,
        profiles: BusinessProcurementProfileRepository | None = None,
        ai: AIProvider | None = None,
        engine: RecommendationEngine | None = None,
        retriever: CatalogRetriever | None = None,
    ) -> None:
        self.requests = requests or SourcingRequestRepository()
        self.items = items or SourcingRequestItemRepository()
        self.recommendations = recommendations or SourcingRecommendationRepository()
        self.profiles = profiles or BusinessProcurementProfileRepository()
        self.ai = ai or get_ai_provider()
        self.engine = engine or RecommendationEngine()
        embedder = self.ai if getattr(self.ai, "supports_generation", False) else None
        self.retriever = retriever or MongoHybridRetriever(embedder=embedder)

    def _require_buyer(self, business: dict[str, Any] | None) -> str:
        if business is None:
            raise BuyerBusinessRequiredError()
        if str(business.get("type") or "") != BusinessAccountType.BUYER:
            raise BuyerBusinessRequiredError()
        return str(business["_id"])

    async def _get_owned_request(
        self, sourcing_request_id: str, *, business_id: str
    ) -> dict[str, Any]:
        doc = await self.requests.get_by_id(sourcing_request_id)
        if doc is None:
            raise SourcingRequestNotFoundError()
        if str(doc.get("buyer_business_id") or "") != business_id:
            raise SourcingNotOwnedError()
        return doc

    async def analyze(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        business_description: str,
    ) -> dict[str, Any]:
        business_id = self._require_buyer(business)
        await consume_ai_quota(subject_id=business_id, feature="ai_sourcing_analyze")
        requirements = await self.ai.extract_procurement_requirements(business_description)
        now = _now()
        doc = await self.requests.create(
            {
                "buyer_user_id": parse_object_id(user_id),
                "buyer_business_id": parse_object_id(business_id),
                "original_prompt": business_description.strip(),
                "destination": requirements.delivery_requirements or requirements.location,
                "required_date": None,
                "status": SourcingRequestStatus.DRAFT,
                "rfq_id": None,
                "business_plan_id": None,
                "profile_id": None,
                "requirements": requirements.model_dump(),
                "ai_summary": self._summary(requirements),
                "created_at": now,
                "updated_at": now,
            }
        )
        return {
            "sourcing_request_id": _oid_str(doc["_id"]),
            "requirements": requirements.model_dump(),
            "status": SourcingRequestStatus.DRAFT,
            "clarification": _clarification(requirements),
        }

    def _summary(self, requirements: ProcurementRequirements) -> str:
        bits: list[str] = []
        if requirements.business_type:
            bits.append(requirements.business_type)
        if requirements.product_requirements:
            bits.append("needs " + ", ".join(requirements.product_requirements[:4]))
        if requirements.location:
            bits.append(f"in {requirements.location}")
        return "; ".join(bits) if bits else requirements.business_description[:160]

    async def confirm_requirements(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        sourcing_request_id: str,
        requirements: ProcurementRequirements,
    ) -> dict[str, Any]:
        business_id = self._require_buyer(business)
        doc = await self._get_owned_request(sourcing_request_id, business_id=business_id)
        now = _now()
        profile = await self._upsert_profile(business_id=business_id, requirements=requirements, now=now)
        updated = await self.requests.update(
            doc["_id"],
            {
                "requirements": requirements.model_dump(),
                "ai_summary": self._summary(requirements),
                "destination": requirements.delivery_requirements or requirements.location,
                "profile_id": profile["_id"],
                "status": SourcingRequestStatus.DRAFT,
                "updated_at": now,
            },
        )
        assert updated is not None
        return {
            "sourcing_request_id": _oid_str(updated["_id"]),
            "requirements": requirements.model_dump(),
            "status": updated["status"],
            "profile_id": _oid_str(profile["_id"]),
        }

    async def _upsert_profile(
        self,
        *,
        business_id: str,
        requirements: ProcurementRequirements,
        now: datetime,
    ) -> dict[str, Any]:
        existing = await self.profiles.get_by_business(business_id)
        payload = {
            "business_account_id": parse_object_id(business_id),
            "business_description": requirements.business_description,
            "business_type": requirements.business_type,
            "location": requirements.location,
            "product_requirements": requirements.product_requirements,
            "categories": requirements.categories,
            "quantity_requirements": [q.model_dump() for q in requirements.quantities],
            "purchase_frequency": requirements.purchase_frequency,
            "delivery_requirements": requirements.delivery_requirements,
            "supplier_preferences": requirements.supplier_preferences,
            "budget_range": requirements.budget_range,
            "ai_summary": self._summary(requirements),
            "missing_information": requirements.missing_information,
            "updated_at": now,
        }
        if existing is None:
            payload["created_at"] = now
            return await self.profiles.create(payload)
        updated = await self.profiles.update(existing["_id"], payload)
        assert updated is not None
        return updated

    async def get_profile(self, *, business: dict[str, Any] | None) -> dict[str, Any] | None:
        business_id = self._require_buyer(business)
        doc = await self.profiles.get_by_business(business_id)
        if doc is None:
            return None
        return {
            "id": _oid_str(doc["_id"]),
            "business_account_id": _oid_str(doc["business_account_id"]),
            "business_description": doc.get("business_description"),
            "business_type": doc.get("business_type"),
            "location": doc.get("location"),
            "product_requirements": doc.get("product_requirements") or [],
            "categories": doc.get("categories") or [],
            "quantity_requirements": doc.get("quantity_requirements") or [],
            "purchase_frequency": doc.get("purchase_frequency"),
            "delivery_requirements": doc.get("delivery_requirements"),
            "supplier_preferences": doc.get("supplier_preferences") or [],
            "budget_range": doc.get("budget_range"),
            "ai_summary": doc.get("ai_summary"),
            "missing_information": doc.get("missing_information") or [],
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        }

    async def recommend(
        self,
        *,
        business: dict[str, Any] | None,
        sourcing_request_id: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        business_id = self._require_buyer(business)
        doc = await self._get_owned_request(sourcing_request_id, business_id=business_id)
        raw_reqs = doc.get("requirements")
        if not raw_reqs:
            raise SourcingRequirementsMissingError()
        requirements = ProcurementRequirements.model_validate(raw_reqs)

        now = _now()
        await self.requests.update(
            doc["_id"],
            {"status": SourcingRequestStatus.SEARCHING, "updated_at": now},
        )

        try:
            retrieved = await self.retriever.retrieve(
                requirements,
                limit=get_settings().ai_max_candidates,
            )
        except Exception:
            logger.exception("Catalog retrieval failed")
            retrieved = []

        if retrieved and getattr(self.ai, "supports_generation", False):
            categories = {
                str(item.product.get("category_id")): {"name": item.category_name}
                for item in retrieved
                if item.product.get("category_id")
            }
            schedule_embedding_sync(
                [item.product for item in retrieved],
                categories_by_id=categories,
                embedder=self.ai,
            )

        eligible = []
        for item in retrieved:
            decision = decide_eligibility(
                product=item.product,
                inventory=item.inventory,
                verified=item.verified,
                requirements=requirements,
            )
            if decision.eligible:
                eligible.append((item, decision))

        products = [item.product for item, _decision in eligible]
        suppliers = {
            str(item.product.get("business_account_id")): item.supplier
            for item, _decision in eligible
            if item.product.get("business_account_id")
        }
        inventories = {
            item.product_id: item.inventory
            for item, _decision in eligible
            if item.inventory is not None
        }
        prices = {item.product_id: item.prices for item, _decision in eligible}
        categories_by_id = {}
        for item, _decision in eligible:
            cat_id = item.product.get("category_id")
            if cat_id is not None:
                categories_by_id[str(cat_id)] = {"_id": cat_id, "name": item.category_name}
        verified_ids = {
            str(item.product.get("business_account_id"))
            for item, _decision in eligible
            if item.verified and item.product.get("business_account_id")
        }
        semantic_scores = {
            item.product_id: item.semantic_score
            for item, _decision in eligible
            if item.semantic_score is not None
        }
        moq_notes = {
            decision.product_id: decision
            for _item, decision in eligible
        }

        scored = self.engine.rank(
            requirements=requirements,
            products=products,
            suppliers_by_business=suppliers,
            inventories_by_product=inventories,
            prices_by_product=prices,
            categories_by_id=categories_by_id,
            verified_business_ids=verified_ids,
            limit=min(limit, RECOMMENDATION_LIMIT),
            min_results=0,
            semantic_scores=semantic_scores or None,
        )

        await self.recommendations.delete_for_request(doc["_id"])
        product_rows: list[dict[str, Any]] = []
        similar_count = 0
        images = await self._primary_image_urls([item.product["_id"] for item, _d in eligible])
        for ranked in scored:
            product = ranked.product
            price = ranked.price
            if ranked.similar:
                similar_count += 1
            note = moq_notes.get(str(product.get("_id")))
            reasons = list(ranked.reasons)
            if note and note.moq_compatible is False:
                reasons.append("The quantity you mentioned is below this product's minimum order.")
            rec = await self.recommendations.create(
                {
                    "sourcing_request_id": doc["_id"],
                    "sourcing_request_item_id": None,
                    "product_id": product["_id"],
                    "business_account_id": product["business_account_id"],
                    "reason": reasons[0] if reasons else None,
                    "match_score": ranked.score,
                    "relevance_label": relevance_label(ranked.score),
                    "matched_requirements": ranked.matched,
                    "unmatched_requirements": ranked.unmatched,
                    "reasons": reasons,
                    "signals": ranked.signals,
                    "estimated_unit_price": price.get("unit_price") if price else None,
                    "estimated_total_price": None,
                    "availability_status": ranked.availability,
                    "created_at": now,
                }
            )
            product_rows.append(
                self._serialize_recommendation(
                    rec,
                    product=product,
                    supplier=ranked.supplier,
                    category_name=ranked.category_name,
                    price=price,
                    verified=True,
                    primary_image_url=images.get(str(product["_id"])),
                    signals=ranked.signals,
                )
            )

        suppliers_out = self._aggregate_suppliers(product_rows)
        message: str | None = None
        suggestions: list[str] = []
        loose_match = bool(product_rows) and similar_count >= max(1, len(product_rows) // 2)
        if not product_rows:
            message = "I couldn't find a verified supplier that currently meets your requirements."
            suggestions = [
                "Try a broader product type",
                "Try a different quantity",
                "Describe what you need another way",
            ]
        elif loose_match:
            message = "These are related listings from verified suppliers."
            suggestions = ["Add a more specific product name for a tighter match"]

        await self.requests.update(
            doc["_id"],
            {"status": SourcingRequestStatus.COMPLETED, "updated_at": _now()},
        )

        return {
            "sourcing_request_id": _oid_str(doc["_id"]),
            "status": SourcingRequestStatus.COMPLETED,
            "products": product_rows,
            "suppliers": suppliers_out,
            "message": message,
            "suggestions": suggestions,
            "loose_match": loose_match,
        }

    async def _primary_image_urls(self, product_ids: list[Any]) -> dict[str, str]:
        if not product_ids:
            return {}
        images_col = mongo_manager.collection(CollectionName.PRODUCT_IMAGES)
        rows = (
            await images_col.find({"product_id": {"$in": product_ids}})
            .sort([("is_primary", -1), ("display_order", 1), ("created_at", 1)])
            .to_list(length=max(len(product_ids) * 8, 1))
        )
        out: dict[str, str] = {}
        for row in rows:
            pid = str(row.get("product_id") or "")
            url = row.get("url")
            if pid and url and pid not in out:
                out[pid] = str(url)
        return out

    def _serialize_recommendation(
        self,
        rec: dict[str, Any],
        *,
        product: dict[str, Any],
        supplier: dict[str, Any],
        category_name: str | None,
        price: dict[str, Any] | None,
        verified: bool,
        primary_image_url: str | None = None,
        signals: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "id": _oid_str(rec["_id"]),
            "product_id": _oid_str(product["_id"]),
            "product_name": product.get("name"),
            "product_sku": product.get("sku"),
            "category_name": category_name,
            "supplier_id": _oid_str(product.get("business_account_id")),
            "supplier_name": supplier.get("name"),
            "supplier_verified": verified,
            "moq": product.get("moq"),
            "unit": product.get("unit"),
            "unit_price": _money_str(price.get("unit_price")) if price else None,
            "currency": price.get("currency") if price else None,
            "primary_image_url": primary_image_url or product.get("image_url"),
            "availability_status": rec.get("availability_status"),
            "relevance_label": rec.get("relevance_label"),
            "match_score": rec.get("match_score"),
            "matched_requirements": rec.get("matched_requirements") or [],
            "unmatched_requirements": rec.get("unmatched_requirements") or [],
            "reasons": rec.get("reasons") or [],
            "signals": signals if signals is not None else rec.get("signals") or {},
        }
        return payload

    def _aggregate_suppliers(self, product_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for row in product_rows:
            sid = row.get("supplier_id")
            if not sid:
                continue
            bucket = buckets.get(sid)
            if bucket is None:
                buckets[sid] = {
                    "supplier_id": sid,
                    "supplier_name": row.get("supplier_name") or "Supplier",
                    "verified": bool(row.get("supplier_verified")),
                    "product_count": 1,
                    "matched_requirements": list(row.get("matched_requirements") or []),
                    "reasons": list(row.get("reasons") or [])[:4],
                    "relevance_label": row.get("relevance_label"),
                    "_score": float(row.get("match_score") or 0),
                }
            else:
                bucket["product_count"] += 1
                for req in row.get("matched_requirements") or []:
                    if req not in bucket["matched_requirements"]:
                        bucket["matched_requirements"].append(req)
                bucket["_score"] = max(bucket["_score"], float(row.get("match_score") or 0))
                if relevance_label(bucket["_score"]) == "highly_relevant":
                    bucket["relevance_label"] = "highly_relevant"

        rows = sorted(buckets.values(), key=lambda r: r["_score"], reverse=True)
        for row in rows:
            row.pop("_score", None)
        return rows

    async def create_draft_request(
        self,
        *,
        business: dict[str, Any] | None,
        sourcing_request_id: str,
    ) -> dict[str, Any]:
        business_id = self._require_buyer(business)
        doc = await self._get_owned_request(sourcing_request_id, business_id=business_id)
        raw_reqs = doc.get("requirements")
        if not raw_reqs:
            raise SourcingRequirementsMissingError()
        requirements = ProcurementRequirements.model_validate(raw_reqs)

        await self.items.delete_for_request(doc["_id"])
        now = _now()
        names = list(
            dict.fromkeys(
                [
                    *requirements.product_requirements,
                    *[q.product for q in requirements.quantities],
                ]
            )
        )
        if not names:
            names = ["General wholesale needs"]

        qty_by_name = {
            q.product.lower(): q for q in requirements.quantities if q.product
        }
        for name in names:
            qty = qty_by_name.get(name.lower())
            quantity = Decimal(str(qty.quantity)) if qty and qty.quantity is not None else Decimal("0")
            unit = (qty.unit if qty and qty.unit else "unit") or "unit"
            await self.items.create(
                {
                    "sourcing_request_id": doc["_id"],
                    "product_id": None,
                    "category_id": None,
                    "requested_name": name,
                    "description": requirements.business_description[:500],
                    "quantity": quantity,
                    "unit": unit,
                    "budget_min": None,
                    "budget_max": None,
                    "required_date": None,
                    "destination": requirements.delivery_requirements or requirements.location,
                    "created_at": now,
                }
            )

        updated = await self.requests.update(
            doc["_id"],
            {
                "status": SourcingRequestStatus.DRAFT,
                "updated_at": _now(),
            },
        )
        assert updated is not None
        items = await self.items.list_for_request(doc["_id"])
        recs = await self.recommendations.list_for_request(doc["_id"])
        return {
            **_serialize_request(
                updated,
                item_count=len(items),
                recommendation_count=len(recs),
            ),
            "items": [
                {
                    "id": _oid_str(item["_id"]),
                    "requested_name": item.get("requested_name"),
                    "quantity": _money_str(item.get("quantity")),
                    "unit": item.get("unit"),
                    "destination": item.get("destination"),
                    "product_id": _oid_str(item["product_id"]) if item.get("product_id") else None,
                }
                for item in items
            ],
            "published": False,
            "message": "Sourcing request saved as draft. Review it before publishing an RFQ.",
        }

    async def get_request(
        self, *, business: dict[str, Any] | None, sourcing_request_id: str
    ) -> dict[str, Any]:
        business_id = self._require_buyer(business)
        doc = await self._get_owned_request(sourcing_request_id, business_id=business_id)
        items = await self.items.list_for_request(doc["_id"])
        recs = await self.recommendations.list_for_request(doc["_id"])
                                                               
        products_col = mongo_manager.collection(CollectionName.PRODUCTS)
        businesses_col = mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS)
        categories_col = mongo_manager.collection(CollectionName.CATEGORIES)
        prices_col = mongo_manager.collection(CollectionName.PRODUCT_PRICES)

        product_ids = [r["product_id"] for r in recs if r.get("product_id")]
        products = {
            str(p["_id"]): p
            for p in await products_col.find({"_id": {"$in": product_ids}}).to_list(
                length=max(len(product_ids), 1)
            )
        } if product_ids else {}
        business_ids = [p["business_account_id"] for p in products.values()]
        suppliers = {
            str(b["_id"]): b
            for b in await businesses_col.find({"_id": {"$in": business_ids}}).to_list(
                length=max(len(business_ids), 1)
            )
        } if business_ids else {}
        profiles_col = mongo_manager.collection(CollectionName.SUPPLIER_PROFILES)
        verified_ids = {
            str(row["business_account_id"])
            for row in await profiles_col.find(
                {
                    "business_account_id": {"$in": business_ids},
                    "verification_status": "verified",
                },
                {"business_account_id": 1},
            ).to_list(length=max(len(business_ids), 1))
        } if business_ids else set()
        cat_ids = [p["category_id"] for p in products.values() if p.get("category_id")]
        categories = {
            str(c["_id"]): c
            for c in await categories_col.find({"_id": {"$in": cat_ids}}).to_list(
                length=max(len(cat_ids), 1)
            )
        } if cat_ids else {}
        prices_by_product: dict[str, list[dict[str, Any]]] = {}
        if product_ids:
            for price in await prices_col.find(
                {"product_id": {"$in": product_ids}, "is_active": True}
            ).sort("min_quantity", 1).to_list(length=max(len(product_ids) * 10, 1)):
                prices_by_product.setdefault(str(price["product_id"]), []).append(price)

        images = await self._primary_image_urls(product_ids)

        product_rows = []
        for rec in recs:
            pid = str(rec["product_id"]) if rec.get("product_id") else None
            product = products.get(pid or "")
            if not product:
                continue
            if str(product.get("status") or "").lower() != "active":
                continue
            business_key = str(product.get("business_account_id") or "")
            if business_key not in verified_ids:
                continue
            supplier = suppliers.get(str(product.get("business_account_id")), {})
            cat = categories.get(str(product.get("category_id")), {})
            price_list = prices_by_product.get(pid or "", [])
            product_rows.append(
                self._serialize_recommendation(
                    rec,
                    product=product,
                    supplier=supplier,
                    category_name=cat.get("name") if cat else None,
                    price=price_list[0] if price_list else None,
                    verified=True,
                    primary_image_url=images.get(pid or ""),
                )
            )

        return {
            **_serialize_request(
                doc,
                item_count=len(items),
                recommendation_count=len(recs),
            ),
            "items": [
                {
                    "id": _oid_str(item["_id"]),
                    "requested_name": item.get("requested_name"),
                    "quantity": _money_str(item.get("quantity")),
                    "unit": item.get("unit"),
                    "destination": item.get("destination"),
                }
                for item in items
            ],
            "recommendations": {
                "products": product_rows,
                "suppliers": self._aggregate_suppliers(product_rows),
            },
        }

    async def convert_to_rfq(
        self, *, user_id: str, business: dict[str, Any] | None, sourcing_request_id: str
    ) -> dict[str, Any]:
        from app.modules.procurement.service import ProcurementService

        detail = await self.get_request(business=business, sourcing_request_id=sourcing_request_id)
        items_src = detail.get("items") or []
        products = (detail.get("recommendations") or {}).get("products") or []
        suppliers = (detail.get("recommendations") or {}).get("suppliers") or []
        requirements = ProcurementRequirements.model_validate(detail.get("requirements") or {})

        rfq_items = []
        if products:
            for p in products[:20]:
                rfq_items.append(
                    {
                        "product_id": p.get("product_id"),
                        "product_name": p.get("product_name") or "Product",
                        "sku": p.get("product_sku"),
                        "quantity": str(_rfq_quantity(requirements, p)),
                        "unit": p.get("unit") or "unit",
                        "target_unit_price": p.get("unit_price"),
                        "category_id": None,
                    }
                )
        else:
            for item in items_src:
                rfq_items.append(
                    {
                        "product_name": item.get("requested_name") or "Item",
                        "quantity": item.get("quantity") or "1",
                        "unit": item.get("unit") or "unit",
                    }
                )
        if not rfq_items:
            from app.core.exceptions import BadRequestError

            raise BadRequestError("Sourcing request has no items or recommendations to convert")

        dest = None
        for item in items_src:
            if item.get("destination"):
                dest = {"city": str(item["destination"]), "country": "Lebanon"}
                break

        rfq = await ProcurementService().create_sourcing_rfq(
            user_id=user_id,
            business=business,
            payload={
                "title": f"RFQ — {detail.get('ai_summary') or 'AI Sourcing'}"[:200],
                "description": detail.get("original_prompt"),
                "destination": dest,
                "currency": "USD",
                "visibility": "invited",
                "sourcing_request_id": sourcing_request_id,
                "items": rfq_items,
                "quantity": "1",
                "publish": False,
            },
        )
        await self.requests.update(
            parse_object_id(sourcing_request_id),
            {"rfq_id": parse_object_id(rfq["id"]), "updated_at": _now()},
        )
        supplier_ids = [
            s["supplier_id"] for s in suppliers if s.get("supplier_id") and s.get("verified")
        ]
        return {
            "rfq": rfq,
            "suggested_supplier_ids": supplier_ids,
            "message": "Draft RFQ created from sourcing request. Publish and invite suppliers next.",
        }

    async def list_requests(
        self,
        *,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        business_id = self._require_buyer(business)
        total = await self.requests.count_for_business(business_id)
        rows = await self.requests.list_for_business(
            business_id,
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return [_serialize_request(row) for row in rows], total
