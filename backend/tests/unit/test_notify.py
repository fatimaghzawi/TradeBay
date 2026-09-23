"""Personal-inbox routing for business event emails."""

from bson import ObjectId

from app.modules.identity.email import outbound_email_is_remote
from app.modules.trust.notify import _default_cta, _personal_inbox


def test_personal_inbox_prefers_stored_personal_email() -> None:
    to = _personal_inbox(
        {
            "email": "karim@levantwholesale.com",
            "personal_email": "karim.personal@gmail.com",
        },
        invite_delivery={},
        company_contact="sales@levantwholesale.com",
    )
    assert to == "karim.personal@gmail.com"


def test_personal_inbox_uses_invitation_delivery_when_personal_missing() -> None:
    to = _personal_inbox(
        {"email": "nora@levantwholesale.com"},
        invite_delivery={"nora@levantwholesale.com": "nora.khoury@gmail.com"},
        company_contact="sales@levantwholesale.com",
    )
    assert to == "nora.khoury@gmail.com"


def test_personal_inbox_allows_owner_when_login_is_company_contact() -> None:
    to = _personal_inbox(
        {"email": "sales@levantwholesale.com"},
        invite_delivery={},
        company_contact="sales@levantwholesale.com",
    )
    assert to == "sales@levantwholesale.com"


def test_personal_inbox_falls_back_to_login_when_not_company_contact() -> None:
    to = _personal_inbox(
        {"email": "nora@levantwholesale.com"},
        invite_delivery={},
        company_contact="sales@levantwholesale.com",
    )
    assert to == "nora@levantwholesale.com"


def test_default_cta_deep_links_orders_and_finance() -> None:
    oid = ObjectId()
    assert _default_cta("order", oid) == f"/procurement/orders/{oid}"
    assert _default_cta("invoice", oid) == "/finance"
    assert _default_cta("shipment", oid) == f"/procurement/shipments/{oid}"
    assert _default_cta("supplier_verification", oid) == "/admin/suppliers"
    assert _default_cta("invitation", oid) == "/accept-invitation"
    assert _default_cta("membership", oid) == "/members"
    assert _default_cta(None, None) == "/notifications"


def test_local_email_sender_is_not_elastic() -> None:
    assert outbound_email_is_remote() is False


def test_rfq_events_do_not_email() -> None:
    from app.modules.trust.notify import _email_event

    assert _email_event("RFQ_INVITATION") is False
    assert _email_event("QUOTE_RECEIVED") is False
    assert _email_event("QUOTATION_ACCEPTED") is False
    assert _email_event("NEGOTIATION_OFFER") is False
    assert _email_event("CONVERSATION_MESSAGE") is False
    assert _email_event("ORDER_CREATED") is True


def test_elastic_quota_exhausted_detects_trial_credits() -> None:
    from app.modules.identity.email import elastic_quota_exhausted

    body = (
        '{"Error":"You have used all your free daily email credits. '
        'Upgrade your account to an unlimited billing plan to continue sending email.",'
        '"MessageID":"no_credits_for_campaign_on_trial_plan"}'
    )
    assert elastic_quota_exhausted(400, body) is True
    assert elastic_quota_exhausted(500, body) is False
    assert elastic_quota_exhausted(400, "invalid recipient") is False
