"""Platform Money integration — hold → release → payout + idempotent webhooks."""

from __future__ import annotations

from decimal import Decimal

import pytest
from bson import ObjectId
from app.core.exceptions import BadRequestError, ForbiddenError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.platform_money.constants import FundsState, PayableStatus, PayoutStatus
from app.modules.platform_money.service import (
    PlatformMoneyService,
    create_commission_and_payable_for_order,
)
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now


@pytest.mark.asyncio
async def test_platform_money_routing_lifecycle(app: object) -> None:
    buyer_id = ObjectId()
    supplier_id = ObjectId()
    order_id = ObjectId()
    payment_id = ObjectId()
    invoice_id = ObjectId()
    now = utc_now()
    user_id = str(ObjectId())

    await mongo_manager.collection(CollectionName.ORDERS).insert_one(
        {
            "_id": order_id,
            "order_number": f"PO-PM-{order_id}",
            "buyer_business_id": buyer_id,
            "supplier_business_id": supplier_id,
            "currency": "USD",
            "subtotal": to_decimal128(Decimal("1000.00")),
            "total": to_decimal128(Decimal("1000.00")),
            "status": "confirmed",
            "created_at": now,
            "updated_at": now,
        }
    )

    commission = await create_commission_and_payable_for_order(
        order={
            "_id": order_id,
            "supplier_business_id": supplier_id,
            "currency": "USD",
            "subtotal": to_decimal128(Decimal("1000.00")),
            "total": to_decimal128(Decimal("1000.00")),
        }
    )
    assert commission is not None
    assert Decimal(str(commission["commission_amount"].to_decimal())) == Decimal("50.00")

    # Idempotent commission
    again = await create_commission_and_payable_for_order(
        order={
            "_id": order_id,
            "supplier_business_id": supplier_id,
            "currency": "USD",
            "total": to_decimal128(Decimal("1000.00")),
            "subtotal": to_decimal128(Decimal("1000.00")),
        }
    )
    assert again is not None
    assert again["_id"] == commission["_id"]

    payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
        {"order_id": order_id}
    )
    assert payable is not None
    assert Decimal(str(payable["net_payable_amount"].to_decimal())) == Decimal("950.00")

    payment = {
        "_id": payment_id,
        "payment_reference": "PAY-TEST",
        "amount": to_decimal128(Decimal("1000.00")),
        "currency": "USD",
        "provider": "manual",
        "status": "completed",
    }
    invoice = {
        "_id": invoice_id,
        "order_id": order_id,
        "buyer_business_id": buyer_id,
        "currency": "USD",
        "total": to_decimal128(Decimal("1000.00")),
    }

    svc = PlatformMoneyService()
    await svc.on_buyer_payment_completed(payment=payment, invoice=invoice)

    held = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
        {"type": "buyer_payment", "order_id": order_id}
    )
    assert held is not None
    assert held["funds_state"] == FundsState.HELD

    fee_tx = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
        {"type": "platform_fee", "order_id": order_id}
    )
    assert fee_tx is not None

    # Duplicate payment handoff is idempotent
    await svc.on_buyer_payment_completed(payment=payment, invoice=invoice)
    count = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).count_documents(
        {"type": "buyer_payment", "order_id": order_id}
    )
    assert count == 1

    released = await svc.release_funds_for_order(order_id=str(order_id), user_id=user_id)
    assert released["status"] == "released"
    payout_id = released["payout_id"]
    assert payout_id

    payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
        {"_id": ObjectId(payout_id)}
    )
    assert payout is not None
    assert payout["status"] == PayoutStatus.PENDING

    platform = {"_id": ObjectId(), "type": "platform"}
    completed = await svc.process_payout(
        user_id=user_id, business=platform, payout_id=payout_id
    )
    assert completed["status"] == PayoutStatus.COMPLETED

    payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
        {"order_id": order_id}
    )
    assert payable is not None
    assert payable["status"] == PayableStatus.SETTLED

    # Invalid transition
    with pytest.raises(BadRequestError):
        await svc.fail_payout(business=platform, payout_id=payout_id, reason="too late")

    # Supplier isolation
    other_supplier = {"_id": ObjectId(), "type": "supplier"}
    with pytest.raises(ForbiddenError):
        await svc.get_payout(business=other_supplier, payout_id=payout_id)

    # Webhook idempotency
    evt = await svc.ingest_provider_event(
        provider="stripe",
        event_id="evt_dup_1",
        event_type="buyer_payment",
        amount="10.00",
        reference_type="payment",
        reference_id=str(ObjectId()),
    )
    evt2 = await svc.ingest_provider_event(
        provider="stripe",
        event_id="evt_dup_1",
        event_type="buyer_payment",
        amount="10.00",
        reference_type="payment",
        reference_id=str(ObjectId()),
    )
    assert evt["id"] == evt2["id"]

    summary = await svc.order_money_summary(
        business=platform, order_id=str(order_id)
    )
    assert summary["fee"] is not None
    assert summary["payable"]["status"] == PayableStatus.SETTLED
    assert summary["payout"]["status"] == PayoutStatus.COMPLETED
    assert len(summary["transactions"]) >= 3

    overview = await svc.admin_overview(business=platform)
    assert overview["currency"] == "USD"
    assert "held_amount" in overview
    assert "pending_payouts_count" in overview
    assert isinstance(overview["recent_transactions"], list)

    with pytest.raises(ForbiddenError):
        await svc.admin_overview(business={"_id": supplier_id, "type": "supplier"})
