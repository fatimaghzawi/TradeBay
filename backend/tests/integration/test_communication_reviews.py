"""Communication + reviews smoke aligned to BRD §8.7."""

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
    }


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    client.cookies = response.cookies


@pytest.mark.asyncio
async def test_brd_conversation_poll_messaging(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
) -> None:
    """FR-MSG-01/02/05/06/07/08 — two-company thread, participants, unread, soft delete."""
    buyer = await _register(client, email_inbox, business_type="buyer")
    supplier = await _register(client, email_inbox, business_type="supplier")
    assert buyer["business"] and supplier["business"]

    await _login(client, buyer["email"], buyer["password"])
    opened = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": supplier["business"]["id"],
            "type": "DIRECT",
            "subject": "Hello supplier",
        },
    )
    assert opened.status_code == 200, opened.text
    conv = opened.json()["data"]
    conv_id = conv["id"]

    sent = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"body": "Can you quote earbuds?"},
    )
    assert sent.status_code == 200, sent.text
    msg_id = sent.json()["data"]["id"]

    again = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": supplier["business"]["id"],
            "type": "DIRECT",
        },
    )
    assert again.status_code == 200
    assert again.json()["data"]["id"] == conv_id

    await _login(client, supplier["email"], supplier["password"])
    inbox = await client.get("/api/v1/conversations")
    assert inbox.status_code == 200
    row = next(r for r in inbox.json()["data"] if r["id"] == conv_id)
    assert row["unread_count"] >= 1
    assert row.get("counterparty_name")

    unread = await client.get("/api/v1/conversations/unread-count")
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["count"] >= 1

    detail = await client.get(f"/api/v1/conversations/{conv_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["unread_count"] == 0

    reply = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"body": "Yes — sending quote shortly.", "reply_to_message_id": msg_id},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["data"]["reply_to_message_id"] == msg_id

    await _login(client, buyer["email"], buyer["password"])
    deleted = await client.delete(f"/api/v1/conversations/{conv_id}/messages/{msg_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["is_deleted"] is True

    listed = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert listed.status_code == 200
    tombstone = next(m for m in listed.json()["data"] if m["id"] == msg_id)
    assert tombstone["is_deleted"] is True
    assert tombstone["body"] is None


@pytest.mark.asyncio
async def test_rfq_context_one_thread_and_system_event(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
) -> None:
    buyer = await _register(client, email_inbox, business_type="buyer")
    supplier = await _register(client, email_inbox, business_type="supplier")
    assert buyer["business"] and supplier["business"]
    rfq_id = ObjectId()

    await _login(client, buyer["email"], buyer["password"])
    opened = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": supplier["business"]["id"],
            "type": "RFQ",
            "context_type": "rfq",
            "context_id": str(rfq_id),
            "subject": "RFQ chat",
        },
    )
    assert opened.status_code == 200, opened.text
    conv_id = opened.json()["data"]["id"]

    from app.modules.communication.constants import SystemEvent
    from app.modules.communication.timeline import post_thread_system_event

    await post_thread_system_event(
        context_type="rfq",
        context_id=str(rfq_id),
        system_event=SystemEvent.QUOTE_RECEIVED,
        body="Quotation Q-1 received",
        initiator_business_id=buyer["business"]["id"],
        counterparty_business_id=supplier["business"]["id"],
        subject="RFQ chat",
    )

    msgs = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert msgs.status_code == 200
    types = {m["message_type"] for m in msgs.json()["data"]}
    assert "SYSTEM" in types


@pytest.mark.asyncio
async def test_same_companies_reuse_one_thread(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
) -> None:
    buyer = await _register(client, email_inbox, business_type="buyer")
    supplier = await _register(client, email_inbox, business_type="supplier")
    assert buyer["business"] and supplier["business"]
    await _login(client, buyer["email"], buyer["password"])

    direct = await client.post(
        "/api/v1/conversations",
        json={"counterparty_business_id": supplier["business"]["id"], "type": "DIRECT"},
    )
    assert direct.status_code == 200, direct.text
    thread_id = direct.json()["data"]["id"]

    rfq_a = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": supplier["business"]["id"],
            "type": "RFQ",
            "context_type": "rfq",
            "context_id": str(ObjectId()),
            "subject": "First RFQ",
        },
    )
    assert rfq_a.status_code == 200, rfq_a.text
    assert rfq_a.json()["data"]["id"] == thread_id

    rfq_b = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": supplier["business"]["id"],
            "type": "RFQ",
            "context_type": "rfq",
            "context_id": str(ObjectId()),
            "subject": "Second RFQ",
        },
    )
    assert rfq_b.status_code == 200, rfq_b.text
    assert rfq_b.json()["data"]["id"] == thread_id

    await _login(client, supplier["email"], supplier["password"])
    from_supplier = await client.post(
        "/api/v1/conversations",
        json={
            "counterparty_business_id": buyer["business"]["id"],
            "type": "ORDER",
            "context_type": "order",
            "context_id": str(ObjectId()),
        },
    )
    assert from_supplier.status_code == 200, from_supplier.text
    assert from_supplier.json()["data"]["id"] == thread_id


@pytest.mark.asyncio
async def test_review_only_on_completed_order(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
) -> None:
    buyer = await _register(client, email_inbox, business_type="buyer")
    supplier = await _register(client, email_inbox, business_type="supplier")
    assert buyer["business"] and supplier["business"]

    order_id = ObjectId()
    now = utc_now()
    await mongo_manager.database["orders"].insert_one(
        {
            "_id": order_id,
            "order_number": f"PO-TEST-{os.urandom(2).hex()}",
            "buyer_business_id": ObjectId(buyer["business"]["id"]),
            "supplier_business_id": ObjectId(supplier["business"]["id"]),
            "status": "completed",
            "currency": "USD",
            "created_at": now,
            "updated_at": now,
        }
    )

    await _login(client, buyer["email"], buyer["password"])
    created = await client.post(
        "/api/v1/reviews",
        json={"order_id": str(order_id), "rating": 5, "comment": "On time"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["rating"] == 5
