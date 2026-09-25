
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from app.db.collections import CollectionName
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai_sourcing.service import _rfq_quantity
from app.modules.business_planner.schemas import AIProductStrategyItem
from app.modules.business_planner.service import BusinessPlannerService, resolve_strategy_lines
from bson import ObjectId


def _item(**overrides) -> AIProductStrategyItem:
    base = {
        "product_id": "cand-1",
        "item_name": "Sparkling Water 1.5L",
        "quantity": 10,
        "target_selling_price": "3.00",
        "estimated_purchase_price": "1.00",
        "rationale": "Fits the budget.",
        "source_type": "MARKETPLACE",
    }
    base.update(overrides)
    return AIProductStrategyItem(**base)

def _market(**candidate_overrides) -> dict:
    candidate = {
        "product_id": "cand-1",
        "product_name": "Sparkling Water 1.5L",
        "category_id": "cat-1",
        "unit_price": "4.50",
        "moq": 50,
    }
    candidate.update(candidate_overrides)
    return {"candidates": [candidate]}

def test_catalog_price_replaces_the_model_price() -> None:
    lines = resolve_strategy_lines([_item()], market=_market())
    assert lines[0]["unit_cost"] == Decimal("4.50")
    assert lines[0]["source"] == "MARKETPLACE"

def test_unpriced_candidate_cannot_keep_a_marketplace_label() -> None:
    lines = resolve_strategy_lines([_item()], market=_market(unit_price=None))
    assert lines[0]["source"] == "AI_ESTIMATE"
    assert lines[0]["draft"].product_id is None
    assert lines[0]["unit_cost"] == Decimal("1.00")

def test_catalog_moq_beats_model_moq() -> None:
    lines = resolve_strategy_lines([_item(suggested_moq=2)], market=_market(moq=50))
    assert lines[0]["moq"] == 50
    assert lines[0]["qty"] == Decimal("50")

def test_model_moq_is_used_only_for_estimate_lines() -> None:
    lines = resolve_strategy_lines(
        [_item(product_id=None, suggested_moq=25, source_type="AI_ESTIMATE")],
        market=_market(),
    )
    assert lines[0]["moq"] == 25
    assert lines[0]["qty"] == Decimal("25")

def test_unknown_category_id_is_dropped() -> None:
    lines = resolve_strategy_lines([_item(category_id="507f1f77bcf86cd799439099")], market=_market())
    assert lines[0]["category_id"] is None

def test_known_category_id_is_kept() -> None:
    lines = resolve_strategy_lines([_item(category_id="cat-1")], market=_market())
    assert lines[0]["category_id"] == "cat-1"

def test_fake_product_id_gets_no_catalog_money() -> None:
    lines = resolve_strategy_lines([_item(product_id="FAKE-123")], market=_market())
    assert lines[0]["cand"] is None
    assert lines[0]["unit_cost"] == Decimal("1.00")
    assert lines[0]["moq"] is None

def test_rfq_uses_the_buyer_quantity() -> None:
    requirements = ProcurementRequirements(
        business_description="I need 500 cases of sparkling water",
        quantities=[{"product": "sparkling water", "quantity": 500, "unit": "case"}],
    )
    row = {"product_name": "Sparkling Water 1.5L", "moq": 50}
    assert _rfq_quantity(requirements, row) == 500

def test_rfq_quantity_is_raised_to_the_minimum_order() -> None:
    requirements = ProcurementRequirements(
        business_description="I need 5 cases of sparkling water",
        quantities=[{"product": "sparkling water", "quantity": 5, "unit": "case"}],
    )
    row = {"product_name": "Sparkling Water 1.5L", "moq": 50}
    assert _rfq_quantity(requirements, row) == 50

def test_rfq_quantity_falls_back_to_moq_when_buyer_gave_none() -> None:
    requirements = ProcurementRequirements(business_description="I need sparkling water")
    assert _rfq_quantity(requirements, {"product_name": "Water", "moq": 24}) == 24
    assert _rfq_quantity(requirements, {"product_name": "Water", "moq": None}) == 1

def test_rfq_quantity_prefers_the_matching_product_line() -> None:
    requirements = ProcurementRequirements(
        business_description="I need 100 cases of olive oil and 800 cases of water",
        quantities=[
            {"product": "olive oil", "quantity": 100, "unit": "case"},
            {"product": "water", "quantity": 800, "unit": "case"},
        ],
    )
    assert _rfq_quantity(requirements, {"product_name": "Bottled Water 1.5L", "moq": 10}) == 800
    assert _rfq_quantity(requirements, {"product_name": "Olive Oil 1L", "moq": 10}) == 100

class _FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def to_list(self, length: int | None = None) -> list[dict]:
        return self._rows

class _FakeCollection:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.queries: list[dict] = []

    def find(self, query: dict, projection: dict | None = None) -> _FakeCursor:
        self.queries.append(query)
        return _FakeCursor(self._rows)

def _patch_catalog(
    monkeypatch: pytest.MonkeyPatch,
    *,
    products: list[dict],
    verified_profiles: list[dict],
) -> None:
    from app.db import mongodb

    collections = {
        CollectionName.PRODUCTS: _FakeCollection(products),
        CollectionName.SUPPLIER_PROFILES: _FakeCollection(verified_profiles),
    }
    monkeypatch.setattr(
        mongodb.mongo_manager,
        "collection",
        lambda name: collections[name],
    )

def test_plan_conversion_keeps_active_verified_products(monkeypatch: pytest.MonkeyPatch) -> None:
    product_id = ObjectId()
    business_id = ObjectId()
    _patch_catalog(
        monkeypatch,
        products=[{"_id": product_id, "business_account_id": business_id}],
        verified_profiles=[{"business_account_id": business_id}],
    )
    keep = asyncio.run(
        BusinessPlannerService()._still_sourceable([{"product_id": product_id}])
    )
    assert keep == {str(product_id)}

def test_plan_conversion_drops_products_whose_supplier_lost_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_id = ObjectId()
    business_id = ObjectId()
    _patch_catalog(
        monkeypatch,
        products=[{"_id": product_id, "business_account_id": business_id}],
        verified_profiles=[],
    )
    keep = asyncio.run(
        BusinessPlannerService()._still_sourceable([{"product_id": product_id}])
    )
    assert keep == set()

def test_plan_conversion_drops_products_that_went_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_id = ObjectId()
    _patch_catalog(monkeypatch, products=[], verified_profiles=[])
    keep = asyncio.run(
        BusinessPlannerService()._still_sourceable([{"product_id": product_id}])
    )
    assert keep == set()
