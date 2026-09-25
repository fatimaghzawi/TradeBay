
from __future__ import annotations

from typing import Any

import pytest
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.trust.notifications import NotificationService
from app.modules.trust.notify import notify
from app.shared.utils.datetime import utc_now
from bson import ObjectId


@pytest.mark.asyncio
async def test_notify_list_and_mark_read(app: object) -> None:
    user_id = ObjectId()
    biz_id = ObjectId()
    now = utc_now()

    await mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).insert_one(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "business_account_id": biz_id,
            "status": "active",
            "created_at": now,
        }
    )

    created = await notify(
        recipient_business_id=biz_id,
        type="TEST_EVENT",
        title="Hello TradeBay",
        message="Body",
        reference_type="order",
        reference_id=ObjectId(),
    )
    assert created >= 1

    svc = NotificationService()
    items, total = await svc.list_for_user(user_id=str(user_id), page_size=10)
    assert total >= 1
    assert items[0]["title"] == "Hello TradeBay"
    assert items[0]["is_read"] is False

    count = await svc.unread_count(user_id=str(user_id))
    assert count >= 1

    marked = await svc.mark_read(user_id=str(user_id), notification_id=items[0]["id"])
    assert marked["is_read"] is True

    after = await svc.unread_count(user_id=str(user_id))
    assert after == count - 1

    await svc.mark_all_read(user_id=str(user_id))
    assert await svc.unread_count(user_id=str(user_id)) == 0

@pytest.mark.asyncio
async def test_notify_emails_personal_inbox_not_company_contact(
    app: object, email_inbox: Any
) -> None:
    user_id = ObjectId()
    biz_id = ObjectId()
    now = utc_now()

    await mongo_manager.collection(CollectionName.USERS).insert_one(
        {
            "_id": user_id,
            "email": "karim@levantwholesale.com",
            "personal_email": "karim.personal@gmail.com",
            "first_name": "Karim",
            "last_name": "Haddad",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).insert_one(
        {
            "_id": biz_id,
            "name": "Levant Wholesale",
            "type": "supplier",
            "status": "verified",
            "contact_email": "sales@levantwholesale.com",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).insert_one(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "business_account_id": biz_id,
            "status": "active",
            "created_at": now,
        }
    )
    created = await notify(
        recipient_business_id=biz_id,
        type="RFQ_INVITATION",
        title="RFQ invitation: RFQ-88",
        message="You have been invited to quote.",
        reference_type="rfq",
        reference_id=ObjectId(),
    )
    assert created >= 1
    assert not [m for m in email_inbox.messages if m["template"] == "business_event"]

@pytest.mark.asyncio
async def test_notify_uses_invitation_delivery_email(
    app: object, email_inbox: Any
) -> None:
    user_id = ObjectId()
    biz_id = ObjectId()
    now = utc_now()
    await mongo_manager.collection(CollectionName.USERS).insert_one(
        {
            "_id": user_id,
            "email": "nora@levantwholesale.com",
            "first_name": "Nora",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).insert_one(
        {
            "_id": biz_id,
            "name": "Levant Wholesale",
            "type": "supplier",
            "status": "verified",
            "contact_email": "sales@levantwholesale.com",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).insert_one(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "business_account_id": biz_id,
            "status": "active",
            "created_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.INVITATIONS).insert_one(
        {
            "_id": ObjectId(),
            "business_account_id": biz_id,
            "invited_email": "nora@levantwholesale.com",
            "delivery_email": "nora.khoury@gmail.com",
            "status": "accepted",
            "created_at": now,
        }
    )
    await notify(
        recipient_business_id=biz_id,
        type="ORDER_CREATED",
        title="New direct order PO-9",
        message="A buyer placed a direct purchase order.",
        reference_type="order",
        reference_id=ObjectId(),
    )
    sent = [m for m in email_inbox.messages if m["template"] == "business_event"]
    assert sent
    assert sent[-1]["to"] == "nora.khoury@gmail.com"
    assert sent[-1]["context"]["business_name"] == "Levant Wholesale"

@pytest.mark.asyncio
async def test_tracking_updated_stays_in_app_unless_emailed(
    app: object, email_inbox: Any
) -> None:
    user_id = ObjectId()
    biz_id = ObjectId()
    now = utc_now()
    await mongo_manager.collection(CollectionName.USERS).insert_one(
        {
            "_id": user_id,
            "email": "omar@harborhospitality.lb",
            "personal_email": "omar.personal@gmail.com",
            "first_name": "Omar",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).insert_one(
        {
            "_id": biz_id,
            "name": "Harbor Hospitality",
            "type": "buyer",
            "status": "verified",
            "contact_email": "ops@harborhospitality.lb",
            "created_at": now,
            "updated_at": now,
        }
    )
    await mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).insert_one(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "business_account_id": biz_id,
            "status": "active",
            "created_at": now,
        }
    )
    await notify(
        recipient_business_id=biz_id,
        type="TRACKING_UPDATED",
        title="Shipment SH-1 → in_transit",
        reference_type="shipment",
        reference_id=ObjectId(),
        email=False,
    )
    assert not [m for m in email_inbox.messages if m["template"] == "business_event"]

    await notify(
        recipient_business_id=biz_id,
        type="TRACKING_UPDATED",
        title="Shipment SH-1 → delivered",
        reference_type="shipment",
        reference_id=ObjectId(),
        email=True,
    )
    sent = [m for m in email_inbox.messages if m["template"] == "business_event"]
    assert sent
    assert sent[-1]["to"] == "omar.personal@gmail.com"
