
import pytest
from app.core.exceptions import RateLimitError
from app.modules.identity.dependencies import assert_email_verified
from app.modules.identity.exceptions import AccountInactiveError, EmailUnverifiedError, PrivilegeEscalationError
from app.modules.identity.password import validate_password
from app.modules.identity.rate_limit import SlidingWindowLimiter


def test_validate_password_accepts_mixed() -> None:
    assert validate_password("SecurePass123!") == "SecurePass123!"

def test_validate_password_rejects_weak() -> None:
    with pytest.raises(ValueError):
        validate_password("short")
    with pytest.raises(ValueError):
        validate_password("NoDigitsHere")
    with pytest.raises(ValueError):
        validate_password("12345678")

def test_assert_email_verified_gate() -> None:
    with pytest.raises(EmailUnverifiedError):
        assert_email_verified({"email_verified_at": None, "status": "pending"})
    with pytest.raises(AccountInactiveError):
        assert_email_verified({"email_verified_at": "2026-01-01T00:00:00Z", "status": "suspended"})
    assert_email_verified({"email_verified_at": "2026-01-01T00:00:00Z", "status": "active"})

def test_challenge_limiter() -> None:
    limiter = SlidingWindowLimiter(max_hits=2, window_seconds=60)
    limiter.hit("a")
    limiter.hit("a")
    with pytest.raises(RateLimitError):
        limiter.hit("a")
    limiter.hit("b")

def test_verified_supplier_can_keep_identity_and_change_contact_fields() -> None:
    from app.modules.identity.service import verified_supplier_identity_changes

    business = {
        "name": "Levant Wholesale",
        "legal_name": "Levant Wholesale SARL",
        "tax_number": "VAT-123",
        "email_domain": "levantwholesale.com",
        "address": {
            "street": "Hamra Street",
            "city": "Beirut",
            "governorate": "Beirut",
            "postal_code": "1107",
            "country": "Lebanon",
        },
    }
    assert verified_supplier_identity_changes(
        business,
        name="Levant Wholesale",
        legal_name="Levant Wholesale SARL",
        tax_number="VAT-123",
        email_domain="levantwholesale.com",
        address=business["address"],
    ) == []

def test_verified_supplier_identity_change_is_detected() -> None:
    from app.modules.identity.service import verified_supplier_identity_changes

    business = {"name": "Levant Wholesale", "legal_name": "Levant SARL"}
    assert verified_supplier_identity_changes(business, name="New Name") == ["name"]
    assert verified_supplier_identity_changes(business, legal_name="Other SARL") == [
        "legal_name"
    ]

@pytest.mark.asyncio
async def test_permission_subset_comparison() -> None:
    from app.modules.identity.directory import DirectoryService

    directory = DirectoryService()
    await directory.assert_subset(actor_permissions={"A", "B", "C"}, requested={"A", "B"})
    with pytest.raises(PrivilegeEscalationError):
        await directory.assert_subset(actor_permissions={"A", "B", "C"}, requested={"A", "B", "D"})

def test_company_member_avatar_uses_business_logo() -> None:
    from app.modules.identity.directory import _company_member_avatar

    user = {"avatar_url": "/personal.png"}
    assert _company_member_avatar(user, "/company.png") == "/company.png"
    assert _company_member_avatar(user, None) == "/personal.png"
    assert _company_member_avatar(None, "/company.png") == "/company.png"
    assert _company_member_avatar(None, None) is None

def test_public_company_omits_tax_and_contacts() -> None:
    from app.modules.identity.service import _serialize_public_company
    from bson import ObjectId

    payload = _serialize_public_company(
        {
            "_id": ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa"),
            "name": "Safawi Foods",
            "type": "buyer",
            "status": "verified",
            "legal_name": "Safawi Foods SAL",
            "tax_number": "VAT-999",
            "contact_email": "secret@safawi.com",
            "contact_phone": "+961111",
            "logo_url": "/logo.png",
            "description": "Buyer of dry goods",
            "website": "https://safawi.com",
            "address": {
                "street": "Hidden Street",
                "city": "Tripoli",
                "governorate": "North",
                "postal_code": "1300",
                "country": "Lebanon",
            },
        }
    )
    assert payload["name"] == "Safawi Foods"
    assert payload["address"] == {
        "city": "Tripoli",
        "governorate": "North",
        "country": "Lebanon",
    }
    assert "tax_number" not in payload
    assert "contact_email" not in payload
    assert "contact_phone" not in payload
    assert "verification_documents" not in payload
