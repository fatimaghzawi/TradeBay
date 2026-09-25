
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from app.modules.ai.provider import AIProviderError, StubAIProvider
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai_sourcing.recommendation import RecommendationEngine, relevance_label
from bson import ObjectId


def _extract(text: str):
    return asyncio.run(StubAIProvider().extract_procurement_requirements(text))

def test_stub_extracts_supermarket_beverages() -> None:
    text = (
        "I run a supermarket in Tyre. I sell food and household products. "
        "I am looking for beverage and cleaning-product suppliers. "
        "I usually buy in bulk every month and I need suppliers who can deliver to South Lebanon."
    )
    result = _extract(text)
    assert result.business_type == "supermarket"
    assert result.location is not None
    assert any("beverage" in p or "drink" in p for p in result.product_requirements)
    assert any("clean" in p for p in result.product_requirements)
    assert result.purchase_frequency == "monthly"
    assert "Bulk availability" in result.supplier_preferences
    assert result.missing_information

def test_stub_does_not_invent_empty_products_for_vague_text() -> None:
    result = _extract(
        "I need help finding good partners for my company somewhere nearby please."
    )
    assert result.product_requirements == []
    assert "product categories you need" in result.missing_information

def test_fallback_uses_stub_when_primary_fails() -> None:
    from app.modules.ai.provider import FallbackAIProvider

    class _Boom:
        async def extract_procurement_requirements(
            self, business_description: str, *, context: str | None = None
        ):
            raise AIProviderError("rate limited")

    text = (
        "I run a supermarket in Beirut looking for beverage suppliers every month."
    )
    provider = FallbackAIProvider(_Boom(), StubAIProvider())  # type: ignore[arg-type]
    result = asyncio.run(provider.extract_procurement_requirements(text))
    assert result.business_type == "supermarket"
    assert any("beverage" in p for p in result.product_requirements)

def test_relevance_label_bands() -> None:
    assert relevance_label(0.9) == "highly_relevant"
    assert relevance_label(0.5) == "relevant"
    assert relevance_label(0.2) == "partial"

def test_unverified_suppliers_are_hard_filtered() -> None:
    engine = RecommendationEngine()
    requirements = ProcurementRequirements(
        business_description="Need bottled water in bulk",
        product_requirements=["bottled water"],
        categories=["Beverages"],
    )
    product_id = ObjectId()
    business_id = ObjectId()
    products = [
        {
            "_id": product_id,
            "business_account_id": business_id,
            "category_id": ObjectId(),
            "name": "Bottled Water 1.5L",
            "description": "Still water",
            "status": "active",
            "moq": 50,
            "unit": "case",
            "origin": "Lebanon",
        }
    ]
    ranked = engine.rank(
        requirements=requirements,
        products=products,
        suppliers_by_business={str(business_id): {"_id": business_id, "name": "Aqua Co"}},
        inventories_by_product={
            str(product_id): {"available_quantity": Decimal("200"), "product_id": product_id}
        },
        prices_by_product={
            str(product_id): [
                {
                    "unit_price": Decimal("4.50"),
                    "currency": "USD",
                    "is_active": True,
                    "min_quantity": 50,
                }
            ]
        },
        categories_by_id={},
        verified_business_ids=set(),
        limit=10,
    )
    assert ranked == []

def test_verified_matching_product_is_recommended() -> None:
    engine = RecommendationEngine()
    requirements = ProcurementRequirements(
        business_description="Need bottled water in bulk",
        product_requirements=["bottled water"],
        categories=["Beverages"],
        supplier_preferences=["Bulk availability"],
    )
    product_id = ObjectId()
    business_id = ObjectId()
    cat_id = ObjectId()
    products = [
        {
            "_id": product_id,
            "business_account_id": business_id,
            "category_id": cat_id,
            "name": "Bottled Water 1.5L",
            "description": "Still mineral water cases",
            "status": "active",
            "moq": 50,
            "unit": "case",
            "origin": "Lebanon",
        }
    ]
    ranked = engine.rank(
        requirements=requirements,
        products=products,
        suppliers_by_business={str(business_id): {"_id": business_id, "name": "Aqua Co"}},
        inventories_by_product={
            str(product_id): {"available_quantity": Decimal("200"), "product_id": product_id}
        },
        prices_by_product={
            str(product_id): [
                {
                    "unit_price": Decimal("4.50"),
                    "currency": "USD",
                    "is_active": True,
                    "min_quantity": 50,
                }
            ]
        },
        categories_by_id={str(cat_id): {"_id": cat_id, "name": "Beverages"}},
        verified_business_ids={str(business_id)},
        limit=10,
    )
    assert len(ranked) == 1
    assert ranked[0].score > 0
    assert any("verified" in r.lower() for r in ranked[0].reasons)

