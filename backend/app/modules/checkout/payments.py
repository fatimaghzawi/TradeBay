
from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.db.transactions import run_in_transaction
from app.modules.checkout.constants import RECEIPT_PREFIX, CheckoutStatus
from app.modules.checkout.gateway import (
    IntentResult,
    get_payment_gateway,
    to_minor_units,
    verify_stripe_signature,
)
from app.modules.finance.constants import (
    InvoiceStatus,
    LedgerDirection,
    LedgerSourceType,
    LedgerTransactionType,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.platform_money.commission import as_decimal, money
from app.modules.procurement.constants import ORDER_TRANSITIONS, OrderStatus, assert_transition
from app.modules.settings.numbering import allocate_seeded_number
from app.shared.repositories.base import MongoSession
from app.shared.services.audit import AuditService
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

logger = get_logger(__name__)

class PaymentAmountMismatchError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "PAYMENT_AMOUNT_MISMATCH",
            "The provider reported a different amount than this checkout. TradeBay was alerted.",
            status_code=409,
        )

def _col(name: CollectionName) -> Any:
    return mongo_manager.collection(name)

async def _notify(**kwargs: Any) -> None:
    try:
        from app.modules.trust.notify import notify

        await notify(**kwargs)
    except Exception:
        logger.warning("checkout_notify_failed", type=kwargs.get("type"))

async def _audit(action: str, *, resource_type: str, resource_id: Any, business_id: Any, user_id: str | None, metadata: dict[str, Any]) -> None:
    try:
        await AuditService().log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            business_account_id=str(business_id) if business_id else None,
            user_id=user_id,
            actor_id=user_id,
            ip_address=None,
            metadata=metadata,
        )
    except Exception:
        logger.warning("checkout_audit_failed", action=action)

                                                                                      

async def cancel_order_in_session(
    order: dict[str, Any], *, user_id: str | None, reason: str, session: MongoSession
) -> bool:
    from app.modules.catalog.exceptions import InsufficientReservedError
    from app.modules.catalog.service import CatalogService
    from app.modules.finance.service import void_invoice_in_session
    from app.modules.platform_money.service import cancel_commission_in_session

    if order.get("status") == OrderStatus.CANCELLED:
        return False
    if str(order.get("payment_status") or "unpaid") not in {"unpaid", ""}:
        raise ConflictError("This order is already paid. Open a dispute so TradeBay can arrange a refund.")
    assert_transition(ORDER_TRANSITIONS, str(order["status"]), OrderStatus.CANCELLED)
    now = utc_now()
    history_entry = {
        "status": OrderStatus.CANCELLED,
        "changed_by_user_id": parse_object_id(user_id) if user_id else None,
        "note": reason,
        "changed_at": now,
    }
    result = await _col(CollectionName.ORDERS).update_one(
        {"_id": order["_id"], "status": order["status"]},
        {
            "$set": {"status": OrderStatus.CANCELLED, "cancelled_at": now, "rejection_reason": reason, "updated_at": now},
            "$push": {"status_history": history_entry},
        },
        session=session,
    )
    if not result.modified_count:
        raise ConflictError("This order was just updated. Refresh to see its status.")

    if order.get("stock_reservation_status") == "reserved":
        catalog = CatalogService()
        items = await _col(CollectionName.ORDER_ITEMS).find({"order_id": order["_id"]}, session=session).to_list(500)
        for item in items:
            if not item.get("product_id"):
                continue
            try:
                await catalog.release_stock(
                    str(item["product_id"]),
                    business_id=str(order["supplier_business_id"]),
                    user_id=user_id or str(order["buyer_business_id"]),
                    quantity=as_decimal(item["quantity"]),
                    reference_type="order",
                    reference_id=str(order["_id"]),
                    reason=f"Order {order.get('order_number')} cancelled",
                    session=session,
                )
            except InsufficientReservedError:
                continue
        await _col(CollectionName.ORDERS).update_one(
            {"_id": order["_id"]}, {"$set": {"stock_reservation_status": "released"}}, session=session
        )

    invoice = await _col(CollectionName.CUSTOMER_INVOICES).find_one({"order_id": order["_id"]}, session=session)
    if invoice is not None:
        await void_invoice_in_session(invoice, user_id=user_id, reason=reason, session=session)
    await cancel_commission_in_session(order_id=order["_id"], session=session)
    return True

