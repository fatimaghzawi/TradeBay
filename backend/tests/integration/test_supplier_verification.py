
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from app.db.mongodb import mongo_manager
from app.modules.identity import storage
from app.modules.identity.constants import SYSTEM_ROLE_PLATFORM_ADMIN, MembershipStatus
from app.modules.identity.email import MemoryEmailSender
from app.shared.utils.datetime import utc_now
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
DOC_TYPES = ("commercial_registration", "tax_certificate", "address_proof")

@pytest.fixture(autouse=True)
def _isolated_verification_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "VERIFICATION_DIR", tmp_path / "verification")

async def _register_supplier(client: AsyncClient, inbox: MemoryEmailSender) -> dict[str, Any]:
    email = f"sup_{os.urandom(4).hex()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Sam",
            "last_name": "Supplier",
            "business_name": "Cedar Supplies",
            "business_type": "supplier",
        },
    )
    assert response.status_code == 200, response.text
    token = inbox.last_token(to=email, template="email_verification")
    verified = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200, verified.text
    return {"email": email, "business_id": response.json()["data"]["business"]["id"]}

async def _upload(client: AsyncClient, business_id: str, doc_type: str, data: bytes) -> Any:
    return await client.post(
        f"/api/v1/businesses/{business_id}/verification/documents/{doc_type}",
        files={"file": (f"{doc_type}.pdf", data, "application/pdf")},
    )

async def _submit_all(client: AsyncClient, business_id: str) -> Any:
    documents = []
    for doc_type in DOC_TYPES:
        uploaded = await _upload(client, business_id, doc_type, PDF_BYTES)
        assert uploaded.status_code == 200, uploaded.text
        documents.append({**uploaded.json()["data"], "document_type": doc_type})
    return await client.post(
        f"/api/v1/businesses/{business_id}/verification/submit",
        json={"documents": documents},
    )

async def _platform_admin(app: Any, inbox: MemoryEmailSender) -> AsyncClient:
    admin = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"staff_{os.urandom(4).hex()}@example.com"
    await admin.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Pat",
            "last_name": "Staff",
            "business_name": "Staff Co",
        },
    )
    token = inbox.last_token(to=email, template="email_verification")
    await admin.post("/api/v1/auth/verify-email", json={"token": token})
    user_doc = await mongo_manager.database["users"].find_one({"email": email})
    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
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
    await admin.post("/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])})
    return admin

@pytest.mark.asyncio
async def test_upload_rejects_files_that_are_not_documents(
    client: AsyncClient, email_inbox: MemoryEmailSender
) -> None:
    supplier = await _register_supplier(client, email_inbox)
    fake = await _upload(client, supplier["business_id"], "tax_certificate", b"<html>hi</html>")
    assert fake.status_code == 400, fake.text

@pytest.mark.asyncio
async def test_revoked_supplier_can_resubmit_and_keeps_evidence(
    client: AsyncClient, app: Any, email_inbox: MemoryEmailSender
) -> None:
    supplier = await _register_supplier(client, email_inbox)
    business_id = supplier["business_id"]
    submitted = await _submit_all(client, business_id)
    assert submitted.status_code == 200, submitted.text

    admin = await _platform_admin(app, email_inbox)
    try:
        approved = await admin.post(
            f"/api/v1/platform/suppliers/{business_id}/review", json={"decision": "approve"}
        )
        assert approved.status_code == 200, approved.text
        again = await admin.post(
            f"/api/v1/platform/suppliers/{business_id}/review", json={"decision": "approve"}
        )
        assert again.status_code == 409, again.text

        locked = await _upload(client, business_id, "tax_certificate", PDF_BYTES)
        assert locked.status_code == 403, locked.text
        folder = storage.VERIFICATION_DIR / business_id
        assert len(list(folder.glob("*"))) == len(DOC_TYPES)

        revoked = await admin.post(
            f"/api/v1/platform/suppliers/{business_id}/review",
            json={"decision": "revoke", "reason": "Expired registration"},
        )
        assert revoked.status_code == 200, revoked.text
    finally:
        await admin.aclose()

    business = await mongo_manager.database["business_accounts"].find_one(
        {"_id": ObjectId(business_id)}
    )
    assert business is not None
    assert business["status"] == "pending"
    resubmitted = await _submit_all(client, business_id)
    assert resubmitted.status_code == 200, resubmitted.text
    profile = await mongo_manager.database["supplier_profiles"].find_one(
        {"business_account_id": ObjectId(business_id)}
    )
    assert profile is not None
    assert profile["verification_status"] == "pending"
