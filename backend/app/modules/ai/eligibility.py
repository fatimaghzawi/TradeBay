
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.modules.ai.requirements import ProcurementRequirements
from app.modules.catalog.constants import ProductStatus


@dataclass
class EligibilityDecision:
    product_id: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    moq_compatible: bool | None = None
    inventory_compatible: bool | None = None

def _quantity(requirements: ProcurementRequirements) -> float | None:
    for qty in requirements.quantities:
        if qty.quantity is not None and qty.quantity > 0:
            return float(qty.quantity)
    return None

def _available(inventory: dict[str, Any] | None) -> Decimal | None:
    if inventory is None or inventory.get("available_quantity") is None:
        return None
    try:
        return Decimal(str(inventory.get("available_quantity")))
    except Exception:
        return None

def decide_eligibility(
    *,
    product: dict[str, Any],
    inventory: dict[str, Any] | None,
    verified: bool,
    requirements: ProcurementRequirements,
) -> EligibilityDecision:
    product_id = str(product.get("_id") or product.get("id") or "")
    reasons: list[str] = []
    status = str(product.get("status") or "").lower()
    if status != str(ProductStatus.ACTIVE).lower() and status != "active":
        reasons.append("inactive")
    if not verified:
        reasons.append("unverified_supplier")

    requested = _quantity(requirements)
    moq_compatible: bool | None = None
    inventory_compatible: bool | None = None
    if requested is not None:
        moq_raw = product.get("moq")
        try:
            moq = int(moq_raw) if moq_raw is not None else 1
        except (TypeError, ValueError):
            moq = 1
        moq_compatible = requested >= moq
        if not moq_compatible:
            reasons.append("below_moq")
        available = _available(inventory)
        if available is not None:
            inventory_compatible = available >= Decimal(str(requested))
            if not inventory_compatible:
                reasons.append("insufficient_stock")

    hard = {"inactive", "unverified_supplier", "insufficient_stock"}
    eligible = not any(reason in hard for reason in reasons)
    return EligibilityDecision(
        product_id=product_id,
        eligible=eligible,
        reasons=reasons,
        moq_compatible=moq_compatible,
        inventory_compatible=inventory_compatible,
    )