async def remove_allocation_in_session(
    payment: dict[str, Any], *, invoice_id: ObjectId, reason: str, session: MongoSession
) -> dict[str, Any]:
    if payment.get("status") not in {PaymentStatus.PENDING, PaymentStatus.FAILED}:
        raise ConflictError("Only an unpaid payment can change")
    allocations = list(payment.get("allocations") or [])
    removed = [a for a in allocations if a.get("invoice_id") == invoice_id]
    if not removed:
        return payment
    remaining = [a for a in allocations if a.get("invoice_id") != invoice_id]
    new_amount = money(sum((as_decimal(a.get("allocated_amount")) for a in remaining), Decimal("0")))
    now = utc_now()
    update: dict[str, Any] = {
        "$set": {"allocations": remaining, "amount": to_decimal128(new_amount), "updated_at": now},
        "$push": {
            "adjustments": {
                "type": "allocation_removed",
                "invoice_id": invoice_id,
                "amount": removed[0].get("allocated_amount"),
                "previous_amount": payment.get("amount"),
                "reason": reason,
                "at": now,
            }
        },
    }
    if not remaining:
        update["$set"]["status"] = PaymentStatus.CANCELLED
        update["$set"]["cancelled_at"] = now
    result = await _col(CollectionName.PAYMENTS).update_one(
        {"_id": payment["_id"], "status": payment["status"]}, update, session=session
    )
    if not result.modified_count:
        raise ConflictError("The payment changed while cancelling. Refresh and try again.")
    return await _col(CollectionName.PAYMENTS).find_one({"_id": payment["_id"]}, session=session)

async def cancel_checkout_in_session(
    checkout: dict[str, Any], *, user_id: str | None, reason: str, session: MongoSession
) -> bool:
    fresh = await _col(CollectionName.CHECKOUTS).find_one({"_id": checkout["_id"]}, session=session)
    if fresh is None:
        raise NotFoundError("Checkout not found")
    if fresh["status"] == CheckoutStatus.CANCELLED:
        return False
    if fresh["status"] != CheckoutStatus.AWAITING_PAYMENT:
        raise ConflictError("A paid checkout can't be cancelled. Open a dispute on the order instead.")
    orders = await _col(CollectionName.ORDERS).find({"checkout_id": fresh["_id"]}, session=session).to_list(100)
    for order in orders:
        if order["status"] not in {OrderStatus.AWAITING_PAYMENT, OrderStatus.PENDING, OrderStatus.CANCELLED}:
            raise ConflictError(
                f"{order.get('order_number')} is already confirmed by the supplier. Cancel the remaining orders one by one."
            )
    for order in orders:
        await cancel_order_in_session(order, user_id=user_id, reason=reason, session=session)
    now = utc_now()
    if fresh.get("payment_id"):
        await _col(CollectionName.PAYMENTS).update_one(
            {"_id": fresh["payment_id"], "status": {"$in": [PaymentStatus.PENDING, PaymentStatus.FAILED]}},
            {"$set": {"status": PaymentStatus.CANCELLED, "cancelled_at": now, "updated_at": now}},
            session=session,
        )
    await _col(CollectionName.CHECKOUTS).update_one(
        {"_id": fresh["_id"], "status": CheckoutStatus.AWAITING_PAYMENT},
        {
            "$set": {"status": CheckoutStatus.CANCELLED, "cancelled_at": now, "updated_at": now},
            "$push": {"status_history": {"status": CheckoutStatus.CANCELLED, "note": reason, "changed_at": now}},
        },
        session=session,
    )
    return True

                                                                                     

