"""Company email-domain helpers."""

from app.modules.identity.company_domain import (
    email_local_domain,
    email_matches_company_domain,
    normalize_email_domain,
    validate_company_email_domain,
)


def test_normalize_and_extract_domain() -> None:
    assert normalize_email_domain(" @Safawi.COM ") == "safawi.com"
    assert normalize_email_domain("www.Safawi.com") == "safawi.com"
    assert email_local_domain("Fatima@Safawi.com") == "safawi.com"
    assert email_local_domain("bad") is None


def test_validate_rejects_public_mail_hosts() -> None:
    try:
        validate_company_email_domain("gmail.com")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "company domain" in str(exc).lower() or "personal" in str(exc).lower()


def test_infer_company_domain_skips_personal_inboxes() -> None:
    from app.modules.identity.company_domain import infer_company_email_domain

    assert infer_company_email_domain("fatima@gmail.com") is None
    assert infer_company_email_domain("fatima@outlook.com", "ops@safawi.com") == "safawi.com"
    assert infer_company_email_domain("ada@example.com") == "example.com"


def test_generate_company_login_email() -> None:
    from app.modules.identity.company_domain import generate_company_login_email

    assert (
        generate_company_login_email(
            personal_email="Fatima.G@gmail.com",
            company_domain="safawi.com",
        )
        == "fatima.g@safawi.com"
    )
    assert (
        generate_company_login_email(
            personal_email="fatima@gmail.com",
            company_domain="safawi.com",
            company_email="sales@safawi.com",
        )
        == "sales@safawi.com"
    )
    try:
        generate_company_login_email(
            personal_email="fatima@gmail.com",
            company_domain="safawi.com",
            company_email="fatima@other.com",
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_email_matches_company_domain() -> None:
    assert email_matches_company_domain("fatima@safawi.com", "safawi.com")
    assert not email_matches_company_domain("fatima@gmail.com", "safawi.com")
    assert not email_matches_company_domain("fatima@othercompany.com", "safawi.com")
    assert not email_matches_company_domain("fatima@safawi.com", None)
