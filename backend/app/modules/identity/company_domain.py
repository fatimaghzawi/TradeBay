
from __future__ import annotations

import re

_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)

                                                                               
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
    if not email or "@" not in email:
        return None
    _, _, domain = email.strip().lower().rpartition("@")
    return normalize_email_domain(domain)

def is_public_mailbox_domain(value: str | None) -> bool:
    domain = normalize_email_domain(value)
    if domain is None and value and "@" in str(value):
        domain = email_local_domain(value)
    return bool(domain and domain in _BLOCKED_PUBLIC_DOMAINS)

def infer_company_email_domain(*emails: str | None) -> str | None:
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
    if not company_domain:
        return False
    return email_local_domain(email) == normalize_email_domain(company_domain)

def sanitize_mailbox_local_part(value: str) -> str:
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

