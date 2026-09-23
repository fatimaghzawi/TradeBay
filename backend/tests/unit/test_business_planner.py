"""Unit tests for Business Planner Decimal finance."""

from __future__ import annotations

from decimal import Decimal

from app.modules.business_planner.finance import (
    compute_line,
    compute_plan_finance,
    scale_quantities_to_budget,
)
from app.modules.business_planner.planner_ai import (
    adaptive_questions_heuristic,
    stub_generate_plan_draft,
)
from app.modules.business_planner.schemas import AIPlanDraft


def test_compute_line_margin() -> None:
    line = compute_line(quantity=10, unit_cost="5.00", selling_price="8.00")
    assert line.inventory_cost == Decimal("50.00")
    assert line.revenue == Decimal("80.00")
    assert line.gross_profit == Decimal("30.00")
    assert line.margin_pct == Decimal("37.50")


def test_compute_plan_finance_scales_to_budget() -> None:
    result = compute_plan_finance(
        line_inputs=[
            {"quantity": 100, "unit_cost": "50", "selling_price": "80"},
            {"quantity": 100, "unit_cost": "40", "selling_price": "70"},
        ],
        available_budget=Decimal("3000"),
        inventory_budget_cap=Decimal("2000"),
        auto_scale=True,
    )
    assert result.total_inventory_cost <= Decimal("2000.00")
    assert result.adjustments
    assert result.gross_margin_pct >= Decimal("0")


def test_scale_quantities_never_uses_float() -> None:
    scaled = scale_quantities_to_budget(
        [(Decimal("100"), Decimal("30"), Decimal("50"))],
        inventory_budget=Decimal("900"),
    )
    assert scaled[0][0] == Decimal("30")
    assert isinstance(scaled[0][0], Decimal)


def test_adaptive_questions_for_fashion() -> None:
    qs = adaptive_questions_heuristic(
        {"business_goal": "Fashion", "adaptive": {}, "desired_margin": "20-30%"}
    )
    ids = {q.id for q in qs}
    assert "audience" in ids or "price_positioning" in ids


def test_stub_plan_uses_marketplace_candidates_only() -> None:
    market = {
        "candidates": [
            {
                "product_id": "507f1f77bcf86cd799439011",
                "product_name": "Wireless Earbuds",
                "category_id": "507f1f77bcf86cd799439012",
                "unit_price": "12.50",
                "moq": 20,
                "unit": "unit",
                "supplier_business_id": "507f1f77bcf86cd799439013",
                "supplier_name": "Audio Co",
            }
        ],
        "categories": [{"name": "Electronics", "product_count": 1}],
        "insufficient_data": False,
    }
    prefs = {
        "business_goal": "Electronics",
        "location": "Tyre",
        "budget_range": "3000_5000",
        "desired_margin": "30-40%",
        "risk_preference": "Balanced",
        "experience": "Beginner",
    }
    draft = stub_generate_plan_draft(preferences=prefs, market=market)
    validated = AIPlanDraft.model_validate(draft.model_dump())
    assert validated.product_strategy
    assert validated.product_strategy[0].product_id == "507f1f77bcf86cd799439011"
    assert validated.product_strategy[0].source_type == "MARKETPLACE"


def test_stub_plan_without_catalog_labels_ai_estimate() -> None:
    draft = stub_generate_plan_draft(
        preferences={
            "business_goal": "Retail Store",
            "location": "Beirut",
            "budget_range": "1000_3000",
            "unsure_goal": False,
        },
        market={"candidates": [], "insufficient_data": True, "categories": []},
    )
    assert draft.product_strategy[0].source_type == "AI_ESTIMATE"
    assert draft.product_strategy[0].product_id is None
