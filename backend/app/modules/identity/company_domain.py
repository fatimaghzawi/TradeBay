"""Company email-domain helpers for organization-scoped identity."""

from __future__ import annotations

import re

_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)

# Public / consumer mail hosts are not valid company domains for TradeBay orgs.
_BLOCKED_PUBLIC_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "mail.com",
        "yandex.com",
        "gmx.com",
        "zoho.com",
    }
)


def normalize_email_domain(value: str | None) -> str | None:
    """Normalize a company domain (lowercase, strip @/whitespace). Empty → None."""
    if value is None:
        return None
    domain = value.strip().lower()
    if domain.startswith("@"):
        domain = domain[1:]
    if domain.startswith("www."):
        domain = domain[4:]
    domain = domain.rstrip(".")
    return domain or None


def email_local_domain(email: str | None) -> str | None:
    """Extract the domain part of an email address."""
    if not email or "@" not in email:
        return None
    _, _, domain = email.strip().lower().rpartition("@")
    return normalize_email_domain(domain)


def is_public_mailbox_domain(value: str | None) -> bool:
    """True for consumer mail hosts (gmail, outlook, …) — not company domains."""
    domain = normalize_email_domain(value)
    if domain is None and value and "@" in str(value):
        domain = email_local_domain(value)
    return bool(domain and domain in _BLOCKED_PUBLIC_DOMAINS)


def infer_company_email_domain(*emails: str | None) -> str | None:
    """Company domain from owner/contact mail, or None for personal inboxes."""
    for email in emails:
        domain = email_local_domain(email)
        if not domain or domain in _BLOCKED_PUBLIC_DOMAINS:
            continue
        try:
            return validate_company_email_domain(domain, required=True)
        except ValueError:
            continue
    return None


def validate_company_email_domain(value: str | None, *, required: bool = True) -> str | None:
    """
    Validate and normalize a company email domain.

    Raises ValueError with a user-facing message on invalid input.
    """
    domain = normalize_email_domain(value)
    if domain is None:
        if required:
            raise ValueError("Company email domain is required")
        return None
    if not _DOMAIN_RE.match(domain):
        raise ValueError("Enter a valid company domain (e.g. safawi.com)")
    if domain in _BLOCKED_PUBLIC_DOMAINS:
        raise ValueError(
            "Use your company domain, not a personal email provider "
            "(e.g. safawi.com instead of gmail.com)"
        )
    return domain


def email_matches_company_domain(email: str, company_domain: str | None) -> bool:
    """True when the email's domain equals the company's owned domain."""
    if not company_domain:
        return False
    return email_local_domain(email) == normalize_email_domain(company_domain)


def sanitize_mailbox_local_part(value: str) -> str:
    """Normalize a mailbox local-part for company login email generation."""
    local = value.strip().lower()
    local = re.sub(r"[^a-z0-9._+-]+", ".", local)
    local = re.sub(r"\.+", ".", local).strip(".")
    return local[:64]


def generate_company_login_email(
    *,
    personal_email: str,
    company_domain: str,
    company_email: str | None = None,
) -> str:
    """
    Resolve the TradeBay login identity for an invite.

    Prefer an explicit company email; otherwise generate
    `{personal-local-part}@{company_domain}`.
    """
    domain = validate_company_email_domain(company_domain, required=True)
    assert domain is not None
    if company_email and company_email.strip():
        normalized = company_email.lower().strip()
        if not email_matches_company_domain(normalized, domain):
            raise ValueError(
                f"Company login email must use the @{domain} company domain"
            )
        return normalized
    personal_local = sanitize_mailbox_local_part(
        (personal_email or "").split("@", 1)[0]
    )
    if not personal_local:
        raise ValueError("Enter a personal email so we can generate a company login email")
    return f"{personal_local}@{domain}"

