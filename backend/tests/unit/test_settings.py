
from __future__ import annotations

from decimal import Decimal

import pytest
from app.modules.settings.schemas import UpdatePlatformSettingsRequest
from app.modules.settings.tax import compute_tax
from pydantic import ValidationError


def test_tax_calculation() -> None:
    result = compute_tax(subtotal="1000.00", discount="50.00", rate="0.11")
    assert result["taxable_amount"] == Decimal("950.00")
    assert result["tax_amount"] == Decimal("104.50")
    assert result["total"] == Decimal("1054.50")

def test_tax_rate_out_of_range() -> None:
    with pytest.raises(ValueError):
        compute_tax(subtotal="100", rate="1.5")

def test_platform_rejects_float_commission() -> None:
    with pytest.raises(ValidationError):
        UpdatePlatformSettingsRequest(commission_rate=0.05)  # type: ignore[arg-type]
