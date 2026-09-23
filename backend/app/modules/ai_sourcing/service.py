"""AI Sourcing service — orchestrates extraction, profile, catalog match, draft request."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.core.config import get_settings
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.ai.provider import AIProvider, get_ai_provider
from app.modules.ai.rag import (
    RagRetriever,
    ensure_catalog_rag_index,
    format_rag_context,
    get_rag_retriever,
)
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai_sourcing.constants import (
    PRODUCT_CANDIDATE_LIMIT,
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
from app.modules.catalog.constants import ProductStatus
from app.modules.identity.constants import BusinessAccountType
from app.shared.utils.objectid import parse_object_id


def _now() -> datetime:
    return datetime.now(UTC)


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
        rag: RagRetriever | None = None,
    ) -> None:
        self.requests = requests or SourcingRequestRepository()
        self.items = items or SourcingRequestItemRepository()
        self.recommendations = recommendations or SourcingRecommendationRepository()
        self.profiles = profiles or BusinessProcurementProfileRepository()
        self.ai = ai or get_ai_provider()
        self.engine = engine or RecommendationEngine()
        self.rag = rag if rag is not None else get_rag_retriever()

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
        rag_context = await self._rag_context(business_description)
        requirements = await self.ai.extract_procurement_requirements(
            business_description,
            context=rag_context or None,
        )
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
        }

    async def _rag_context(self, business_description: str) -> str:
        """Retrieve catalog vocabulary for extraction. Empty when RAG is off."""
        cfg = get_settings()
        if not cfg.ai_rag_enabled:
            return ""
        store = await ensure_catalog_rag_index(self.rag, settings=cfg)
        chunks = await store.retrieve(
            business_description,
            top_k=max(1, cfg.ai_rag_top_k),
        )
        return format_rag_context(chunks)

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

        candidates = await self._load_catalog_candidates(requirements)
        scored = self.engine.rank(
            requirements=requirements,
            products=candidates["products"],
            suppliers_by_business=candidates["suppliers"],
            inventories_by_product=candidates["inventories"],
            prices_by_product=candidates["prices"],
            categories_by_id=candidates["categories"],
            verified_business_ids=candidates["verified_ids"],
            limit=min(limit, RECOMMENDATION_LIMIT),
            min_results=8,
        )

        await self.recommendations.delete_for_request(doc["_id"])
        product_rows: list[dict[str, Any]] = []
        similar_count = 0
        for item in scored:
            product = item.product
            price = item.price
            if item.similar:
                similar_count += 1
            rec = await self.recommendations.create(
                {
                    "sourcing_request_id": doc["_id"],
                    "sourcing_request_item_id": None,
                    "product_id": product["_id"],
                    "business_account_id": product["business_account_id"],
                    "reason": item.reasons[0] if item.reasons else None,
                    "match_score": item.score,
                    "relevance_label": relevance_label(item.score),
                    "matched_requirements": item.matched,
                    "unmatched_requirements": item.unmatched,
                    "reasons": item.reasons,
                    "estimated_unit_price": price.get("unit_price") if price else None,
                    "estimated_total_price": None,
                    "availability_status": item.availability,
                    "created_at": now,
                }
            )
            product_rows.append(
                self._serialize_recommendation(
                    rec,
                    product=product,
                    supplier=item.supplier,
                    category_name=item.category_name,
                    price=price,
                    verified=True,
                    primary_image_url=candidates["images"].get(str(product["_id"])),
                )
            )

        suppliers = self._aggregate_suppliers(product_rows)
        suggestions: list[str] = []
        if not product_rows:
            suggestions = [
                "Try broadening product categories",
                "Add alternate product names",
                "Ask platform staff to verify more suppliers in your categories",
            ]
        elif similar_count and similar_count >= max(1, len(product_rows) // 2):
            suggestions = [
                "Showing similar catalog matches — refine your brief for tighter fits",
            ]

        await self.requests.update(
            doc["_id"],
            {"status": SourcingRequestStatus.COMPLETED, "updated_at": _now()},
        )

        return {
            "sourcing_request_id": _oid_str(doc["_id"]),
            "status": SourcingRequestStatus.COMPLETED,
            "products": product_rows,
            "suppliers": suppliers,
            "suggestions": suggestions,
        }

    async def _load_catalog_candidates(
        self, requirements: ProcurementRequirements
    ) -> dict[str, Any]:
        products_col = mongo_manager.collection(CollectionName.PRODUCTS)
        categories_col = mongo_manager.collection(CollectionName.CATEGORIES)
        inventories_col = mongo_manager.collection(CollectionName.INVENTORIES)
        prices_col = mongo_manager.collection(CollectionName.PRODUCT_PRICES)
        businesses_col = mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS)
        profiles_col = mongo_manager.collection(CollectionName.SUPPLIER_PROFILES)

        search_terms = list(
            dict.fromkeys(
                [
                    *requirements.product_requirements,
                    *requirements.categories,
                    *[q.product for q in requirements.quantities],
                ]
            )
        )
        # Also search individual tokens so "cleaning products" matches "cleaner"
        token_terms: list[str] = []
        for term in search_terms:
            for token in re.findall(r"[a-z0-9]+", term.lower()):
                if len(token) > 2 and token not in token_terms:
                    token_terms.append(token)

        or_clauses: list[dict[str, Any]] = []
        for cleaned in [*search_terms, *token_terms]:
            text = cleaned.strip()
            if len(text) < 2:
                continue
            escaped = re.escape(text)
            or_clauses.append({"name": {"$regex": escaped, "$options": "i"}})
            or_clauses.append({"description": {"$regex": escaped, "$options": "i"}})

        # Category name → ids
        category_docs = await categories_col.find({"is_active": True}).to_list(length=200)
        categories_by_id = {str(c["_id"]): c for c in category_docs}
        category_ids: list[ObjectId] = []
        for cat in category_docs:
            name = str(cat.get("name") or "").lower()
            if any(
                term.lower() in name or name in term.lower()
                for term in requirements.categories + requirements.product_requirements + token_terms
                if term
            ):
                category_ids.append(cat["_id"])

        query: dict[str, Any] = {"status": ProductStatus.ACTIVE}
        or_filters: list[dict[str, Any]] = list(or_clauses)
        if category_ids:
            or_filters.append({"category_id": {"$in": category_ids}})
        if or_filters:
            query["$or"] = or_filters

        cursor = products_col.find(query).sort("updated_at", -1).limit(PRODUCT_CANDIDATE_LIMIT)
        products = await cursor.to_list(length=PRODUCT_CANDIDATE_LIMIT)

        # Broaden the pool for similar recommendations when the net came back thin
        if len(products) < 12:
            verified_profiles = await profiles_col.find(
                {"verification_status": "verified"}
            ).to_list(length=120)
            verified_biz_ids = [
                p["business_account_id"] for p in verified_profiles if p.get("business_account_id")
            ]
            if verified_biz_ids:
                broaden = (
                    await products_col.find(
                        {
                            "status": ProductStatus.ACTIVE,
                            "business_account_id": {"$in": verified_biz_ids},
                        }
                    )
                    .sort("updated_at", -1)
                    .limit(PRODUCT_CANDIDATE_LIMIT)
                    .to_list(length=PRODUCT_CANDIDATE_LIMIT)
                )
                seen = {str(p["_id"]) for p in products}
                for row in broaden:
                    rid = str(row["_id"])
                    if rid not in seen:
                        products.append(row)
                        seen.add(rid)
                    if len(products) >= PRODUCT_CANDIDATE_LIMIT:
                        break

        business_ids = list({p["business_account_id"] for p in products if p.get("business_account_id")})
        verified_ids: set[str] = set()
        suppliers: dict[str, dict[str, Any]] = {}
        if business_ids:
            profiles = await profiles_col.find(
                {
                    "business_account_id": {"$in": business_ids},
                    "verification_status": "verified",
                }
            ).to_list(length=len(business_ids))
            verified_ids = {str(p["business_account_id"]) for p in profiles}
            businesses = await businesses_col.find({"_id": {"$in": business_ids}}).to_list(
                length=len(business_ids)
            )
            for biz in businesses:
                suppliers[str(biz["_id"])] = biz

        product_ids = [p["_id"] for p in products]
        inventories: dict[str, dict[str, Any]] = {}
        prices: dict[str, list[dict[str, Any]]] = {}
        if product_ids:
            inv_rows = await inventories_col.find({"product_id": {"$in": product_ids}}).to_list(
                length=len(product_ids)
            )
            for inv in inv_rows:
                inventories[str(inv["product_id"])] = inv
            price_rows = await prices_col.find(
                {"product_id": {"$in": product_ids}, "is_active": True}
            ).sort("min_quantity", 1).to_list(length=max(len(product_ids) * 10, 1))
            for price in price_rows:
                prices.setdefault(str(price["product_id"]), []).append(price)

        return {
            "products": products,
            "suppliers": suppliers,
            "inventories": inventories,
            "prices": prices,
            "categories": categories_by_id,
            "verified_ids": verified_ids,
            "images": await self._primary_image_urls(product_ids),
        }

    async def _primary_image_urls(self, product_ids: list[Any]) -> dict[str, str]:
        """Map product_id → primary (or first) image URL."""
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
    ) -> dict[str, Any]:
        return {
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
        }

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
        """Materialize requirement items on the sourcing request. Remains DRAFT — never publishes RFQ."""
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
        # Re-hydrate product display for stored recommendations
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
        """Create a draft RFQ from a sourcing request + recommendations."""
        from app.modules.procurement.service import ProcurementService

        detail = await self.get_request(business=business, sourcing_request_id=sourcing_request_id)
        items_src = detail.get("items") or []
        products = (detail.get("recommendations") or {}).get("products") or []
        suppliers = (detail.get("recommendations") or {}).get("suppliers") or []

        rfq_items = []
        if products:
            for p in products[:20]:
                rfq_items.append(
                    {
                        "product_id": p.get("product_id"),
                        "product_name": p.get("product_name") or "Product",
                        "sku": None,
                        "quantity": "50",
                        "unit": "unit",
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
                "title": f"RFQ — {detail.get('title') or 'AI Sourcing'}",
                "description": detail.get("business_description") or detail.get("notes"),
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
