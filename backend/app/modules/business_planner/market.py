"""Catalog-backed market snapshot for Business Planner.

Only aggregates real TradeBay catalog rows. Never invents demand or RFQ stats.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import Decimal128, ObjectId

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.business_planner.constants import PriceEstimateSourceType
from app.modules.catalog.constants import ProductStatus
from app.modules.identity.constants import SupplierVerificationStatus
from app.shared.types.money import to_decimal128


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _tokens(text: str) -> set[str]:
    import re

    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


async def build_market_snapshot(
    *,
    preferences: dict[str, Any],
    limit_products: int = 40,
) -> dict[str, Any]:
    """Return marketplace aggregates + candidate products from real catalog data."""
    db = mongo_manager.database
    products_col = db[str(CollectionName.PRODUCTS)]
    prices_col = db[str(CollectionName.PRODUCT_PRICES)]
    categories_col = db[str(CollectionName.CATEGORIES)]
    businesses_col = db[str(CollectionName.BUSINESS_ACCOUNTS)]
    profiles_col = db[str(CollectionName.SUPPLIER_PROFILES)]

    goal = str(preferences.get("business_goal") or "")
    category_hints = [str(c).lower() for c in (preferences.get("category_hints") or [])]
    product_prefs = [str(p).lower() for p in (preferences.get("product_preferences") or [])]
    adaptive = preferences.get("adaptive") or {}
    adaptive_terms = []
    for v in adaptive.values():
        if isinstance(v, str):
            adaptive_terms.append(v.lower())
        elif isinstance(v, list):
            adaptive_terms.extend(str(x).lower() for x in v)

    search_terms = _tokens(
        " ".join([goal, *category_hints, *product_prefs, *adaptive_terms])
    )

    verified_profiles = await profiles_col.find(
        {"verification_status": SupplierVerificationStatus.VERIFIED},
        {"business_account_id": 1},
    ).to_list(length=500)
    verified_ids = [p["business_account_id"] for p in verified_profiles if p.get("business_account_id")]

    if not verified_ids:
        return {
            "label": "TradeBay data",
            "insufficient_data": True,
            "message": (
                "TradeBay does not currently have enough marketplace data to estimate this accurately."
            ),
            "product_count": 0,
            "supplier_count": 0,
            "categories": [],
            "price_range": None,
            "candidates": [],
        }

    biz_docs = await businesses_col.find({"_id": {"$in": verified_ids}}).to_list(length=len(verified_ids))
    suppliers_by_id = {str(d["_id"]): d for d in biz_docs}

    query: dict[str, Any] = {
        "status": ProductStatus.ACTIVE,
        "business_account_id": {"$in": verified_ids},
    }
    products = await products_col.find(query).limit(200).to_list(length=200)

    # Soft rank by token overlap when we have search terms
    scored: list[tuple[float, dict[str, Any]]] = []
    for product in products:
        blob = " ".join(
            [
                str(product.get("name") or ""),
                str(product.get("description") or ""),
                str(product.get("sku") or ""),
            ]
        )
        pt = _tokens(blob)
        score = len(pt & search_terms) / max(len(search_terms), 1) if search_terms else 0.15
        # Prefer products that match at least one term; keep a small baseline set if unsure
        if search_terms and score <= 0 and preferences.get("unsure_goal"):
            score = 0.05
        if search_terms and score <= 0 and not preferences.get("unsure_goal"):
            continue
        scored.append((score, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored and products:
        # Unsure / no match — sample diverse active products (still real)
        scored = [(0.05, p) for p in products[:limit_products]]

    top = [p for _, p in scored[:limit_products]]
    product_ids = [p["_id"] for p in top]
    category_ids = list({p["category_id"] for p in top if p.get("category_id")})

    categories: dict[str, dict[str, Any]] = {}
    if category_ids:
        cat_docs = await categories_col.find({"_id": {"$in": category_ids}}).to_list(length=100)
        categories = {str(c["_id"]): c for c in cat_docs}

    prices_by_product: dict[str, list[dict[str, Any]]] = {str(pid): [] for pid in product_ids}
    if product_ids:
        price_docs = await prices_col.find(
            {"product_id": {"$in": product_ids}, "is_active": True}
        ).to_list(length=500)
        for pr in price_docs:
            prices_by_product.setdefault(str(pr["product_id"]), []).append(pr)

    all_prices: list[Decimal] = []
    moqs: list[int] = []
    candidates: list[dict[str, Any]] = []
    supplier_ids_used: set[str] = set()
    category_counts: dict[str, int] = {}

    for product in top:
        pid = str(product["_id"])
        sid = str(product.get("business_account_id") or "")
        supplier_ids_used.add(sid)
        cat = categories.get(str(product.get("category_id") or ""))
        cat_name = str(cat.get("name")) if cat else None
        if cat_name:
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        moq = product.get("moq")
        if isinstance(moq, int):
            moqs.append(moq)

        price_rows = prices_by_product.get(pid) or []
        unit_price = None
        currency = "USD"
        for row in price_rows:
            d = _dec(row.get("unit_price"))
            if d is not None:
                all_prices.append(d)
                if unit_price is None:
                    unit_price = d
                    currency = str(row.get("currency") or "USD")

        supplier = suppliers_by_id.get(sid) or {}
        candidates.append(
            {
                "product_id": pid,
                "product_name": product.get("name"),
                "sku": product.get("sku"),
                "category_id": str(product["category_id"]) if product.get("category_id") else None,
                "category_name": cat_name,
                "supplier_business_id": sid or None,
                "supplier_name": supplier.get("name"),
                "supplier_verified": True,
                "moq": moq if isinstance(moq, int) else None,
                "unit": product.get("unit") or "unit",
                "unit_price": str(unit_price) if unit_price is not None else None,
                "currency": currency,
                "source_type": PriceEstimateSourceType.MARKETPLACE,
            }
        )

    price_range = None
    if all_prices:
        price_range = {
            "min": str(min(all_prices)),
            "avg": str((sum(all_prices) / Decimal(len(all_prices))).quantize(Decimal("0.01"))),
            "max": str(max(all_prices)),
            "sample_count": len(all_prices),
            "source_type": PriceEstimateSourceType.MARKETPLACE,
        }

    return {
        "label": "TradeBay data",
        "insufficient_data": len(candidates) == 0,
        "message": None
        if candidates
        else "TradeBay does not currently have enough marketplace data to estimate this accurately.",
        "product_count": len(candidates),
        "supplier_count": len(supplier_ids_used),
        "verified_supplier_count": len(supplier_ids_used),
        "categories": [
            {"name": name, "product_count": count}
            for name, count in sorted(category_counts.items(), key=lambda x: -x[1])
        ],
        "moq": {
            "min": min(moqs) if moqs else None,
            "max": max(moqs) if moqs else None,
            "source_type": PriceEstimateSourceType.MARKETPLACE,
        }
        if moqs
        else None,
        "price_range": price_range,
        "candidates": candidates,
        "location_note": (
            f"Location preference: {preferences.get('location')}. "
            "Delivery feasibility is an AI projection until logistics data is available."
        )
        if preferences.get("location")
        else None,
    }


# Keep Decimal128 helper import used for type clarity in callers that persist money
__all__ = ["ObjectId", "build_market_snapshot", "to_decimal128"]
