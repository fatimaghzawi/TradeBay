
from __future__ import annotations

from typing import Any

from app.modules.ai.requirements import ProcurementRequirements

EVAL_CASES: list[dict[str, Any]] = [
    {
        "id": "sparkling_water_beirut",
        "prompt": "I need 500 cases of sparkling water for Beirut supermarkets.",
        "expect_any_product": ["sparkling", "water", "beverage"],
        "expect_location": "beirut",
        "expect_quantity": 500,
        "expect_unit_any": ["case", "cases"],
    },
    {
        "id": "cleaning_bulk",
        "prompt": "I want affordable cleaning products in bulk.",
        "expect_any_product": ["clean"],
        "expect_missing_any": ["quantity", "location", "budget"],
    },
    {
        "id": "cafe_open",
        "prompt": "I need products for opening a small café.",
        "expect_business_any": ["hospitality", "cafe", "café"],
        "expect_missing_any": ["quantity", "budget"],
    },
    {
        "id": "grocery_budget",
        "prompt": "I have $10,000 and want to source products for a grocery store.",
        "expect_business_any": ["supermarket", "grocery", "retail"],
        "expect_budget_hint": True,
    },
    {
        "id": "similar_water",
        "prompt": "I need something similar to mineral water but cheaper.",
        "expect_any_product": ["water", "mineral", "beverage"],
    },
    {
        "id": "unknown_name",
        "prompt": "I need 200 units but I don't know the exact product name.",
        "expect_quantity": 200,
        "expect_missing_any": ["product"],
    },
]

def fact_failures(case: dict[str, Any], result: ProcurementRequirements) -> list[str]:
    failures: list[str] = []
    products = " ".join(result.product_requirements + result.categories).lower()
    description = (result.business_description or "").lower()
    business = (result.business_type or "").lower()
    location = (result.location or "").lower()
    missing = " ".join(result.missing_information).lower()
    budget = f"{result.budget_range or ''} {description}"

    expected_products = case.get("expect_any_product") or []
    if expected_products and not any(token in products or token in description for token in expected_products):
        failures.append("product")

    expected_business = case.get("expect_business_any") or []
    if expected_business and not any(token in business or token in description for token in expected_business):
        failures.append("business")

    if case.get("expect_location") and case["expect_location"] not in location:
        failures.append("location")

    expected_qty = case.get("expect_quantity")
    if expected_qty is not None and not any(qty.quantity == expected_qty for qty in result.quantities):
        failures.append("quantity")

    expected_units = case.get("expect_unit_any") or []
    if expected_units and not any(
        qty.unit and any(unit in qty.unit.lower() for unit in expected_units) for qty in result.quantities
    ):
        failures.append("unit")

    expected_missing = case.get("expect_missing_any") or []
    if expected_missing and not any(token in missing for token in expected_missing):
        failures.append("missing")

    if case.get("expect_budget_hint") and not any(ch.isdigit() for ch in budget):
        failures.append("budget")

    return failures
