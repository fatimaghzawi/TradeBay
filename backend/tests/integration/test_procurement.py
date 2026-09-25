
from __future__ import annotations

import os
from typing import Any

import pytest
from app.db.mongodb import mongo_manager
from app.modules.identity.email import MemoryEmailSender
from app.shared.utils.datetime import utc_now
from bson import ObjectId
from httpx import AsyncClient


async def _verify_email(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/auth/email/verify", json={"token": token})
    assert response.status_code == 200, response.text

async def _register(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    *,
    business_type: str,
) -> dict[str, Any]:
    email = f"{business_type}_{os.urandom(4).hex()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Pat",
            "last_name": business_type.title(),
            "business_name": f"{business_type.title()} Co {os.urandom(2).hex()}",
            "business_type": business_type,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    token = email_inbox.last_token(to=email, template="email_verification")
    assert token
    client.cookies = response.cookies
    await _verify_email(client, token)
    return {
        "email": email,
        "password": "SecurePass123!",
        "user": payload["user"],
        "business": payload.get("business"),
        "cookies": response.cookies,
    }

async def _mark_supplier_verified(business_id: str) -> None:
    now = utc_now()
    await mongo_manager.database["business_accounts"].update_one(
        {"_id": ObjectId(business_id)},
        {"$set": {"status": "verified", "updated_at": now}},
    )
    await mongo_manager.database["supplier_profiles"].update_one(
        {"business_account_id": ObjectId(business_id)},
        {
            "$set": {
                "verification_status": "verified",
                "verified_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
    )

async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    client.cookies = response.cookies

@pytest.mark.asyncio
async def test_procurement_end_to_end(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
) -> None:
    buyer = await _register(client, email_inbox, business_type="buyer")
    supplier = await _register(client, email_inbox, business_type="supplier")
    assert buyer["business"] and supplier["business"]
    supplier_id = supplier["business"]["id"]
    await _mark_supplier_verified(supplier_id)

    await _login(client, buyer["email"], buyer["password"])

    created = await client.post(
        "/api/v1/rfqs",
        json={
            "title": "Wireless earbuds procurement",
            "description": "Starter RFQ",
            "destination": {"city": "Tyre", "governorate": "South", "country": "Lebanon"},
            "currency": "USD",
            "visibility": "invited",
            "items": [
                {
                    "product_name": "Wireless Earbuds",
                    "sku": "WB-100",
                    "quantity": "100",
                    "unit": "unit",
                    "target_unit_price": "12.00",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    rfq = created.json()["data"]
    rfq_id = rfq["id"]
    assert rfq["status"] == "draft"
    assert len(rfq["items"]) == 1
    rfq_item_id = rfq["items"][0]["id"]

    published = await client.post(f"/api/v1/rfqs/{rfq_id}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "published"

    invited = await client.post(
        f"/api/v1/rfqs/{rfq_id}/invite-suppliers",
        json={"supplier_business_ids": [supplier_id]},
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["data"]["invite_count"] >= 1

    await _login(client, supplier["email"], supplier["password"])
    accepted = await client.post(f"/api/v1/rfqs/{rfq_id}/invitations/accept")
    assert accepted.status_code == 200, accepted.text

    quoted = await client.post(
        f"/api/v1/rfqs/{rfq_id}/quotations?submit=true",
        json={
            "payment_terms": "Net 30",
            "delivery_terms": "Delivered to Tyre",
            "lines": [
                {
                    "rfq_item_id": rfq_item_id,
                    "quantity": "100",
                    "unit_price": "11.50",
                    "moq": 50,
                    "lead_time_days": 5,
                    "discount": "0",
                    "tax": "0",
                    "shipping_allocation": "50.00",
                }
            ],
            "document_discount": "0",
            "document_shipping": "0",
            "document_tax": "0",
        },
    )
    assert quoted.status_code == 200, quoted.text
    quotation = quoted.json()["data"]
    assert quotation["status"] == "submitted"
    assert quotation["total"] == "1200.00"
    quotation_id = quotation["id"]

    await _login(client, buyer["email"], buyer["password"])
    comparison = await client.get(f"/api/v1/rfqs/{rfq_id}/comparison")
    assert comparison.status_code == 200
    assert len(comparison.json()["data"]["quotations"]) >= 1

    awarded = await client.post(
        f"/api/v1/rfqs/{rfq_id}/award",
        json={"quotation_id": quotation_id, "confirm": True},
    )
    assert awarded.status_code == 200, awarded.text
    order = awarded.json()["data"]
    assert order["status"] == "pending"
    assert order["order_number"].startswith("PO-")
    order_id = order["id"]
    order_item_id = order["items"][0]["id"]

    await _login(client, supplier["email"], supplier["password"])
    ack = await client.post(f"/api/v1/purchase-orders/{order_id}/acknowledge")
    assert ack.status_code == 200, ack.text
    assert ack.json()["data"]["status"] == "confirmed"

    ship = await client.post(
        f"/api/v1/purchase-orders/{order_id}/shipments",
        json={
            "carrier_name": "Local Courier",
            "tracking_number": "TRK-001",
            "origin": "Beirut",
            "lines": [{"order_item_id": order_item_id, "quantity": "100"}],
        },
    )
    assert ship.status_code == 200, ship.text
    shipment = ship.json()["data"]
    shipment_id = shipment["id"]
                                                                                     
    assert shipment["status"] == "shipped"

    for status in ("in_transit", "delivered"):
        track = await client.post(
            f"/api/v1/shipments/{shipment_id}/tracking-events",
            json={"status": status, "description": f"Moved to {status}", "location": "Lebanon"},
        )
        assert track.status_code == 200, track.text

    evidence = await client.post(
        f"/api/v1/shipments/{shipment_id}/delivery-evidence",
        json={"evidence_type": "pod", "url": "https://example.com/pod.pdf", "note": "Signed"},
    )
    assert evidence.status_code == 200, evidence.text

    await _login(client, buyer["email"], buyer["password"])
    received = await client.post(
        f"/api/v1/shipments/{shipment_id}/receive",
        json={
            "complete_order": True,
            "lines": [
                {
                    "order_item_id": order_item_id,
                    "received_quantity": "95",
                    "damaged_quantity": "3",
                    "missing_quantity": "2",
                    "rejected_quantity": "0",
                }
            ],
        },
    )
    assert received.status_code == 200, received.text

    final_order = await client.get(f"/api/v1/purchase-orders/{order_id}")
    assert final_order.status_code == 200
    assert final_order.json()["data"]["status"] == "completed"
