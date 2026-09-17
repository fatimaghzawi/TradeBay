"""Identity security integration tests: OTP, recovery, sessions, RBAC, isolation."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import pytest
from app.core.constants import REFRESH_COOKIE_NAME
from app.core.security import hash_token, verify_password
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import SYSTEM_ROLE_PLATFORM_ADMIN, MembershipStatus
from app.modules.identity.email import MemoryEmailSender
from app.modules.identity.permissions import permission_code
from app.shared.utils.datetime import utc_now
from httpx import ASGITransport, AsyncClient


async def _register(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    *,
    email: str | None = None,
    business_name: str | None = "Co Ltd",
) -> dict[str, Any]:
    address = email or f"u_{os.urandom(4).hex()}@example.com"
    payload: dict[str, Any] = {
        "email": address,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
    }
    if business_name:
        payload["business_name"] = business_name
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert "verification_token" not in body
    return {
        "email": address,
        "password": "SecurePass123!",
        "user": body["user"],
        "business": body.get("business"),
        "verification_token": email_inbox.last_token(to=address, template="email_verification"),
    }


async def _verify(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_register_hashes_password_and_starts_unverified(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    user = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    assert user is not None
    assert user["password_hash"] != registered_user["password"]
    assert verify_password(registered_user["password"], user["password_hash"])
    assert user["status"] == "pending"
    assert user.get("email_verified_at") is None


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": registered_user["email"],
            "password": "SecurePass123!",
            "first_name": "Other",
            "last_name": "Person",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_invalid_email_and_password_rejected(client: AsyncClient) -> None:
    bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "SecurePass123!", "first_name": "A", "last_name": "B"},
    )
    assert bad_email.status_code == 422
    weak = await client.post(
        "/api/v1/auth/register",
        json={"email": "ok@example.com", "password": "short", "first_name": "A", "last_name": "B"},
    )
    assert weak.status_code == 422
    no_digit = await client.post(
        "/api/v1/auth/register",
        json={"email": "ok2@example.com", "password": "NoDigitsHere", "first_name": "A", "last_name": "B"},
    )
    assert no_digit.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_invalid_expired_reused_and_wrong_purpose(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    token = registered_user["verification_token"]
    assert token
    bad = await client.post("/api/v1/auth/verify-email", json={"token": "totally-invalid-token"})
    assert bad.status_code == 401

    reset = await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    assert reset.status_code == 200
    reset_token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert reset_token
    wrong_purpose = await client.post("/api/v1/auth/verify-email", json={"token": reset_token})
    assert wrong_purpose.status_code == 401

    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"expires_at": utc_now() - timedelta(hours=1)}},
    )
    expired = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert expired.status_code == 401

    fresh = await client.post("/api/v1/auth/resend-verification")
    assert fresh.status_code == 200
    new_token = email_inbox.last_token(to=registered_user["email"], template="email_verification")
    assert new_token
    assert new_token != token
    old_again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert old_again.status_code == 401

    ok = await client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert ok.status_code == 200
    reused = await client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert reused.status_code == 401
    already = await client.post("/api/v1/auth/resend-verification")
    assert already.status_code == 200


@pytest.mark.asyncio
async def test_otp_max_attempts_on_same_challenge(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    token = registered_user["verification_token"]
    assert token
    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"attempts": 5}},
    )
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verified_user_can_create_second_business(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _verify(client, registered_user["verification_token"])
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "Second Trading",
            "legal_name": "Second Trading LLC",
            "tax_number": "TN-1",
            "contact_email": "ops@second.example.com",
            "contact_phone": "+964750000000",
            "address": {"city": "Baghdad", "country": "IQ"},
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["legal_name"] == "Second Trading LLC"
    assert body["contact_email"] == "ops@second.example.com"
    businesses = await client.get("/api/v1/businesses")
    assert businesses.json()["meta"]["total"] >= 2


@pytest.mark.asyncio
async def test_password_reset_flow_and_session_invalidation(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200
    assert unknown.json()["data"]["requested"] is True

    requested = await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    assert requested.status_code == 200
    token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert token

    verify_with_reset = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_with_reset.status_code == 401

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert reset.status_code == 200
    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert reused.status_code == 401

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "BrandNewPass123!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_expired_and_attempts(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert token
    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"expires_at": utc_now() - timedelta(hours=3)}},
    )
    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert expired.status_code == 401

    verify_token = registered_user["verification_token"]
    wrong = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": verify_token, "password": "BrandNewPass123!"},
    )
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_rejects_old_credential(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    assert old_refresh
    first = await client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    reused = await client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_current_and_revokes_sessions(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPass123!", "new_password": "NewerPass123!"},
    )
    assert wrong.status_code == 401
    ok = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": registered_user["password"], "new_password": "NewerPass123!"},
    )
    assert ok.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "NewerPass123!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_business_switch_rejected(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    other = await _register(client, email_inbox, business_name="Other Co")
    other_id = other["business"]["id"]
    # Restore first user's cookies by logging in again.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200
    switch = await client.post("/api/v1/businesses/current/switch", json={"business_id": other_id})
    assert switch.status_code == 403


@pytest.mark.asyncio
async def test_multi_business_permission_isolation(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _verify(client, registered_user["verification_token"])
    first_id = registered_user["business"]["id"]
    created = await client.post("/api/v1/businesses", json={"name": "Finance Desk"})
    assert created.status_code == 200
    second_id = created.json()["data"]["id"]
    switched = await client.post("/api/v1/businesses/current/switch", json={"business_id": second_id})
    assert switched.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.json()["data"]["active_business"]["id"] == second_id
    roles_b = (await client.get("/api/v1/roles")).json()["data"]
    await client.post("/api/v1/businesses/current/switch", json={"business_id": first_id})
    roles_a = (await client.get("/api/v1/roles")).json()["data"]
    ids_a = {item["id"] for item in roles_a}
    ids_b = {item["id"] for item in roles_b}
    assert ids_a.isdisjoint(ids_b)
    foreign = next(item for item in roles_b if item["name"] == "Viewer")
    patch = await client.patch(
        f"/api/v1/roles/{foreign['id']}",
        json={"permissions": ["users.read"]},
    )
    assert patch.status_code == 403


@pytest.mark.asyncio
async def test_invitation_accept_wrong_recipient_and_reuse(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    invitee_email = f"invitee_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={"email": invitee_email, "role_id": viewer["id"], "permissions": ["products.manage"]},
    )
    assert invited.status_code == 200
    assert "token" not in invited.json()["data"]
    assert "permissions" not in invited.json()["data"]
    token = email_inbox.last_token(to=invitee_email, template="invitation")
    assert token

    wrong = await client.post("/api/v1/invitations/accept", json={"token": token})
    assert wrong.status_code == 403

    other_transport = ASGITransport(app=app)
    async with AsyncClient(transport=other_transport, base_url="http://test") as other_client:
        await _register(other_client, email_inbox, email=invitee_email, business_name=None)
        accepted = await other_client.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text
        reused = await other_client.post("/api/v1/invitations/accept", json={"token": token})
        assert reused.status_code == 403


@pytest.mark.asyncio
async def test_invitation_expired_and_revoked(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"later_{os.urandom(3).hex()}@example.com"
    invited = await client.post("/api/v1/invitations", json={"email": email, "role_id": viewer["id"]})
    invitation_id = invited.json()["data"]["id"]
    token = email_inbox.last_token(to=email, template="invitation")
    revoked = await client.post(f"/api/v1/invitations/{invitation_id}/revoke")
    assert revoked.status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=email, business_name=None)
        accepted = await other.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 403


@pytest.mark.asyncio
async def test_custom_role_and_system_role_protection(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    created = await client.post(
        "/api/v1/roles",
        json={"name": "Ops Desk", "permissions": ["users.read", "roles.read"]},
    )
    assert created.status_code == 200
    role_id = created.json()["data"]["id"]
    deleted = await client.delete(f"/api/v1/roles/{role_id}")
    assert deleted.status_code == 200
    roles = (await client.get("/api/v1/roles")).json()["data"]
    admin = next(item for item in roles if item["name"] == "Business Admin")
    blocked = await client.delete(f"/api/v1/roles/{admin['id']}")
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_permission_denied_uses_resource_action_not_role_name(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"viewer_{os.urandom(3).hex()}@example.com"
    await client.post("/api/v1/invitations", json={"email": email, "role_id": viewer["id"]})
    token = email_inbox.last_token(to=email, template="invitation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=email, business_name=None)
        await other.post("/api/v1/invitations/accept", json={"token": token})
        await other.post(
            "/api/v1/businesses/current/switch",
            json={"business_id": registered_user["business"]["id"]},
        )
        denied = await other.post("/api/v1/roles", json={"name": "Nope", "permissions": ["users.read"]})
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
        assert denied.json()["error"]["details"]["resource"] == "roles"
        assert denied.json()["error"]["details"]["action"] == "manage"


@pytest.mark.asyncio
async def test_suspend_requires_reason_blocks_sessions_and_audits(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    missing = await client.post(
        "/api/v1/users/suspend",
        json={"user_id": registered_user["user"]["id"], "reason": ""},
    )
    assert missing.status_code == 422
    suspended = await client.post(
        "/api/v1/users/suspend",
        json={"user_id": registered_user["user"]["id"], "reason": "Policy violation"},
    )
    assert suspended.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 403
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code in {401, 403}
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 403
    logs = await mongo_manager.database["audit_logs"].find({"action": "USER_SUSPENDED"}).to_list(10)
    assert logs
    assert logs[-1]["metadata"]["reason"] == "Policy violation"
    assert "password" not in logs[-1]["metadata"]


@pytest.mark.asyncio
async def test_platform_staff_through_platform_business(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    me = await client.get("/api/v1/auth/me")
    trading_permissions = set(me.json()["data"]["permissions"])
    assert permission_code("settings", "manage") not in trading_permissions
    assert permission_code("suppliers", "verify") not in trading_permissions
    user_doc = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    assert user_doc is not None
    assert "is_platform_admin" not in user_doc
    assert "is_staff" not in user_doc

    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    assert platform is not None
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    assert role is not None
    now = utc_now()
    await mongo_manager.database["business_memberships"].insert_one(
        {
            "user_id": user_doc["_id"],
            "business_account_id": platform["_id"],
            "role_id": role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    switched = await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])}
    )
    assert switched.status_code == 200, switched.text
    platform_me = await client.get("/api/v1/auth/me")
    codes = set(platform_me.json()["data"]["permissions"])
    assert permission_code("settings", "manage") in codes
    assert permission_code("suppliers", "verify") in codes
    await client.post(
        "/api/v1/businesses/current/switch",
        json={"business_id": registered_user["business"]["id"]},
    )
    back = await client.get("/api/v1/auth/me")
    assert permission_code("settings", "manage") not in set(back.json()["data"]["permissions"])


@pytest.mark.asyncio
async def test_audit_registration_has_actor_and_no_secrets(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    logs = await mongo_manager.database["audit_logs"].find(
        {"action": "USER_REGISTERED", "resource_id": __import__("bson").ObjectId(registered_user["user"]["id"])}
    ).to_list(5)
    assert logs
    row = logs[0]
    assert row.get("user_id") is not None
    assert row.get("action") == "USER_REGISTERED"
    assert row.get("created_at") is not None
    blob = str(row.get("metadata") or {})
    assert "SecurePass123!" not in blob
    assert registered_user["verification_token"] not in blob