async def apply_payment_success(
    *,
    payment_id: ObjectId,
    provider_event_id: str | None = None,
    amount_minor: int | None = None,
    currency: str | None = None,
    actor_user_id: str | None = None,
    note: str | None = None,
) -> tuple[dict[str, Any], bool]:
    from app.modules.finance.service import (
        FinanceService,
        _insert_ledger_row,
        promote_draft_invoice_in_session,
    )
    from app.modules.platform_money.service import record_checkout_payment_in_session

    async def _work(session: MongoSession) -> tuple[dict[str, Any], bool]:
        pay = await _col(CollectionName.PAYMENTS).find_one({"_id": payment_id}, session=session)
        if pay is None:
            raise NotFoundError("Payment not found")
        if pay["status"] == PaymentStatus.COMPLETED:
            return pay, False
        if pay["status"] not in {PaymentStatus.PENDING, PaymentStatus.FAILED}:
            raise ConflictError("This payment was cancelled and can't be completed")
        if amount_minor is not None:
            expected = to_minor_units(money(pay["amount"]))
            if amount_minor != expected or (currency and currency.upper() != str(pay.get("currency")).upper()):
                raise PaymentAmountMismatchError()
        allocations = list(pay.get("allocations") or [])
        allocated = money(sum((as_decimal(a.get("allocated_amount")) for a in allocations), Decimal("0")))
        if allocated != money(pay["amount"]) or not allocations:
            raise ConflictError("Payment allocations don't add up to the payment amount")

        now = utc_now()
        receipt = await allocate_seeded_number(RECEIPT_PREFIX, CollectionName.PAYMENTS, "receipt_number", session=session)
        patch: dict[str, Any] = {
            "status": PaymentStatus.COMPLETED,
            "paid_at": now,
            "receipt_number": receipt,
            "receipt_issued_at": now,
            "confirmed_by_user_id": parse_object_id(actor_user_id) if actor_user_id else None,
            "confirmation_note": note,
            "updated_at": now,
        }
        if provider_event_id:
            patch["provider_event_id"] = provider_event_id
        result = await _col(CollectionName.PAYMENTS).update_one(
            {"_id": pay["_id"], "status": pay["status"]},
            {"$set": patch, "$unset": {"failure_code": "", "failure_message": ""}},
            session=session,
        )
        if not result.modified_count:
            return await _col(CollectionName.PAYMENTS).find_one({"_id": pay["_id"]}, session=session), False
        pay = {**pay, **patch}

        invoices: dict[ObjectId, dict[str, Any]] = {}
        for alloc in allocations:
            inv = await _col(CollectionName.CUSTOMER_INVOICES).find_one({"_id": alloc["invoice_id"]}, session=session)
            if inv is None or inv.get("status") == InvoiceStatus.VOID:
                raise ConflictError("An invoice on this payment is no longer payable")
            invoices[inv["_id"]] = await promote_draft_invoice_in_session(inv, user_id=actor_user_id, session=session)

        for alloc in allocations:
            inv = invoices[alloc["invoice_id"]]
            await _insert_ledger_row(
                business_account_id=pay["payer_business_id"],
                amount=as_decimal(alloc["allocated_amount"]),
                currency=pay.get("currency") or "USD",
                source_type=LedgerSourceType.PAYMENT,
                source_id=pay["_id"],
                transaction_type=LedgerTransactionType.PAYMENT_RECEIVED,
                direction=LedgerDirection.CREDIT,
                description=f"Payment {pay.get('payment_reference')} on {inv.get('invoice_number')}",
                invoice_id=inv["_id"],
                order_id=inv.get("order_id"),
                user_id=actor_user_id,
                session=session,
            )

        await record_checkout_payment_in_session(
            payment=pay, invoices=invoices, provider_event_id=provider_event_id, session=session
        )
        finance = FinanceService()
        for inv in invoices.values():
            await finance._refresh_invoice_status(inv, session=session)

        for inv in invoices.values():
            order = await _col(CollectionName.ORDERS).find_one({"_id": inv["order_id"]}, session=session)
            if order and order["status"] == OrderStatus.AWAITING_PAYMENT:
                await _col(CollectionName.ORDERS).update_one(
                    {"_id": order["_id"], "status": OrderStatus.AWAITING_PAYMENT},
                    {
                        "$set": {"status": OrderStatus.PENDING, "updated_at": now},
                        "$push": {
                            "status_history": {
                                "status": OrderStatus.PENDING,
                                "changed_by_user_id": None,
                                "note": "Payment confirmed — sent to supplier",
                                "changed_at": now,
                            }
                        },
                    },
                    session=session,
                )
        if pay.get("checkout_id"):
            await _col(CollectionName.CHECKOUTS).update_one(
                {"_id": pay["checkout_id"], "status": CheckoutStatus.AWAITING_PAYMENT},
                {
                    "$set": {"status": CheckoutStatus.PAID, "paid_at": now, "updated_at": now},
                    "$push": {"status_history": {"status": CheckoutStatus.PAID, "note": "Payment confirmed", "changed_at": now}},
                },
                session=session,
            )
        return pay, True

    pay, applied = await run_in_transaction(_work)
    if applied:
        await _after_payment_success(pay, actor_user_id=actor_user_id)
    return pay, applied