def test_similar_recommendations_require_topic_overlap() -> None:
    engine = RecommendationEngine()
    requirements = ProcurementRequirements(
        business_description="I need rare volcanic glass beads for a boutique",
        product_requirements=["volcanic glass beads"],
        categories=["Specialty crafts"],
    )
    food_id = ObjectId()
    craft_id = ObjectId()
    business_id = ObjectId()
    food_cat = ObjectId()
    craft_cat = ObjectId()
    ranked = engine.rank(
        requirements=requirements,
        products=[
            {
                "_id": food_id,
                "business_account_id": business_id,
                "category_id": food_cat,
                "name": "Olive Oil Extra Virgin 5L",
                "description": "Cold pressed Lebanese oil for food service",
                "status": "active",
                "moq": 10,
                "unit": "can",
                "origin": "Lebanon",
            },
            {
                "_id": craft_id,
                "business_account_id": business_id,
                "category_id": craft_cat,
                "name": "Colored Glass Bead Assortment",
                "description": "Decorative glass beads for craft boutiques",
                "status": "active",
                "moq": 5,
                "unit": "pack",
                "origin": "Lebanon",
            },
        ],
        suppliers_by_business={str(business_id): {"_id": business_id, "name": "Levant Crafts"}},
        inventories_by_product={
            str(food_id): {"available_quantity": Decimal("80"), "product_id": food_id},
            str(craft_id): {"available_quantity": Decimal("40"), "product_id": craft_id},
        },
        prices_by_product={
            str(food_id): [
                {
                    "unit_price": Decimal("28"),
                    "currency": "USD",
                    "is_active": True,
                    "min_quantity": 10,
                }
            ],
            str(craft_id): [
                {
                    "unit_price": Decimal("12"),
                    "currency": "USD",
                    "is_active": True,
                    "min_quantity": 5,
                }
            ],
        },
        categories_by_id={
            str(food_cat): {"_id": food_cat, "name": "Grocery"},
            str(craft_cat): {"_id": craft_cat, "name": "Specialty crafts"},
        },
        verified_business_ids={str(business_id)},
        limit=10,
        min_results=4,
    )
    ids = {str(r.product["_id"]) for r in ranked}
    assert str(food_id) not in ids
    assert str(craft_id) in ids
    assert ranked[0].score > 0

    engine = RecommendationEngine()
    requirements = ProcurementRequirements(
        business_description="Need water",
        product_requirements=["water"],
    )
    product_id = ObjectId()
    business_id = ObjectId()
    ranked = engine.rank(
        requirements=requirements,
        products=[
            {
                "_id": product_id,
                "business_account_id": business_id,
                "category_id": ObjectId(),
                "name": "Water",
                "description": "",
                "status": "draft",
                "moq": 1,
                "unit": "unit",
            }
        ],
        suppliers_by_business={str(business_id): {"name": "X"}},
        inventories_by_product={},
        prices_by_product={},
        categories_by_id={},
        verified_business_ids={str(business_id)},
        limit=10,
    )
    assert ranked == []

def test_stub_rejects_too_short() -> None:
    with pytest.raises(AIProviderError):
        _extract("Hi")

def test_adaptive_answers_become_retriever_terms() -> None:
    from app.modules.business_planner.market import retrieval_requirements

    requirements = retrieval_requirements(
        {
            "business_goal": "grocery",
            "product_preferences": ["olive oil"],
            "category_hints": ["Grocery"],
            "adaptive": {"audience": "small shops", "margin_confirm": "20-30%"},
        }
    )
    assert "olive oil" in requirements.product_requirements
    assert "small shops" in requirements.product_requirements
    assert all("20-30%" not in term for term in requirements.product_requirements)

def test_stub_uses_supplied_context_for_catalog_vocabulary() -> None:
    context = (
        "Retrieved TradeBay catalog vocabulary:\n\n"
        "1. [product] Lebanese Olive Oil\n"
        "Product: Lebanese Olive Oil. Category: Grocery."
    )
    result = asyncio.run(
        StubAIProvider().extract_procurement_requirements(
            "Looking for olive oil suppliers for my shop in Beirut every month.",
            context=context,
        )
    )
    assert any("olive" in p.lower() for p in result.product_requirements)
    assert any("grocery" in c.lower() for c in result.categories)
