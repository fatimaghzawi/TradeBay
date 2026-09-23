"""System Settings integration — admin RBAC, updates, numbering, immutability."""

from __future__ import annotations

from decimal import Decimal

import pytest
from bson import ObjectId
from app.core.exceptions import ForbiddenError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.settings.constants import SINGLETON_KEY
from app.modules.settings.numbering import allocate_document_number
from app.modules.settings.service import SettingsService
from app.modules.platform_money.service import create_commission_and_payable_for_order
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now


@pytest.mark.asyncio
async def test_settings_admin_update_and_history(app: object) -> None:
    svc = SettingsService()
    platform = {"_id": ObjectId(), "type": "platform"}
    buyer = {"_id": ObjectId(), "type": "buyer"}
    user_id = str(ObjectId())

    with pytest.raises(ForbiddenError):
        await svc.get_all(business=buyer)

    all_settings = await svc.get_all(business=platform)
    assert all_settings["platform"] is not None
    assert all_settings["business"] is not None

    old_rate = all_settings["platform"]["commission_rate"]

    # Snapshot commission on an order before rate change
    order_id = ObjectId()
    supplier_id = ObjectId()
    await create_commission_and_payable_for_order(
        order={
            "_id": order_id,
            "supplier_business_id": supplier_id,
            "currency": "USD",
            "subtotal": to_decimal128(Decimal("1000.00")),
            "total": to_decimal128(Decimal("1000.00")),
        }
    )
    commission = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
        {"order_id": order_id}
    )
    assert commission is not None
    frozen_rate = commission["rate"]

    updated = await svc.update_platform(
        user_id=user_id,
        business=platform,
        payload={"commission_rate": "0.06", "platform_name": "TradeBay Admin"},
    )
    assert updated["commission_rate"] == "0.06"
    assert updated["platform_name"] == "TradeBay Admin"

    # Historical commission unchanged
    commission = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
        {"order_id": order_id}
    )
    assert commission is not None
    assert commission["rate"] == frozen_rate

    # Tax rate change creates new active row; old invoices would keep their snapshot
    tax_before = await mongo_manager.collection(CollectionName.TAX_SETTINGS).find_one(
        {"is_active": True}
    )
    assert tax_before is not None
    old_tax_id = tax_before["_id"]
    old_tax_rate = tax_before["rate"]

    new_tax = await svc.update_tax(
        user_id=user_id,
        business=platform,
        payload={"rate": "0.15", "name": "VAT"},
    )
    assert new_tax["rate"] == "0.15"
    assert new_tax["is_active"] is True

    closed = await mongo_manager.collection(CollectionName.TAX_SETTINGS).find_one(
        {"_id": old_tax_id}
    )
    assert closed is not None
    assert closed["is_active"] is False
    assert closed["rate"] == old_tax_rate

    biz = await svc.update_business(
        user_id=user_id,
        business=platform,
        payload={"invoice_prefix": "TB-INV", "business_name": "TradeBay SAL"},
    )
    assert biz["business_name"] == "TradeBay SAL"

    # Atomic numbering uniqueness
    n1 = await allocate_document_number(kind="invoice", prefix="TB-TEST")
    n2 = await allocate_document_number(kind="invoice", prefix="TB-TEST")
    assert n1 != n2
    assert n1.startswith("TB-TEST-")

    # Restore commission rate so other tests aren't polluted if shared DB
    await svc.update_platform(
        user_id=user_id,
        business=platform,
        payload={"commission_rate": old_rate or "0.05"},
    )


@pytest.mark.asyncio
async def test_settings_rejects_secret_like_provider(app: object) -> None:
    svc = SettingsService()
    platform = {"_id": ObjectId(), "type": "platform"}
    with pytest.raises(Exception):
        await svc.update_platform(
            user_id=str(ObjectId()),
            business=platform,
            payload={"payment_provider": "stripe_secret_key"},
        )
