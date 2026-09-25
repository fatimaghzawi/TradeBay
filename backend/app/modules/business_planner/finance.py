
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.modules.business_planner.constants import DEFAULT_BUDGET_SPLIT

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")

def money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))

def quantize(value: Decimal) -> Decimal:
    return money(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

@dataclass(frozen=True)
class LineFinance:
    quantity: Decimal
    unit_cost: Decimal
    selling_price: Decimal
    inventory_cost: Decimal
    revenue: Decimal
    gross_profit: Decimal
    margin_ratio: Decimal
    margin_pct: Decimal

@dataclass(frozen=True)
class PlanFinance:
    lines: list[LineFinance]
    total_inventory_cost: Decimal
    total_revenue: Decimal
    total_gross_profit: Decimal
    gross_margin_pct: Decimal
    budget_allocation: dict[str, Any]
    financial_projection: dict[str, Any]
    over_budget: bool
    adjustments: list[str]

def compute_line(
    *,
    quantity: Decimal | int | str,
    unit_cost: Decimal | int | str,
    selling_price: Decimal | int | str,
) -> LineFinance:
    qty = money(quantity)
    cost = money(unit_cost)
    sell = money(selling_price)
    inventory_cost = quantize(qty * cost)
    revenue = quantize(qty * sell)
    gross_profit = quantize(revenue - inventory_cost)
    if revenue > ZERO:
        margin_ratio = (gross_profit / revenue).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        margin_ratio = ZERO
    margin_pct = quantize(margin_ratio * HUNDRED)
    return LineFinance(
        quantity=qty,
        unit_cost=quantize(cost),
        selling_price=quantize(sell),
        inventory_cost=inventory_cost,
        revenue=revenue,
        gross_profit=gross_profit,
        margin_ratio=margin_ratio,
        margin_pct=margin_pct,
    )

def _split_amounts(total: Decimal, weights: dict[str, Decimal]) -> dict[str, Decimal]:
    if total <= ZERO:
        return {k: ZERO for k in weights}
    weight_sum = sum(weights.values(), ZERO)
    if weight_sum <= ZERO:
        return {k: ZERO for k in weights}
    allocated: dict[str, Decimal] = {}
    running = ZERO
    keys = list(weights.keys())
    for i, key in enumerate(keys):
        if i == len(keys) - 1:
            allocated[key] = quantize(total - running)
        else:
            share = quantize(total * (weights[key] / weight_sum))
            allocated[key] = share
            running += share
    return allocated

def allocate_startup_budget(
    *,
    available_budget: Decimal,
    inventory_investment: Decimal,
    inventory_budget_cap: Decimal | None = None,
) -> dict[str, Any]:
    available = quantize(available_budget)
    inventory = quantize(inventory_investment)
    if inventory_budget_cap is not None:
        inventory = min(inventory, quantize(inventory_budget_cap))

    weights = {k: money(v) for k, v in DEFAULT_BUDGET_SPLIT.items() if k != "inventory"}
    remainder = max(available - inventory, ZERO)
    other = _split_amounts(remainder, weights)

    allocation = {
        "inventory": str(inventory),
        "equipment": str(other.get("equipment", ZERO)),
        "rent": str(other.get("rent", ZERO)),
        "marketing": str(other.get("marketing", ZERO)),
        "logistics": str(other.get("logistics", ZERO)),
        "operations": str(other.get("operations", ZERO)),
        "reserve": str(other.get("reserve", ZERO)),
        "working_capital": str(other.get("working_capital", ZERO)),
        "total_required": str(available),
        "available_budget": str(available),
        "label": "AI estimate — startup allocation based on your budget and planned inventory.",
    }
    return allocation

def estimate_break_even_units(
    *,
    monthly_operating_expenses: Decimal,
    unit_gross_profit: Decimal,
) -> Decimal | None:
    profit = money(unit_gross_profit)
    opex = money(monthly_operating_expenses)
    if profit <= ZERO:
        return None
    return (opex / profit).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

def build_financial_projection(
    *,
    inventory_cost: Decimal,
    expected_revenue: Decimal,
    gross_profit: Decimal,
    gross_margin_pct: Decimal,
    available_budget: Decimal,
    budget_allocation: dict[str, Any],
    target_monthly_income: Decimal | None = None,
) -> dict[str, Any]:
    monthly_opex = (
        money(budget_allocation.get("rent"))
        + money(budget_allocation.get("operations"))
        + money(budget_allocation.get("marketing"))
        + money(budget_allocation.get("logistics"))
    )
                                                                              
    monthly_opex = quantize(monthly_opex / Decimal("3")) if monthly_opex > ZERO else ZERO
    expected_monthly_sales = quantize(expected_revenue)                                       
    operating_profit = quantize(gross_profit - monthly_opex)
    cash_reserve = money(budget_allocation.get("reserve"))
    return {
        "initial_investment": str(quantize(available_budget)),
        "inventory_investment": str(quantize(inventory_cost)),
        "monthly_operating_expenses": str(monthly_opex),
        "expected_monthly_sales": str(expected_monthly_sales),
        "gross_revenue": str(quantize(expected_revenue)),
        "cost_of_goods": str(quantize(inventory_cost)),
        "gross_profit": str(quantize(gross_profit)),
        "gross_margin_pct": str(quantize(gross_margin_pct)),
        "estimated_operating_profit": str(operating_profit),
        "break_even_units": None,
        "cash_reserve": str(quantize(cash_reserve)),
        "target_monthly_income": str(quantize(target_monthly_income)) if target_monthly_income else None,
        "label": (
            "AI estimate — based on your selected budget, target margin, and planned inventory. "
            "Not a guarantee of profitability or demand."
        ),
    }

def suggest_budget_adjustments(
    *,
    available_budget: Decimal,
    inventory_cost: Decimal,
    line_count: int,
) -> list[str]:
    tips: list[str] = []
    if inventory_cost > available_budget:
        tips.append("Reduce initial SKU count to fit your available capital.")
        tips.append("Start online to defer rent and fit-out costs.")
        tips.append("Prefer products with lower MOQ to reduce first-order size.")
        tips.append("Focus on fast-moving, essential products first.")
        tips.append("Choose lower-cost product categories within your interest area.")
        tips.append("Delay non-essential equipment and marketing spend.")
    elif inventory_cost > available_budget * money("0.55"):
        tips.append("Inventory is a large share of capital — keep an emergency reserve.")
    if line_count > 8:
        tips.append("Narrow the assortment for your first order cycle.")
    return tips

def scale_quantities_to_budget(
    lines: list[tuple[Decimal, Decimal, Decimal]],
    *,
    inventory_budget: Decimal,
) -> list[tuple[Decimal, Decimal, Decimal]]:
    budget = quantize(inventory_budget)
    if budget <= ZERO or not lines:
        return [(ZERO, c, s) for _, c, s in lines]
    current = sum((money(q) * money(c) for q, c, _ in lines), ZERO)
    if current <= ZERO or current <= budget:
        return [(money(q), money(c), money(s)) for q, c, s in lines]
    ratio = budget / current
    scaled: list[tuple[Decimal, Decimal, Decimal]] = []
    for qty, cost, sell in lines:
        new_qty = (money(qty) * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if new_qty < Decimal("1") and money(qty) >= Decimal("1"):
            new_qty = Decimal("1")
        scaled.append((new_qty, money(cost), money(sell)))
                                                         
    while scaled and sum((q * c for q, c, _ in scaled), ZERO) > budget:
        if len(scaled) == 1:
            _q, c, s = scaled[0]
            max_q = (budget / c).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if c > ZERO else ZERO
            scaled[0] = (max(max_q, ZERO), c, s)
            break
        scaled.pop()
    return scaled

def compute_plan_finance(
    *,
    line_inputs: list[dict[str, Any]],
    available_budget: Decimal,
    inventory_budget_cap: Decimal | None = None,
    target_monthly_income: Decimal | None = None,
    auto_scale: bool = True,
) -> PlanFinance:
    raw_lines: list[tuple[Decimal, Decimal, Decimal]] = [
        (money(row["quantity"]), money(row["unit_cost"]), money(row["selling_price"]))
        for row in line_inputs
    ]
    inv_cap = inventory_budget_cap
    if inv_cap is None:
        inv_cap = quantize(available_budget * money(DEFAULT_BUDGET_SPLIT["inventory"]))

    adjustments: list[str] = []
    working = list(raw_lines)
    inventory_cost_preview = sum((q * c for q, c, _ in working), ZERO)
    if auto_scale and inventory_cost_preview > inv_cap:
        adjustments = suggest_budget_adjustments(
            available_budget=available_budget,
            inventory_cost=inventory_cost_preview,
            line_count=len(working),
        )
        working = scale_quantities_to_budget(working, inventory_budget=inv_cap)

    lines = [
        compute_line(quantity=q, unit_cost=c, selling_price=s) for q, c, s in working if q > ZERO
    ]
    total_inventory = quantize(sum((ln.inventory_cost for ln in lines), ZERO))
    total_revenue = quantize(sum((ln.revenue for ln in lines), ZERO))
    total_profit = quantize(sum((ln.gross_profit for ln in lines), ZERO))
    margin_pct = (
        quantize((total_profit / total_revenue) * HUNDRED) if total_revenue > ZERO else ZERO
    )
    allocation = allocate_startup_budget(
        available_budget=available_budget,
        inventory_investment=total_inventory,
        inventory_budget_cap=inv_cap,
    )
    over = total_inventory > available_budget
    if over and not adjustments:
        adjustments = suggest_budget_adjustments(
            available_budget=available_budget,
            inventory_cost=total_inventory,
            line_count=len(lines),
        )
    projection = build_financial_projection(
        inventory_cost=total_inventory,
        expected_revenue=total_revenue,
        gross_profit=total_profit,
        gross_margin_pct=margin_pct,
        available_budget=available_budget,
        budget_allocation=allocation,
        target_monthly_income=target_monthly_income,
    )
    if lines:
        avg_profit = quantize(
            sum((ln.gross_profit for ln in lines), ZERO) / Decimal(len(lines))
        )
        be = estimate_break_even_units(
            monthly_operating_expenses=money(projection["monthly_operating_expenses"]),
            unit_gross_profit=avg_profit,
        )
        projection["break_even_units"] = str(be) if be is not None else None

    return PlanFinance(
        lines=lines,
        total_inventory_cost=total_inventory,
        total_revenue=total_revenue,
        total_gross_profit=total_profit,
        gross_margin_pct=margin_pct,
        budget_allocation=allocation,
        financial_projection=projection,
        over_budget=over,
        adjustments=adjustments,
    )
