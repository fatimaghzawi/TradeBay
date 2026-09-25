
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

WEBHOOK_TOLERANCE_SECONDS = 300

class PaymentGatewayError(AppError):
    def __init__(self, message: str = "The card processor didn't respond. Please try again.") -> None:
        super().__init__("PAYMENT_PROVIDER_ERROR", message, status_code=502)

class WebhookSignatureError(AppError):
    def __init__(self, message: str = "Invalid webhook signature") -> None:
        super().__init__("INVALID_WEBHOOK_SIGNATURE", message, status_code=400)

@dataclass(frozen=True)
class IntentResult:
    id: str
    status: str
    amount_minor: int
    currency: str
    client_secret: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    metadata: dict[str, Any] | None = None

class PaymentGateway(Protocol):
    provider: str

    def is_configured(self) -> bool: ...

    def publishable_key(self) -> str | None: ...

    async def create_intent(
        self, *, amount_minor: int, currency: str, idempotency_key: str, metadata: dict[str, str]
    ) -> IntentResult: ...

    async def retrieve_intent(self, intent_id: str) -> IntentResult: ...

    async def cancel_intent(self, intent_id: str) -> IntentResult: ...

def to_minor_units(amount: Decimal) -> int:
    minor = (amount * 100).to_integral_value()
    if minor != amount * 100:
        raise ValueError("Amount has more precision than the currency allows")
    return int(minor)

def _intent_from_payload(data: dict[str, Any]) -> IntentResult:
    err = data.get("last_payment_error") or {}
    return IntentResult(
        id=str(data["id"]),
        status=str(data.get("status") or ""),
        amount_minor=int(data.get("amount") or 0),
        currency=str(data.get("currency") or "").upper(),
        client_secret=data.get("client_secret"),
        failure_code=err.get("decline_code") or err.get("code"),
        failure_message=err.get("message"),
        metadata=dict(data.get("metadata") or {}),
    )

class StripeGateway:
    provider = "stripe"

    def _secret(self) -> str | None:
        key = get_settings().stripe_secret_key
        return key.get_secret_value() if key else None

    def is_configured(self) -> bool:
        return bool(self._secret())

    def publishable_key(self) -> str | None:
        return get_settings().stripe_publishable_key

    async def _request(
        self, method: str, path: str, *, data: dict[str, str] | None = None, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        secret = self._secret()
        if not secret:
            raise PaymentGatewayError("Card payments aren't available right now.")
        settings = get_settings()
        headers = {"Authorization": f"Bearer {secret}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            async with httpx.AsyncClient(
                base_url=settings.stripe_api_base, timeout=settings.stripe_timeout_seconds
            ) as client:
                response = await client.request(method, path, data=data, headers=headers)
        except httpx.HTTPError as exc:
            raise PaymentGatewayError() from exc
        payload = response.json() if response.content else {}
        if response.status_code >= 400:
                                                                                     
            message = ((payload.get("error") or {}).get("message")) or "The card processor rejected the request."
            raise PaymentGatewayError(str(message)[:200])
        return payload

    async def create_intent(
        self, *, amount_minor: int, currency: str, idempotency_key: str, metadata: dict[str, str]
    ) -> IntentResult:
        data = {
            "amount": str(amount_minor),
            "currency": currency.lower(),
            "payment_method_types[]": "card",
            "description": metadata.get("description", "TradeBay checkout"),
        }
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value
        payload = await self._request("POST", "/v1/payment_intents", data=data, idempotency_key=idempotency_key)
        return _intent_from_payload(payload)

    async def retrieve_intent(self, intent_id: str) -> IntentResult:
        return _intent_from_payload(await self._request("GET", f"/v1/payment_intents/{intent_id}"))

    async def cancel_intent(self, intent_id: str) -> IntentResult:
        return _intent_from_payload(await self._request("POST", f"/v1/payment_intents/{intent_id}/cancel"))

_gateway: PaymentGateway = StripeGateway()

def get_payment_gateway() -> PaymentGateway:
    return _gateway

def set_payment_gateway(gateway: PaymentGateway | None) -> None:
    global _gateway
    _gateway = gateway or StripeGateway()

def verify_stripe_signature(
    *, payload: bytes, signature_header: str | None, secret: str, now: float | None = None
) -> dict[str, Any]:
    if not signature_header:
        raise WebhookSignatureError("Missing Stripe-Signature header")
    timestamp: str | None = None
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not timestamp.isdigit() or not signatures:
        raise WebhookSignatureError()
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise WebhookSignatureError()
    current = now if now is not None else time.time()
    if abs(current - int(timestamp)) > WEBHOOK_TOLERANCE_SECONDS:
        raise WebhookSignatureError("Webhook timestamp outside the allowed window")
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookSignatureError("Webhook body is not valid JSON") from exc
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise WebhookSignatureError("Webhook body is not a Stripe event")
    return event

def sign_stripe_payload(*, payload: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"
