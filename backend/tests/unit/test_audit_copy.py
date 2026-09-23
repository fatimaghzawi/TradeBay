"""Audit serialization / enrichment helpers."""

from __future__ import annotations

from bson import ObjectId

from app.shared.services.audit import AuditService, _sanitize_metadata


def test_sanitize_drops_none_and_secrets() -> None:
    cleaned = _sanitize_metadata(
        {
            "invited_email": "a@b.com",
            "role_name": None,
            "password": "secret",
            "otp": "123456",
        }
    )
    assert cleaned == {"invited_email": "a@b.com"}


def test_serialize_fills_actor_and_invite_subject() -> None:
    actor_id = ObjectId()
    invite_id = ObjectId()
    row = {
        "_id": ObjectId(),
        "action": "USER_INVITED",
        "resource_type": "invitation",
        "resource_id": invite_id,
        "business_account_id": ObjectId(),
        "user_id": actor_id,
        "metadata": {"invited_email": "sales@acme.com"},
        "ip_address": None,
        "created_at": None,
    }
    out = AuditService._serialize(
        row,
        user_labels={str(actor_id): "Lina Admin"},
        role_names={},
        invitation_emails={},
    )
    assert out["metadata"]["actor_name"] == "Lina Admin"
    assert out["metadata"]["invited_email"] == "sales@acme.com"


def test_serialize_accept_uses_member_not_role_as_person() -> None:
    user_id = ObjectId()
    role_id = ObjectId()
    invite_id = ObjectId()
    row = {
        "_id": ObjectId(),
        "action": "INVITATION_ACCEPTED",
        "resource_type": "invitation",
        "resource_id": invite_id,
        "business_account_id": ObjectId(),
        "user_id": user_id,
        "metadata": {"role_id": str(role_id), "role_name": "Sales Manager"},
        "ip_address": None,
        "created_at": None,
    }
    out = AuditService._serialize(
        row,
        user_labels={str(user_id): "Fatoum Safawi"},
        role_names={str(role_id): "Sales Manager"},
        invitation_emails={str(invite_id): "littlemiss_fatoum@safawi.com"},
    )
    assert out["metadata"]["actor_name"] == "Fatoum Safawi"
    assert out["metadata"]["member_name"] == "Fatoum Safawi"
    assert out["metadata"]["invited_email"] == "littlemiss_fatoum@safawi.com"
    assert out["metadata"]["role_name"] == "Sales Manager"