async def _after_payment_success(pay: dict[str, Any], *, actor_user_id: str | None) -> None:
    checkout = (
        await _col(CollectionName.CHECKOUTS).find_one({"_id": pay["checkout_id"]}) if pay.get("checkout_id") else None
    )
    ref = (checkout or {}).get("checkout_number") or pay.get("payment_reference")
    await _audit(
        "PAYMENT_COMPLETED",
        resource_type="payment",
        resource_id=pay["_id"],
        business_id=pay.get("payer_business_id"),
        user_id=actor_user_id,
        metadata={
            "payment_reference": pay.get("payment_reference"),
            "checkout_number": (checkout or {}).get("checkout_number"),
            "amount": format(money(pay["amount"]), "f"),
            "currency": pay.get("currency"),
            "method": pay.get("payment_method"),
            "provider": pay.get("provider"),
        },
    )
    is_cash = pay.get("payment_method") == PaymentMethod.CASH
    await _notify(
        recipient_business_id=pay["payer_business_id"],
        type="PAYMENT_RECEIVED",
        title=f"Payment received for {ref}",
        message=(
            "TradeBay confirmed your cash payment. Thank you!"
            if is_cash
            else "Your card payment went through. Suppliers are preparing your orders."
        ),
        reference_type="checkout" if checkout else "payment",
        reference_id=checkout["_id"] if checkout else pay["_id"],
    )
    invoice_ids = [a["invoice_id"] for a in pay.get("allocations") or []]
    order_ids = [
        inv["order_id"]
        async for inv in _col(CollectionName.CUSTOMER_INVOICES).find({"_id": {"$in": invoice_ids}}, {"order_id": 1})
    ]
    async for order in _col(CollectionName.ORDERS).find({"_id": {"$in": order_ids}}):
        await _notify(
            recipient_business_id=order["supplier_business_id"],
            type="PAYMENT_RECEIVED" if is_cash else "ORDER_CREATED",
            title=(
                f"Cash received for {order.get('order_number')}"
                if is_cash
                else f"New paid order {order.get('order_number')}"
            ),
            message=(
                "TradeBay confirmed the buyer's cash payment. Your earnings are now pending release."
                if is_cash
                else "The buyer paid by card. Confirm the order in TradeBay to start fulfilment."
            ),
            reference_type="order",
            reference_id=order["_id"],
        )
        if order.get("status") == OrderStatus.COMPLETED:
                                                                                        
            try:
                from app.modules.platform_money.service import PlatformMoneyService

                await PlatformMoneyService().release_funds_for_order(order_id=str(order["_id"]), user_id=actor_user_id)
            except Exception:
                logger.warning("checkout_release_after_cash_failed", order_id=str(order["_id"]))

                                                                                     

async def apply_payment_failure(
    *, payment_id: ObjectId, failure_code: str | None, failure_message: str | None
) -> bool:
    now = utc_now()
    result = await _col(CollectionName.PAYMENTS).update_one(
        {"_id": payment_id, "status": {"$in": [PaymentStatus.PENDING, PaymentStatus.FAILED]}},
        {
            "$set": {
                "status": PaymentStatus.FAILED,
                "failure_code": (failure_code or "card_declined")[:80],
                "failure_message": (failure_message or "The card was declined.")[:300],
                "failed_at": now,
                "updated_at": now,
            },
            "$inc": {"failure_count": 1},
        },
    )
    if not result.modified_count:
        return False
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": payment_id})
    if pay and int(pay.get("failure_count") or 0) == 1:
        await _notify(
            recipient_business_id=pay["payer_business_id"],
            type="PAYMENT_FAILED",
            title="Card payment didn't go through",
            message="Nothing was charged. You can try another card from your checkout.",
            reference_type="checkout",
            reference_id=pay.get("checkout_id") or pay["_id"],
        )
    return True

async def apply_provider_cancellation(*, payment_id: ObjectId, reason: str) -> bool:
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": payment_id})
    if pay is None or pay["status"] not in {PaymentStatus.PENDING, PaymentStatus.FAILED}:
        return False
    checkout = await _col(CollectionName.CHECKOUTS).find_one({"_id": pay.get("checkout_id")})
    if checkout is None:
        return False

    async def _work(session: MongoSession) -> bool:
        return await cancel_checkout_in_session(checkout, user_id=None, reason=reason, session=session)

    return await run_in_transaction(_work)

                                                                                     

