"""Recommendation engine — ranks REAL TradeBay catalog rows only."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai_sourcing.constants import (
    WEIGHT_CATEGORY,
    WEIGHT_DESCRIPTION,
    WEIGHT_INVENTORY,
    WEIGHT_MOQ,
    WEIGHT_NAME,
    WEIGHT_VERIFIED,
    AvailabilityStatus,
    RelevanceLabel,
)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def relevance_label(score: float) -> str:
    if score >= 0.72:
        return RelevanceLabel.HIGHLY_RELEVANT
    if score >= 0.45:
        return RelevanceLabel.RELEVANT
    return RelevanceLabel.PARTIAL


@dataclass
class ScoredCandidate:
    product: dict[str, Any]
    supplier: dict[str, Any]
    inventory: dict[str, Any] | None
    price: dict[str, Any] | None
    category_name: str | None
    score: float
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    availability: str = AvailabilityStatus.UNKNOWN
    similar: bool = False


class RecommendationEngine:
    """Hard filters first, then weighted relevance from factual fields only.

    When exact matches are thin, fills the haul with softer *similar* catalog picks
    from verified suppliers so buyers still see useful recommendations.
    """

    def rank(
        self,
        *,
        requirements: ProcurementRequirements,
        products: list[dict[str, Any]],
        suppliers_by_business: dict[str, dict[str, Any]],
        inventories_by_product: dict[str, dict[str, Any]],
        prices_by_product: dict[str, list[dict[str, Any]]],
        categories_by_id: dict[str, dict[str, Any]],
        verified_business_ids: set[str],
        limit: int = 20,
        min_results: int = 8,
    ) -> list[ScoredCandidate]:
        need_terms = self._requirement_terms(requirements)
        qty_hint = self._primary_quantity(requirements)
        results: list[ScoredCandidate] = []
        scored_ids: set[str] = set()

        for product in products:
            candidate = self._build_candidate(
                product=product,
                suppliers_by_business=suppliers_by_business,
                inventories_by_product=inventories_by_product,
                prices_by_product=prices_by_product,
                categories_by_id=categories_by_id,
                verified_business_ids=verified_business_ids,
                requirements=requirements,
                need_terms=need_terms,
                qty_hint=qty_hint,
                similar=False,
            )
            if candidate is None or candidate.score <= 0:
                continue
            pid = str(candidate.product.get("_id") or "")
            scored_ids.add(pid)
            results.append(candidate)

        results.sort(key=lambda c: c.score, reverse=True)

        if len(results) < min_results:
            similar_rows: list[ScoredCandidate] = []
            for product in products:
                pid = str(product.get("_id") or product.get("id") or "")
                if pid in scored_ids:
                    continue
                candidate = self._build_candidate(
                    product=product,
                    suppliers_by_business=suppliers_by_business,
                    inventories_by_product=inventories_by_product,
                    prices_by_product=prices_by_product,
                    categories_by_id=categories_by_id,
                    verified_business_ids=verified_business_ids,
                    requirements=requirements,
                    need_terms=need_terms,
                    qty_hint=qty_hint,
                    similar=True,
                )
                if candidate is None or candidate.score <= 0:
                    continue
                similar_rows.append(candidate)
            similar_rows.sort(key=lambda c: c.score, reverse=True)
            for row in similar_rows:
                if len(results) >= limit:
                    break
                results.append(row)

        return results[:limit]

    def _build_candidate(
        self,
        *,
        product: dict[str, Any],
        suppliers_by_business: dict[str, dict[str, Any]],
        inventories_by_product: dict[str, dict[str, Any]],
        prices_by_product: dict[str, list[dict[str, Any]]],
        categories_by_id: dict[str, dict[str, Any]],
        verified_business_ids: set[str],
        requirements: ProcurementRequirements,
        need_terms: set[str],
        qty_hint: float | None,
        similar: bool,
    ) -> ScoredCandidate | None:
        business_id = str(product.get("business_account_id") or "")
        if not business_id:
            return None
        if business_id not in verified_business_ids:
            return None
        if str(product.get("status") or "").lower() != "active":
            return None

        supplier = suppliers_by_business.get(business_id) or {}
        inventory = inventories_by_product.get(str(product.get("_id") or product.get("id") or ""))
        prices = prices_by_product.get(str(product.get("_id") or product.get("id") or ""), [])
        active_prices = [p for p in prices if p.get("is_active", True)]
        price = active_prices[0] if active_prices else None
        cat = categories_by_id.get(str(product.get("category_id") or ""))
        category_name = str(cat.get("name")) if cat else None

        if similar:
            return self._score_similar(
                product=product,
                supplier=supplier,
                inventory=inventory,
                price=price,
                category_name=category_name,
                requirements=requirements,
                need_terms=need_terms,
            )
        return self._score_product(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            requirements=requirements,
            need_terms=need_terms,
            qty_hint=qty_hint,
            verified=True,
        )

    def _requirement_terms(self, requirements: ProcurementRequirements) -> set[str]:
        bag: set[str] = set()
        for item in requirements.product_requirements + requirements.categories:
            bag |= _tokens(item)
        for qty in requirements.quantities:
            bag |= _tokens(qty.product)
        if requirements.business_type:
            bag |= _tokens(requirements.business_type)
        bag |= _tokens(requirements.business_description[:400])
        return bag

    def _primary_quantity(self, requirements: ProcurementRequirements) -> float | None:
        for qty in requirements.quantities:
            if qty.quantity is not None:
                return float(qty.quantity)
        return None

    def _score_product(
        self,
        *,
        product: dict[str, Any],
        supplier: dict[str, Any],
        inventory: dict[str, Any] | None,
        price: dict[str, Any] | None,
        category_name: str | None,
        requirements: ProcurementRequirements,
        need_terms: set[str],
        qty_hint: float | None,
        verified: bool,
    ) -> ScoredCandidate:
        name = str(product.get("name") or "")
        description = str(product.get("description") or "")
        name_tokens = _tokens(name)
        desc_tokens = _tokens(description)
        cat_tokens = _tokens(category_name or "")

        name_score = _overlap_ratio(need_terms, name_tokens)
        desc_score = _overlap_ratio(need_terms, desc_tokens)
        cat_score = _overlap_ratio(need_terms, cat_tokens)

        req_blob = " ".join(requirements.product_requirements + requirements.categories).lower()
        if req_blob and (
            req_blob in name.lower()
            or any(r.lower() in name.lower() for r in requirements.product_requirements)
        ):
            name_score = max(name_score, 0.75)
        if category_name and any(
            r.lower() in category_name.lower() or category_name.lower() in r.lower()
            for r in (requirements.categories + requirements.product_requirements)
        ):
            cat_score = max(cat_score, 0.8)

        matched: list[str] = []
        unmatched: list[str] = []
        reasons: list[str] = []

        for req in requirements.product_requirements:
            if (
                _overlap_ratio(_tokens(req), name_tokens | cat_tokens | desc_tokens) >= 0.34
                or req.lower() in name.lower()
            ):
                matched.append(req)
                reasons.append(f"Product matches your “{req}” requirement")
            else:
                unmatched.append(req)

        for cat_req in requirements.categories:
            if category_name and (
                cat_req.lower() in category_name.lower() or category_name.lower() in cat_req.lower()
            ):
                if cat_req not in matched:
                    matched.append(cat_req)
                reasons.append(f"Listed under category {category_name}")

        score = (
            WEIGHT_NAME * name_score
            + WEIGHT_DESCRIPTION * desc_score
            + WEIGHT_CATEGORY * cat_score
        )

        if verified:
            score += WEIGHT_VERIFIED
            reasons.append("Supplier is verified on TradeBay")

        availability = AvailabilityStatus.UNKNOWN
        if inventory is not None:
            try:
                available = Decimal(str(inventory.get("available_quantity", "0")))
            except Exception:
                available = Decimal("0")
            if available > 0:
                availability = (
                    AvailabilityStatus.IN_STOCK if available >= 20 else AvailabilityStatus.LIMITED
                )
                score += WEIGHT_INVENTORY
                reasons.append("Inventory shows available stock")
            else:
                availability = AvailabilityStatus.OUT_OF_STOCK

        moq = int(product.get("moq") or 1)
        if qty_hint is not None:
            if qty_hint >= moq:
                score += WEIGHT_MOQ
                reasons.append(f"Supports your quantity (MOQ {moq})")
                matched.append("quantity / MOQ")
            else:
                unmatched.append("quantity / MOQ")
                reasons.append(f"MOQ is {moq} — higher than the quantity you mentioned")
                score *= 0.85
        elif "Bulk availability" in requirements.supplier_preferences:
            if moq >= 10:
                score += WEIGHT_MOQ * 0.7
                reasons.append("Supports bulk purchasing")
                matched.append("bulk purchasing")

        if requirements.location and product.get("origin"):
            origin = str(product["origin"])
            if _overlap_ratio(_tokens(requirements.location), _tokens(origin)) > 0:
                reasons.append(f"Product origin noted as {origin}")

        if requirements.delivery_requirements:
            unmatched.append("delivery area (not confirmed in catalog data)")

        if name_score < 0.15 and cat_score < 0.15 and desc_score < 0.15 and not matched:
            return ScoredCandidate(
                product=product,
                supplier=supplier,
                inventory=inventory,
                price=price,
                category_name=category_name,
                score=0.0,
                availability=availability,
            )

        score = min(score, 1.0)
        return ScoredCandidate(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            score=round(score, 4),
            matched=matched,
            unmatched=unmatched,
            reasons=self._unique_reasons(reasons),
            availability=availability,
            similar=False,
        )

    def _score_similar(
        self,
        *,
        product: dict[str, Any],
        supplier: dict[str, Any],
        inventory: dict[str, Any] | None,
        price: dict[str, Any] | None,
        category_name: str | None,
        requirements: ProcurementRequirements,
        need_terms: set[str],
    ) -> ScoredCandidate:
        """Softer ranking for nearby / related catalog picks."""
        name = str(product.get("name") or "")
        description = str(product.get("description") or "")
        name_tokens = _tokens(name)
        desc_tokens = _tokens(description)
        cat_tokens = _tokens(category_name or "")
        pool = name_tokens | desc_tokens | cat_tokens

        shared = need_terms & pool if need_terms else set()
        name_score = _overlap_ratio(need_terms, name_tokens) if need_terms else 0.0
        desc_score = _overlap_ratio(need_terms, desc_tokens) if need_terms else 0.0
        cat_score = _overlap_ratio(need_terms, cat_tokens) if need_terms else 0.0

        score = 0.18 + WEIGHT_VERIFIED * 0.65
        reasons = [
            "Similar to your brief — related listing from a verified supplier",
            "Supplier is verified on TradeBay",
        ]
        matched: list[str] = []

        if shared:
            score += 0.12 + 0.35 * max(name_score, desc_score, cat_score)
            sample = sorted(shared)[:3]
            reasons.insert(0, f"Shares terms with your brief: {', '.join(sample)}")
            matched.extend(sample)

        if category_name:
            score += WEIGHT_CATEGORY * max(cat_score, 0.25)
            reasons.append(f"Listed under {category_name}")

        availability = AvailabilityStatus.UNKNOWN
        if inventory is not None:
            try:
                available = Decimal(str(inventory.get("available_quantity", "0")))
            except Exception:
                available = Decimal("0")
            if available > 0:
                availability = (
                    AvailabilityStatus.IN_STOCK if available >= 20 else AvailabilityStatus.LIMITED
                )
                score += WEIGHT_INVENTORY * 0.8
                reasons.append("Inventory shows available stock")
            else:
                availability = AvailabilityStatus.OUT_OF_STOCK

        if requirements.business_type and (
            requirements.business_type.lower() in name.lower()
            or requirements.business_type.lower() in (category_name or "").lower()
        ):
            score += 0.08
            reasons.append(f"Fits {requirements.business_type} sourcing")

        # Keep similar scores in the partial band so exact matches stay on top
        score = min(score, 0.44)

        return ScoredCandidate(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            score=round(score, 4),
            matched=matched,
            unmatched=list(requirements.product_requirements),
            reasons=self._unique_reasons(reasons),
            availability=availability,
            similar=True,
        )

    @staticmethod
    def _unique_reasons(reasons: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for reason in reasons:
            if reason not in seen:
                seen.add(reason)
                unique.append(reason)
        return unique
