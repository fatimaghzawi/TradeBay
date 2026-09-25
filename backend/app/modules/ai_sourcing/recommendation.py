
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

def _best_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return max(_overlap_ratio(a, b), _overlap_ratio(b, a))

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
    signals: dict[str, float] = field(default_factory=dict)
    availability: str = AvailabilityStatus.UNKNOWN
    similar: bool = False

class RecommendationEngine:

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
        semantic_scores: dict[str, float] | None = None,
    ) -> list[ScoredCandidate]:
        need_terms = self._requirement_terms(requirements)
        focus_terms = self._focus_terms(requirements)
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
                focus_terms=focus_terms,
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
                    focus_terms=focus_terms,
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

        if semantic_scores:
            for row in results:
                pid = str(row.product.get("_id") or "")
                raw = semantic_scores.get(pid)
                if raw is None:
                    continue
                semantic = max(0.0, min(1.0, float(raw)))
                row.signals["semantic_match"] = round(semantic, 4)
                row.score = round(min(1.0, row.score * 0.85 + 0.15 * semantic), 4)

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
        focus_terms: set[str],
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
                need_terms=focus_terms or need_terms,
            )
        return self._score_product(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            requirements=requirements,
            need_terms=need_terms,
            focus_terms=focus_terms,
            qty_hint=qty_hint,
            verified=True,
        )

    def _focus_terms(self, requirements: ProcurementRequirements) -> set[str]:
        bag: set[str] = set()
        for item in requirements.product_requirements + requirements.categories:
            bag |= _tokens(item)
                                            
            for token in list(_tokens(item)):
                if token.endswith("s") and len(token) > 4:
                    bag.add(token[:-1])
        for qty in requirements.quantities:
            bag |= _tokens(qty.product)
        return bag

    def _requirement_terms(self, requirements: ProcurementRequirements) -> set[str]:
        bag = self._focus_terms(requirements)
        if requirements.business_type:
            bag |= _tokens(requirements.business_type)
                                                                                  
        soft = _tokens(requirements.business_description[:240])
                                                        
        filler = {
            "looking",
            "need",
            "want",
            "business",
            "company",
            "please",
            "help",
            "finding",
            "partners",
            "suppliers",
            "supplier",
            "usually",
            "every",
            "month",
            "lebanon",
        }
        bag |= {t for t in soft if t not in filler and len(t) > 3}
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
        focus_terms: set[str],
        qty_hint: float | None,
        verified: bool,
    ) -> ScoredCandidate:
        name = str(product.get("name") or "")
        description = str(product.get("description") or "")
        name_tokens = _tokens(name)
        desc_tokens = _tokens(description)
        cat_tokens = _tokens(category_name or "")
        query = focus_terms or need_terms

        name_score = _best_overlap(query, name_tokens)
        desc_score = _best_overlap(query, desc_tokens)
        cat_score = _best_overlap(query, cat_tokens)

        req_blob = " ".join(requirements.product_requirements + requirements.categories).lower()
        if req_blob and (
            req_blob in name.lower()
            or any(r.lower() in name.lower() for r in requirements.product_requirements)
            or any(
                r.lower().rstrip("s") in name.lower()
                for r in requirements.product_requirements
                if len(r) > 3
            )
        ):
            name_score = max(name_score, 0.75)
        if category_name and any(
            r.lower() in category_name.lower()
            or category_name.lower() in r.lower()
            or r.lower().rstrip("s") in category_name.lower()
            for r in (requirements.categories + requirements.product_requirements)
        ):
            cat_score = max(cat_score, 0.8)

        matched: list[str] = []
        unmatched: list[str] = []
        reasons: list[str] = []

        for req in requirements.product_requirements:
            req_tokens = _tokens(req)
            if (
                _best_overlap(req_tokens, name_tokens | cat_tokens | desc_tokens) >= 0.34
                or req.lower() in name.lower()
                or req.lower().rstrip("s") in name.lower()
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

        if name_score < 0.12 and cat_score < 0.12 and desc_score < 0.12 and not matched:
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
        signals = {
            "text_match": round(name_score, 4),
            "description_match": round(desc_score, 4),
            "category_match": round(cat_score, 4),
            "supplier_verified": 1.0 if verified else 0.0,
            "inventory_match": 1.0 if availability in {
                AvailabilityStatus.IN_STOCK,
                AvailabilityStatus.LIMITED,
            } else 0.0,
        }
        if qty_hint is not None:
            signals["moq_match"] = 1.0 if qty_hint >= moq else 0.0
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
            signals=signals,
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
        name = str(product.get("name") or "")
        description = str(product.get("description") or "")
        name_tokens = _tokens(name)
        desc_tokens = _tokens(description)
        cat_tokens = _tokens(category_name or "")
        pool = name_tokens | desc_tokens | cat_tokens

        empty = ScoredCandidate(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            score=0.0,
            availability=AvailabilityStatus.UNKNOWN,
            similar=True,
        )
        if not need_terms:
            return empty

        shared = need_terms & pool
                                                                         
        stemmed_need = set(need_terms)
        for t in list(need_terms):
            if t.endswith("s") and len(t) > 4:
                stemmed_need.add(t[:-1])
            else:
                stemmed_need.add(t + "s")
        shared |= stemmed_need & pool

        category_hit = False
        if category_name:
            cat_l = category_name.lower()
            category_hit = any(
                r.lower() in cat_l or cat_l in r.lower() or r.lower().rstrip("s") in cat_l
                for r in (requirements.categories + requirements.product_requirements)
                if r
            )

        if not shared and not category_hit:
            return empty

        name_score = _best_overlap(need_terms, name_tokens)
        desc_score = _best_overlap(need_terms, desc_tokens)
        cat_score = _best_overlap(need_terms, cat_tokens)
        if category_hit:
            cat_score = max(cat_score, 0.55)

        score = 0.2 + WEIGHT_VERIFIED * 0.5
        reasons = ["Similar to your brief — related listing from a verified supplier"]
        matched: list[str] = []

        if shared:
            score += 0.15 + 0.4 * max(name_score, desc_score, cat_score)
            sample = sorted(shared)[:3]
            reasons.insert(0, f"Related to your ask: {', '.join(sample)}")
            matched.extend(sample)
        elif category_hit:
            score += 0.2
            reasons.insert(0, f"Same category family as your ask ({category_name})")
            if category_name:
                matched.append(category_name)

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
                score += WEIGHT_INVENTORY * 0.6
                reasons.append("Inventory shows available stock")
            else:
                availability = AvailabilityStatus.OUT_OF_STOCK

        score = min(score, 0.44)

        return ScoredCandidate(
            product=product,
            supplier=supplier,
            inventory=inventory,
            price=price,
            category_name=category_name,
            score=round(score, 4),
            matched=matched,
            unmatched=[
                r
                for r in requirements.product_requirements
                if r.lower() not in {m.lower() for m in matched}
            ],
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