async def apply_intent_state(pay: dict[str, Any], intent: IntentResult, *, event_id: str | None) -> str:
    meta_payment = (intent.metadata or {}).get("payment_id")
    if meta_payment and meta_payment != str(pay["_id"]):
        logger.error("stripe_intent_payment_mismatch", intent=intent.id)
        return "mismatch"
    if intent.status == "succeeded":
        _, applied = await apply_payment_success(
            payment_id=pay["_id"],
            provider_event_id=event_id,
            amount_minor=intent.amount_minor,
            currency=intent.currency,
        )
        return "completed" if applied else "already_completed"
    if intent.status == "canceled":
        return "cancelled" if await apply_provider_cancellation(payment_id=pay["_id"], reason="Card payment cancelled") else "noop"
    if intent.failure_message or intent.failure_code:
        changed = await apply_payment_failure(
            payment_id=pay["_id"], failure_code=intent.failure_code, failure_message=intent.failure_message
        )
        return "failed" if changed else "noop"
    return "pending"

async def sync_card_payment(pay: dict[str, Any]) -> str:
    if not pay.get("provider_payment_id"):
        return "pending"
    intent = await get_payment_gateway().retrieve_intent(str(pay["provider_payment_id"]))
    return await apply_intent_state(pay, intent, event_id=None)

async def handle_stripe_webhook(*, payload: bytes, signature: str | None) -> dict[str, Any]:
    secret = get_settings().stripe_webhook_secret
    if secret is None or not secret.get_secret_value():
        raise AppError("WEBHOOK_NOT_CONFIGURED", "Stripe webhooks are not configured", status_code=503)
    event = verify_stripe_signature(payload=payload, signature_header=signature, secret=secret.get_secret_value())
    event_id = str(event["id"])
    event_type = str(event["type"])
    events = _col(CollectionName.PAYMENT_PROVIDER_EVENTS)
    now = utc_now()
    try:
        await events.insert_one(
            {"provider": "stripe", "event_id": event_id, "type": event_type, "status": "processing", "received_at": now}
        )
    except DuplicateKeyError:
        existing = await events.find_one({"provider": "stripe", "event_id": event_id})
        if existing and existing.get("status") in {"processed", "ignored", "unmatched"}:
            return {"received": True, "duplicate": True}
                                                                                          

    obj = ((event.get("data") or {}).get("object")) or {}
    outcome = "ignored"
    if obj.get("object") == "payment_intent" and event_type in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:
        from app.modules.checkout.gateway import _intent_from_payload

        intent = _intent_from_payload(obj)
        pay = await _col(CollectionName.PAYMENTS).find_one({"provider": "stripe", "provider_payment_id": intent.id})
        if pay is None:
            outcome = "unmatched"
        else:
            if event_type == "payment_intent.succeeded" and obj.get("amount_received") is not None:
                intent = IntentResult(
                    id=intent.id,
                    status=intent.status,
                    amount_minor=int(obj["amount_received"]),
                    currency=intent.currency,
                    metadata=intent.metadata,
                )
            try:
                outcome = await apply_intent_state(pay, intent, event_id=event_id)
            except PaymentAmountMismatchError:
                outcome = "amount_mismatch"
                await _col(CollectionName.PAYMENTS).update_one(
                    {"_id": pay["_id"]},
                    {"$set": {"requires_attention": True, "attention_reason": "amount_mismatch", "updated_at": now}},
                )
            except ConflictError:
                                                                                                  
                outcome = "requires_attention"
                await _col(CollectionName.PAYMENTS).update_one(
                    {"_id": pay["_id"]},
                    {"$set": {"requires_attention": True, "attention_reason": event_type, "updated_at": now}},
                )
            except Exception:
                await events.update_one(
                    {"provider": "stripe", "event_id": event_id}, {"$set": {"status": "failed", "updated_at": utc_now()}}
                )
                raise
    await events.update_one(
        {"provider": "stripe", "event_id": event_id},
        {"$set": {"status": "processed" if outcome not in {"ignored", "unmatched"} else outcome, "outcome": outcome, "processed_at": utc_now()}},
    )
    return {"received": True, "outcome": outcome}

async def confirm_offline_payment(*, payment_id: str, user_id: str, note: str | None) -> dict[str, Any]:
    from app.modules.finance.service import FinanceService

    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": parse_object_id(payment_id)})
    if pay is None:
        raise NotFoundError("Payment not found")
    if pay.get("payment_method") != PaymentMethod.CASH:
        raise BadRequestError("Only cash payments are confirmed by hand. Card payments confirm through the processor.")
    if pay["status"] == PaymentStatus.CANCELLED:
        raise ConflictError("This payment was cancelled")
    updated, _ = await apply_payment_success(payment_id=pay["_id"], actor_user_id=user_id, note=note)
    return FinanceService()._serialize_payment(updated)
