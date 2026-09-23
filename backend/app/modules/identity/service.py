"""Identity application services.

- ``AuthService`` — register, login, sessions, email verify, password flows
- ``BusinessService`` — create/update companies, supplier verification

Routers call these; they call repositories. No FastAPI types here.
"""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_otp_code,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.seed import seed_trading_roles
from app.db.transactions import run_in_transaction
from app.modules.identity.auth_cache import invalidate_session_auth
from app.modules.identity.constants import (
    AUTH_TOKEN_MAX_ATTEMPTS,
    EMAIL_OTP_LENGTH,
    EMAIL_VERIFY_TTL_MINUTES,
    PASSWORD_RESET_TTL_MINUTES,
    REQUIRED_SUPPLIER_DOCUMENT_TYPES,
    SYSTEM_ROLE_BUSINESS_ADMIN,
    VERIFICATION_TRANSITIONS,
    AuthTokenPurpose,
    BusinessAccountStatus,
    BusinessAccountType,
    InvitationStatus,
    MembershipStatus,
    SupplierVerificationStatus,
    UserStatus,
    is_business_operational,
)
from app.modules.identity.email import get_email_sender
from app.modules.identity.exceptions import (
    AccountInactiveError,
    BusinessAlreadyExistsError,
    BusinessInactiveError,
    CompanyDomainTakenError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvitationInvalidError,
    MembershipRequiredError,
    OtpAttemptsExceededError,
    SessionRevokedError,
    VerifiedBusinessLockedError,
)
from app.modules.identity.guards import assert_not_last_admin
from app.modules.identity.rate_limit import challenge_limiter
from app.modules.identity.repository import (
    AuthTokenRepository,
    BusinessRepository,
    InvitationRepository,
    MembershipRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    SessionRepository,
    SupplierProfileRepository,
    UserRepository,
)
from app.shared.events.bus import USER_REGISTERED, DomainEvent, event_bus
from app.shared.repositories.base import MongoSession
from app.shared.services.audit import AuditService
from app.shared.utils.datetime import as_utc, utc_now
from app.shared.utils.objectid import parse_object_id

logger = get_logger(__name__)


# ── Response serializers (dict → API-safe payload) ───────────────────────────


def _serialize_user(doc: dict[str, Any], *, company_logo_url: str | None = None) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "status": doc["status"],
        "avatar_url": company_logo_url or doc.get("avatar_url"),
        "email_verified_at": doc.get("email_verified_at"),
    }


def _serialize_address(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    return {
        "street": doc.get("street") or doc.get("line1"),
        "city": doc.get("city"),
        "district": doc.get("district"),
        "governorate": doc.get("governorate") or doc.get("state"),
        "postal_code": doc.get("postal_code"),
        "country": doc.get("country"),
    }


def _norm_identity_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_identity_address(address: dict[str, Any] | None) -> tuple[str, ...]:
    addr = address if isinstance(address, dict) else {}
    return (
        _norm_identity_text(addr.get("street") or addr.get("line1")),
        _norm_identity_text(addr.get("city")),
        _norm_identity_text(addr.get("district")),
        _norm_identity_text(addr.get("governorate") or addr.get("state")),
        _norm_identity_text(addr.get("postal_code")),
        _norm_identity_text(addr.get("country") or "Lebanon").lower(),
    )


def verified_supplier_identity_changes(
    business: dict[str, Any],
    *,
    name: str | None = None,
    legal_name: str | None = None,
    tax_number: str | None = None,
    email_domain: str | None = None,
    address: dict[str, Any] | None = None,
) -> list[str]:
    """Return locked identity fields that would actually change."""
    changed: list[str] = []
    if name is not None and _norm_identity_text(name) != _norm_identity_text(business.get("name")):
        changed.append("name")
    if legal_name is not None and _norm_identity_text(legal_name) != _norm_identity_text(
        business.get("legal_name")
    ):
        changed.append("legal_name")
    if tax_number is not None and _norm_identity_text(tax_number) != _norm_identity_text(
        business.get("tax_number")
    ):
        changed.append("tax_number")
    if email_domain is not None and _norm_identity_text(email_domain).lstrip("@").lower() != (
        _norm_identity_text(business.get("email_domain")).lstrip("@").lower()
    ):
        changed.append("email_domain")
    stored_address = business.get("address") if isinstance(business.get("address"), dict) else None
    if address is not None and _norm_identity_address(address) != _norm_identity_address(stored_address):
        changed.append("address")
    return changed


def _serialize_business(
    doc: dict[str, Any],
    *,
    verification_status: str | None = None,
    verification_documents: list[dict[str, Any]] | None = None,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "type": doc["type"],
        "status": doc["status"],
        "legal_name": doc.get("legal_name"),
        "tax_number": doc.get("tax_number"),
        "contact_email": doc.get("contact_email"),
        "contact_phone": doc.get("contact_phone"),
        "email_domain": doc.get("email_domain"),
        "logo_url": doc.get("logo_url"),
        "cover_url": doc.get("cover_url"),
        "address": _serialize_address(doc.get("address") if isinstance(doc.get("address"), dict) else None),
        "description": doc.get("description"),
        "website": doc.get("website"),
        "year_established": doc.get("year_established"),
        "company_size": doc.get("company_size"),
        "industry_categories": doc.get("industry_categories") or [],
        "business_tags": doc.get("business_tags") or [],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if verification_status is not None:
        payload["verification_status"] = verification_status
    if verification_documents is not None:
        payload["verification_documents"] = verification_documents
    if rejection_reason is not None:
        payload["rejection_reason"] = rejection_reason
    return payload


def _serialize_verification_documents(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not profile:
        return []
    rows: list[dict[str, Any]] = []
    for item in profile.get("documents") or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str) and url.startswith("pending:"):
            url = None
        rows.append(
            {
                "document_type": item.get("document_type"),
                "file_name": item.get("file_name"),
                "url": url,
                "uploaded_at": item.get("uploaded_at"),
            }
        )
    return rows


async def _serialize_business_enriched(
    doc: dict[str, Any],
    *,
    profiles: SupplierProfileRepository | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verification_status: str | None = None
    verification_documents: list[dict[str, Any]] | None = None
    rejection_reason: str | None = None
    if doc.get("type") == BusinessAccountType.SUPPLIER:
        resolved = profile
        if resolved is None:
            repo = profiles or SupplierProfileRepository()
            resolved = await repo.get_by_business(doc["_id"])
        verification_status = (
            str(resolved["verification_status"])
            if resolved and resolved.get("verification_status")
            else SupplierVerificationStatus.UNVERIFIED
        )
        verification_documents = _serialize_verification_documents(resolved)
        if resolved and resolved.get("rejection_reason"):
            rejection_reason = str(resolved["rejection_reason"])
    return _serialize_business(
        doc,
        verification_status=verification_status,
        verification_documents=verification_documents,
        rejection_reason=rejection_reason,
    )


def _serialize_public_company(
    doc: dict[str, Any],
    *,
    verification_status: str | None = None,
) -> dict[str, Any]:
    """Counterparty-facing company card — no tax, contacts, or verification files."""
    raw_address = doc.get("address") if isinstance(doc.get("address"), dict) else None
    address: dict[str, Any] | None = None
    if raw_address:
        city = raw_address.get("city")
        governorate = raw_address.get("governorate") or raw_address.get("state")
        country = raw_address.get("country")
        if city or governorate or country:
            address = {
                "city": city,
                "governorate": governorate,
                "country": country,
            }
    payload: dict[str, Any] = {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "type": doc["type"],
        "status": doc["status"],
        "legal_name": doc.get("legal_name"),
        "logo_url": doc.get("logo_url"),
        "cover_url": doc.get("cover_url"),
        "description": doc.get("description"),
        "website": doc.get("website"),
        "year_established": doc.get("year_established"),
        "company_size": doc.get("company_size"),
        "industry_categories": doc.get("industry_categories") or [],
        "business_tags": doc.get("business_tags") or [],
        "address": address,
    }
    if verification_status is not None:
        payload["verification_status"] = verification_status
    return payload


# ── AuthService — authentication & sessions ──────────────────────────────────


class AuthService:
    """Register / login / logout / refresh / current user foundation."""

    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        sessions: SessionRepository | None = None,
        businesses: BusinessRepository | None = None,
        memberships: MembershipRepository | None = None,
        roles: RoleRepository | None = None,
        permissions: PermissionRepository | None = None,
        role_permissions: RolePermissionRepository | None = None,
        auth_tokens: AuthTokenRepository | None = None,
        invitations: InvitationRepository | None = None,
        supplier_profiles: SupplierProfileRepository | None = None,
        audit: AuditService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.sessions = sessions or SessionRepository()
        self.businesses = businesses or BusinessRepository()
        self.memberships = memberships or MembershipRepository()
        self.roles = roles or RoleRepository()
        self.permissions = permissions or PermissionRepository()
        self.role_permissions = role_permissions or RolePermissionRepository()
        self.auth_tokens = auth_tokens or AuthTokenRepository()
        self.invitations = invitations or InvitationRepository()
        self.supplier_profiles = supplier_profiles or SupplierProfileRepository()
        self.audit = audit or AuditService()
        self.settings = settings or get_settings()

    # —— Register / login / logout / refresh ————————————————————————————————

    async def register(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        business_name: str | None = None,
        business_type: str | None = None,
        invitation_token: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        normalized = email.lower().strip()
        existing = await self.users.get_by_email(normalized)
        if existing is not None:
            if invitation_token:
                raise EmailAlreadyRegisteredError()
            return await self._resume_unverified_registration(
                existing=existing,
                password=password,
                first_name=first_name,
                last_name=last_name,
                business_name=business_name,
                business_type=business_type,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # Invitee signup: join an existing company — never create a trading business here.
        # Company login emails are often not real mailboxes; the invitation link (delivered
        # to the personal delivery_email) is the proof of identity instead of OTP.
        via_invitation = False
        personal_email: str | None = None
        if invitation_token:
            invitation = await self.invitations.get_by_token_hash(hash_token(invitation_token))
            now_check = utc_now()
            if invitation is None:
                raise InvitationInvalidError("Invitation link is invalid")
            if invitation.get("status") == InvitationStatus.REVOKED:
                raise InvitationInvalidError(
                    "This invitation was revoked. Ask an admin for a new invite."
                )
            if invitation.get("status") == InvitationStatus.DECLINED:
                raise InvitationInvalidError("This invitation was declined.")
            if invitation.get("status") == InvitationStatus.ACCEPTED:
                raise InvitationInvalidError("This invitation was already accepted.")
            if invitation.get("status") == InvitationStatus.EXPIRED or (
                invitation.get("status") == InvitationStatus.PENDING
                and as_utc(invitation["expires_at"]) < now_check
            ):
                if invitation.get("status") == InvitationStatus.PENDING:
                    await self.invitations.update(
                        invitation["_id"],
                        {"status": InvitationStatus.EXPIRED, "updated_at": now_check},
                    )
                raise InvitationInvalidError(
                    "This invitation has expired. Ask an admin to resend it."
                )
            if invitation.get("status") != InvitationStatus.PENDING:
                raise InvitationInvalidError()
            if invitation["invited_email"].lower().strip() != normalized:
                raise InvitationInvalidError(
                    "Register with the company login email on this invitation"
                )
            business = await self.businesses.get_by_id(invitation["business_account_id"])
            if business is None:
                raise InvitationInvalidError("This company is no longer available")
            business_name = None
            business_type = None
            personal_email = (invitation.get("delivery_email") or "").strip().lower() or None
            via_invitation = True

        now = utc_now()
        user = await self.users.create(
            {
                "email": normalized,
                "personal_email": personal_email or normalized,
                "password_hash": hash_password(password),
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "phone": None,
                "status": UserStatus.ACTIVE if via_invitation else UserStatus.PENDING,
                "email_verified_at": now if via_invitation else None,
                "created_at": now,
                "updated_at": now,
            }
        )
        email_task: asyncio.Task[Any] | None = None
        if not via_invitation:
            raw_verify = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFICATION)
            email_task = asyncio.create_task(
                get_email_sender().send(
                    to=normalized,
                    template="email_verification",
                    context={"user_id": str(user["_id"]), "token": raw_verify, "otp": raw_verify},
                )
            )

        account_type = BusinessAccountType.BUYER
        if business_type == BusinessAccountType.SUPPLIER:
            account_type = BusinessAccountType.SUPPLIER

        business: dict[str, Any] | None = None
        try:
            if business_name:
                business = await self._create_business_with_admin(
                    name=business_name.strip(),
                    owner_user_id=user["_id"],
                    account_type=account_type,
                    contact_email=normalized,
                    owner_email=normalized,
                )

            tokens = await self._issue_session(
                user=user,
                business_account_id=business["_id"] if business else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            await self.audit.log(
                action="USER_REGISTERED",
                resource_type="user",
                resource_id=user["_id"],
                business_account_id=business["_id"] if business else None,
                user_id=user["_id"],
                ip_address=ip_address,
                metadata={
                    "via_invitation": via_invitation,
                    "email_verified_via": "invitation" if via_invitation else None,
                },
            )
            await event_bus.publish(DomainEvent(name=USER_REGISTERED, payload={"user_id": str(user["_id"])}))
        finally:
            if email_task is not None:
                try:
                    await email_task
                except Exception:
                    # Account exists; verification can be resent. Don't fail registration on provider blips.
                    logger.exception("verification_email_failed", email=normalized)

        return {
            "user": _serialize_user(user),
            "business": _serialize_business(business) if business else None,
            **tokens,
        }

    async def _resume_unverified_registration(
        self,
        *,
        existing: dict[str, Any],
        password: str,
        first_name: str,
        last_name: str,
        business_name: str | None,
        business_type: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        """Retry signup when the account exists but the inbox was never verified.

        A failed first OTP must not permanently lock the email. Verified accounts
        still raise EmailAlreadyRegisteredError.
        """
        if existing.get("email_verified_at") or existing.get("status") != UserStatus.PENDING:
            raise EmailAlreadyRegisteredError()

        now = utc_now()
        user = await self.users.update(
            existing["_id"],
            {
                "password_hash": hash_password(password),
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "updated_at": now,
            },
        )
        if user is None:
            raise EmailAlreadyRegisteredError()

        challenge_limiter.hit(f"email_verification_email:{user['email']}")
        raw_verify = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFICATION)
        inbox = (user.get("personal_email") or user["email"]).strip().lower()
        email_task = asyncio.create_task(
            get_email_sender().send(
                to=inbox,
                template="email_verification",
                context={"user_id": str(user["_id"]), "token": raw_verify, "otp": raw_verify},
            )
        )

        business: dict[str, Any] | None = None
        memberships = await self.memberships.list_for_user(user["_id"])
        for membership in memberships:
            candidate = await self.businesses.get_by_id(membership["business_account_id"])
            if candidate and candidate.get("type") != BusinessAccountType.PLATFORM:
                business = candidate
                break

        account_type = BusinessAccountType.BUYER
        if business_type == BusinessAccountType.SUPPLIER:
            account_type = BusinessAccountType.SUPPLIER

        try:
            if business is None and business_name:
                business = await self._create_business_with_admin(
                    name=business_name.strip(),
                    owner_user_id=user["_id"],
                    account_type=account_type,
                    contact_email=user["email"],
                    owner_email=user["email"],
                )

            tokens = await self._issue_session(
                user=user,
                business_account_id=business["_id"] if business else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await self.audit.log(
                action="USER_REGISTERED",
                resource_type="user",
                resource_id=user["_id"],
                business_account_id=business["_id"] if business else None,
                user_id=user["_id"],
                ip_address=ip_address,
                metadata={"resumed_unverified": True},
            )
        finally:
            try:
                await email_task
            except Exception:
                logger.exception("verification_email_failed", email=inbox)

        return {
            "user": _serialize_user(user),
            "business": _serialize_business(business) if business else None,
            **tokens,
        }

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        user = await self.users.get_by_email(email.lower().strip())
        if user is None or not verify_password(password, user["password_hash"]):
            raise InvalidCredentialsError()
        if user["status"] not in {UserStatus.ACTIVE, UserStatus.PENDING}:
            raise AccountInactiveError()

        memberships = await self.memberships.list_for_user(user["_id"])
        active_business_id = None
        if memberships:
            active_business_id = memberships[0]["business_account_id"]

        tokens = await self._issue_session(
            user=user,
            business_account_id=active_business_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.audit.log(
            action="USER_LOGIN",
            resource_type="user",
            resource_id=user["_id"],
            business_account_id=active_business_id,
            user_id=user["_id"],
            ip_address=ip_address,
        )
        return {"user": _serialize_user(user), **tokens}

    async def logout(
        self, *, session_id: str, user_id: str | None = None, ip_address: str | None = None
    ) -> None:
        session = await self.sessions.revoke(session_id, utc_now())
        invalidate_session_auth(session_id)
        await self.audit.log(
            action="USER_LOGOUT",
            resource_type="session",
            resource_id=session_id,
            business_account_id=session.get("active_business_account_id") if session else None,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        session = await self.sessions.get_by_refresh_hash(hash_token(raw_refresh_token))
        if session is None:
            raise SessionRevokedError()
        if session.get("revoked_at") is not None:
            raise SessionRevokedError()
        if as_utc(session["expires_at"]) < utc_now():
            raise SessionRevokedError()

        user = await self.users.get_by_id(session["user_id"])
        if user is None or user["status"] not in {UserStatus.ACTIVE, UserStatus.PENDING}:
            raise AccountInactiveError()

        claimed = await self.sessions.revoke_if_active(session["_id"], utc_now())
        if claimed is None:
            raise SessionRevokedError()
        tokens = await self._issue_session(
            user=user,
            business_account_id=session.get("active_business_account_id"),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.audit.log(
            action="SESSION_REFRESHED",
            resource_type="session",
            resource_id=tokens["session_id"],
            business_account_id=session.get("active_business_account_id"),
            user_id=user["_id"],
            ip_address=ip_address,
        )
        return {"user": _serialize_user(user), **tokens}

    # —— Profile / me ——————————————————————————————————————————————————————

    async def get_me(self, *, user_id: str, session: dict[str, Any]) -> dict[str, Any]:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()

        active_business = None
        membership = None
        role_name = None
        permission_codes: list[str] = []

        business_id = session.get("active_business_account_id")
        if business_id:
            business_doc = await self.businesses.get_by_id(business_id)
            if business_doc:
                active_business = await _serialize_business_enriched(
                    business_doc, profiles=self.supplier_profiles
                )
            membership_doc = await self.memberships.get_active_membership(user_id, business_id)
            if membership_doc:
                membership = {
                    "id": str(membership_doc["_id"]),
                    "business_account_id": str(membership_doc["business_account_id"]),
                    "role_id": str(membership_doc["role_id"]),
                    "status": membership_doc["status"],
                }
                role = await self.roles.get_by_id(membership_doc["role_id"])
                if role:
                    role_name = role["name"]
                    permission_codes = await self._permission_codes_for_role(role["_id"])

        return {
            "user": _serialize_user(
                user,
                company_logo_url=(active_business or {}).get("logo_url"),
            ),
            "active_business": active_business,
            "membership": membership,
            "role_name": role_name,
            "permissions": permission_codes,
        }

    # —— Email verification ————————————————————————————————————————————————

    async def verify_email(
        self,
        *,
        raw_token: str,
        email: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        token_row = await self._consume_auth_token(
            raw_token,
            AuthTokenPurpose.EMAIL_VERIFICATION,
            email=email,
        )
        now = utc_now()
        user = await self.users.update(
            token_row["user_id"],
            {"status": UserStatus.ACTIVE, "email_verified_at": now, "updated_at": now},
        )
        if user is None:
            raise InvalidCredentialsError()
        await self.audit.log(
            action="USER_EMAIL_VERIFIED",
            resource_type="user",
            resource_id=user["_id"],
            user_id=user["_id"],
            ip_address=ip_address,
        )
        return {"user": _serialize_user(user)}

    async def resend_verification(self, *, user_id: str) -> None:
        challenge_limiter.hit(f"email_verification:{user_id}")
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()
        if user.get("email_verified_at"):
            return
        raw = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFICATION)
        await get_email_sender().send(
            to=user["email"],
            template="email_verification",
            context={"user_id": str(user["_id"]), "token": raw, "otp": raw},
        )

    # —— Password reset / change ————————————————————————————————————————————

    async def request_password_reset(self, *, email: str) -> None:
        normalized = email.lower().strip()
        challenge_limiter.hit(f"password_reset:{normalized}")
        user = await self.users.get_by_email(normalized)
        if user is None:
            return
        if user["status"] in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
            return
        raw = await self._issue_auth_token(user["_id"], AuthTokenPurpose.PASSWORD_RESET)
        await get_email_sender().send(
            to=user["email"],
            template="password_reset",
            context={"user_id": str(user["_id"]), "token": raw, "otp": raw},
        )

    async def reset_password(
        self, *, raw_token: str, new_password: str, ip_address: str | None = None
    ) -> None:
        token_row = await self._require_open_auth_token(raw_token, AuthTokenPurpose.PASSWORD_RESET)
        now = utc_now()
        password_hash = hash_password(new_password)

        async def work(session: MongoSession) -> None:
            await self.auth_tokens.update(token_row["_id"], {"used_at": now}, session=session)
            await self.users.update(
                token_row["user_id"],
                {"password_hash": password_hash, "updated_at": now},
                session=session,
            )
            await self.sessions.revoke_all_for_user(token_row["user_id"], now, session=session)

        await run_in_transaction(work)
        await self.audit.log(
            action="USER_PASSWORD_RESET",
            resource_type="user",
            resource_id=token_row["user_id"],
            user_id=token_row["user_id"],
            ip_address=ip_address,
        )

    async def change_password(
        self,
        *,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
    ) -> None:
        user = await self.users.get_by_id(user_id)
        if user is None or not verify_password(current_password, user["password_hash"]):
            raise InvalidCredentialsError()
        now = utc_now()
        password_hash = hash_password(new_password)

        async def work(session: MongoSession) -> None:
            await self.users.update(
                user_id, {"password_hash": password_hash, "updated_at": now}, session=session
            )
            await self.sessions.revoke_all_for_user(user_id, now, session=session)

        await run_in_transaction(work)
        await self.audit.log(
            action="USER_PASSWORD_CHANGED",
            resource_type="user",
            resource_id=user_id,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def logout_all(
        self,
        *,
        user_id: str,
        current_session_id: str | None = None,
        include_current: bool = True,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        if include_current:
            revoked = await self.sessions.revoke_all_for_user(user_id, now)
        else:
            revoked = await self.sessions.revoke_all_for_user(
                user_id, now, except_session_id=current_session_id
            )
        invalidate_session_auth()
        await self.audit.log(
            action="USER_LOGOUT_ALL",
            resource_type="user",
            resource_id=user_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"revoked_count": revoked, "include_current": include_current},
        )
        return {"revoked": revoked}

    # —— Session list / revoke / profile update ——————————————————————————————

    async def list_sessions(self, *, user_id: str, current_session_id: str) -> list[dict[str, Any]]:
        rows = await self.sessions.list_active_for_user(user_id)
        return [
            {
                "id": str(row["_id"]),
                "active_business_account_id": (
                    str(row["active_business_account_id"])
                    if row.get("active_business_account_id")
                    else None
                ),
                "ip_address": row.get("ip_address"),
                "user_agent": row.get("user_agent"),
                "last_used_at": row.get("last_used_at"),
                "created_at": row.get("created_at"),
                "expires_at": row.get("expires_at"),
                "is_current": str(row["_id"]) == current_session_id,
            }
            for row in rows
        ]

    async def revoke_session(
        self,
        *,
        user_id: str,
        session_id: str,
        ip_address: str | None = None,
    ) -> None:
        session = await self.sessions.get_by_id(session_id)
        if session is None or str(session["user_id"]) != user_id:
            raise SessionRevokedError()
        if session.get("revoked_at") is not None:
            return
        await self.sessions.revoke(session_id, utc_now())
        invalidate_session_auth(session_id)
        await self.audit.log(
            action="SESSION_REVOKED",
            resource_type="session",
            resource_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def update_profile(
        self,
        *,
        user_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {"updated_at": utc_now()}
        if first_name is not None:
            updates["first_name"] = first_name.strip()
        if last_name is not None:
            updates["last_name"] = last_name.strip()
        if len(updates) == 1:
            user = await self.users.get_by_id(user_id)
            if user is None:
                raise InvalidCredentialsError()
            return _serialize_user(user)
        user = await self.users.update(user_id, updates)
        if user is None:
            raise InvalidCredentialsError()
        return _serialize_user(user)

    async def resend_verification_for_email(self, *, email: str) -> None:
        """Public resend — always silent to avoid account enumeration."""
        normalized = email.lower().strip()
        challenge_limiter.hit(f"email_verification_email:{normalized}")
        user = await self.users.get_by_email(normalized)
        if user is None or user.get("email_verified_at"):
            return
        if user["status"] in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
            return
        raw = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFICATION)
        await get_email_sender().send(
            to=user["email"],
            template="email_verification",
            context={"user_id": str(user["_id"]), "token": raw, "otp": raw},
        )

    # —— Switch active business on the current session ——————————————————————

    async def switch_business(self, *, session_id: str, user_id: str, business_id: str) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None or not is_business_operational(str(business.get("status", ""))):
            raise BusinessInactiveError()
        session = await self.sessions.update(
            session_id,
            {"active_business_account_id": parse_object_id(business_id), "last_used_at": utc_now()},
        )
        if session is None:
            raise SessionRevokedError()
        invalidate_session_auth(session_id)
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()
        access = create_access_token(
            settings=self.settings,
            user_id=str(user["_id"]),
            session_id=str(session["_id"]),
            business_account_id=str(business["_id"]),
        )
        role = await self.roles.get_by_id(membership["role_id"])
        business_payload = await _serialize_business_enriched(
            business, profiles=self.supplier_profiles
        )
        business_payload["role_name"] = role["name"] if role else None
        return {
            "business": business_payload,
            "access_token": access,
            "access_token_expires_in_minutes": self.settings.access_token_expire_minutes,
        }

    # —— Private helpers (tokens, OTP, session issue, bootstrap company) ——————

    async def _issue_auth_token(self, user_id: ObjectId, purpose: AuthTokenPurpose) -> str:
        raw = generate_otp_code(length=EMAIL_OTP_LENGTH)
        if purpose == AuthTokenPurpose.EMAIL_VERIFICATION:
            ttl = timedelta(minutes=EMAIL_VERIFY_TTL_MINUTES)
        else:
            ttl = timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
        now = utc_now()
        await self.auth_tokens.invalidate_open(user_id, purpose, at=now)
        await self.auth_tokens.create(
            {
                "user_id": user_id,
                "purpose": purpose,
                "token_hash": hash_token(raw),
                "expires_at": now + ttl,
                "used_at": None,
                "invalidated_at": None,
                "attempts": 0,
                "created_at": now,
            }
        )
        return raw

    async def _require_open_auth_token(
        self,
        raw_token: str,
        purpose: AuthTokenPurpose,
        *,
        email: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        cleaned = raw_token.strip()
        row = await self.auth_tokens.get_by_hash(hash_token(cleaned))

        # Wrong OTP: hash miss. Attribute the attempt to the open challenge when email is known.
        if row is None:
            challenge = None
            if email:
                user = await self.users.get_by_email(email.lower().strip())
                if user is not None:
                    challenge = await self.auth_tokens.get_latest_open(user["_id"], purpose)
            if challenge is None:
                raise InvalidOtpError()
            return await self._register_failed_otp_attempt(challenge, now=now)

        attempts = int(row.get("attempts") or 0)
        if attempts >= AUTH_TOKEN_MAX_ATTEMPTS:
            raise OtpAttemptsExceededError(max_attempts=AUTH_TOKEN_MAX_ATTEMPTS)

        attempts += 1
        await self.auth_tokens.update(row["_id"], {"attempts": attempts})

        if (
            row.get("purpose") != purpose
            or row.get("used_at") is not None
            or row.get("invalidated_at") is not None
            or as_utc(row["expires_at"]) < now
        ):
            raise InvalidOtpError()
        return row

    async def _register_failed_otp_attempt(
        self, challenge: dict[str, Any], *, now: Any
    ) -> dict[str, Any]:
        attempts = int(challenge.get("attempts") or 0)
        if attempts >= AUTH_TOKEN_MAX_ATTEMPTS:
            raise OtpAttemptsExceededError(max_attempts=AUTH_TOKEN_MAX_ATTEMPTS)
        if as_utc(challenge["expires_at"]) < now:
            raise InvalidOtpError()

        attempts += 1
        await self.auth_tokens.update(challenge["_id"], {"attempts": attempts})
        if attempts >= AUTH_TOKEN_MAX_ATTEMPTS:
            raise OtpAttemptsExceededError(max_attempts=AUTH_TOKEN_MAX_ATTEMPTS)

        remaining = AUTH_TOKEN_MAX_ATTEMPTS - attempts
        raise InvalidOtpError(remaining=remaining, max_attempts=AUTH_TOKEN_MAX_ATTEMPTS)

    async def _consume_auth_token(
        self,
        raw_token: str,
        purpose: AuthTokenPurpose,
        *,
        email: str | None = None,
    ) -> dict[str, Any]:
        row = await self._require_open_auth_token(raw_token, purpose, email=email)
        await self.auth_tokens.update(row["_id"], {"used_at": utc_now()})
        return row

    async def _permission_codes_for_role(self, role_id: ObjectId) -> list[str]:
        permission_ids = await self.role_permissions.list_permission_ids_for_role(role_id)
        if not permission_ids:
            return []
        rows = await self.permissions.collection.find(
            {"_id": {"$in": list(permission_ids)}}
        ).to_list(length=500)
        return sorted({f"{row['resource']}.{row['action']}" for row in rows})

    async def provision_user_by_platform(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        actor_user_id: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Create an active, email-verified login account (no trading company)."""
        normalized = email.lower().strip()
        if await self.users.get_by_email(normalized):
            raise EmailAlreadyRegisteredError()

        now = utc_now()
        user = await self.users.create(
            {
                "email": normalized,
                "personal_email": normalized,
                "password_hash": hash_password(password),
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "phone": None,
                "status": UserStatus.ACTIVE,
                "email_verified_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="USER_PROVISIONED_BY_PLATFORM",
            resource_type="user",
            resource_id=user["_id"],
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "email": normalized,
                "actor_name": (
                    f"{actor.get('first_name', '')} {actor.get('last_name', '')}".strip()
                    if actor
                    else None
                ),
            },
        )
        await event_bus.publish(
            DomainEvent(name=USER_REGISTERED, payload={"user_id": str(user["_id"])})
        )
        return _serialize_user(user)

    async def provision_trading_account_by_platform(
        self,
        *,
        account_type: str,
        business_name: str,
        owner_email: str,
        owner_password: str,
        owner_first_name: str,
        owner_last_name: str,
        actor_user_id: str,
        email_domain: str | None = None,
        legal_name: str | None = None,
        tax_number: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        verify_supplier: bool = True,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Create a buyer/supplier company with an owner Business Admin."""
        from app.modules.identity.company_domain import (
            email_local_domain,
            email_matches_company_domain,
            validate_company_email_domain,
        )
        from app.modules.identity.exceptions import (
            CompanyDomainMismatchError,
            CompanyDomainRequiredError,
        )

        if account_type not in {BusinessAccountType.BUYER, BusinessAccountType.SUPPLIER}:
            raise ForbiddenError("account_type must be buyer or supplier")

        normalized_owner = owner_email.lower().strip()
        if await self.users.get_by_email(normalized_owner):
            raise EmailAlreadyRegisteredError()

        try:
            resolved_domain = validate_company_email_domain(
                email_domain or email_local_domain(normalized_owner),
                required=True,
            )
        except ValueError as exc:
            raise CompanyDomainRequiredError(str(exc)) from exc

        assert resolved_domain is not None
        if not email_matches_company_domain(normalized_owner, resolved_domain):
            raise CompanyDomainMismatchError(
                company_name=business_name.strip(),
                company_domain=resolved_domain,
            )

        existing_domain = await self.businesses.get_by_email_domain(resolved_domain)
        if existing_domain is not None:
            raise CompanyDomainTakenError(resolved_domain)

        now = utc_now()
        user = await self.users.create(
            {
                "email": normalized_owner,
                "personal_email": normalized_owner,
                "password_hash": hash_password(owner_password),
                "first_name": owner_first_name.strip(),
                "last_name": owner_last_name.strip(),
                "phone": None,
                "status": UserStatus.ACTIVE,
                "email_verified_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )

        contact = (contact_email or normalized_owner).lower().strip()
        business = await self._create_business_with_admin(
            name=business_name.strip(),
            owner_user_id=user["_id"],
            account_type=BusinessAccountType(account_type),
            legal_name=legal_name,
            tax_number=tax_number,
            contact_email=contact,
            contact_phone=contact_phone,
            email_domain=resolved_domain,
            owner_email=normalized_owner,
        )

        if (
            account_type == BusinessAccountType.SUPPLIER
            and verify_supplier
        ):
            profile = await self.supplier_profiles.get_by_business(business["_id"])
            if profile is not None:
                await self.supplier_profiles.update(
                    profile["_id"],
                    {
                        "verification_status": SupplierVerificationStatus.VERIFIED,
                        "verified_at": now,
                        "verified_by": parse_object_id(actor_user_id),
                        "rejection_reason": None,
                        "updated_at": now,
                    },
                )
                await self.businesses.update(
                    business["_id"],
                    {
                        "status": BusinessAccountStatus.VERIFIED,
                        "updated_at": now,
                    },
                )
                refreshed = await self.businesses.get_by_id(business["_id"])
                if refreshed is not None:
                    business = refreshed

        actor = await self.users.get_by_id(actor_user_id)
        actor_name = (
            f"{actor.get('first_name', '')} {actor.get('last_name', '')}".strip()
            if actor
            else None
        )
        await self.audit.log(
            action="TRADING_ACCOUNT_PROVISIONED_BY_PLATFORM",
            resource_type="business_account",
            resource_id=business["_id"],
            business_account_id=business["_id"],
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "account_type": account_type,
                "owner_user_id": str(user["_id"]),
                "owner_email": normalized_owner,
                "email_domain": resolved_domain,
                "supplier_verified": bool(
                    account_type == BusinessAccountType.SUPPLIER and verify_supplier
                ),
                "actor_name": actor_name,
            },
        )
        await event_bus.publish(
            DomainEvent(name=USER_REGISTERED, payload={"user_id": str(user["_id"])})
        )
        return {
            "user": _serialize_user(user),
            "business": await _serialize_business_enriched(
                business, profiles=self.supplier_profiles
            ),
        }

    async def _create_business_with_admin(
        self,
        *,
        name: str,
        owner_user_id: ObjectId,
        account_type: BusinessAccountType,
        legal_name: str | None = None,
        tax_number: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        email_domain: str | None = None,
        address: dict[str, Any] | None = None,
        owner_email: str | None = None,
    ) -> dict[str, Any]:
        from app.modules.identity.company_domain import (
            infer_company_email_domain,
            validate_company_email_domain,
        )
        from app.modules.identity.exceptions import CompanyDomainRequiredError

        now = utc_now()
        # Buyers are operational immediately. Suppliers stay pending until platform
        # staff approve verification documents (FR-BIZ-02 / FR-BIZ-04).
        initial_status = (
            BusinessAccountStatus.PENDING
            if account_type == BusinessAccountType.SUPPLIER
            else BusinessAccountStatus.VERIFIED
        )
        # Self-serve owners register with a personal inbox so they can receive OTP.
        # Only an explicit company domain (or a custom-domain mailbox) is stored.
        try:
            if email_domain and str(email_domain).strip():
                resolved_domain = validate_company_email_domain(email_domain, required=True)
            else:
                resolved_domain = infer_company_email_domain(contact_email, owner_email)
        except ValueError as exc:
            raise CompanyDomainRequiredError(str(exc)) from exc

        payload = {
            "name": name,
            "type": account_type,
            "status": initial_status,
            "legal_name": (legal_name or name).strip() if legal_name or name else name,
            "tax_number": tax_number,
            "contact_email": contact_email.lower().strip() if contact_email else None,
            "contact_phone": contact_phone.strip() if contact_phone else None,
            "email_domain": resolved_domain,
            "address": address,
            "created_at": now,
            "updated_at": now,
        }

        async def work(session: MongoSession) -> dict[str, Any]:
            business = await self.businesses.create(payload, session=session)
            roles = await seed_trading_roles(business["_id"], session=session, fresh=True)
            admin_role = roles[SYSTEM_ROLE_BUSINESS_ADMIN]
            await self.memberships.create(
                {
                    "user_id": owner_user_id,
                    "business_account_id": business["_id"],
                    "role_id": admin_role["_id"],
                    "status": MembershipStatus.ACTIVE,
                    "joined_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
                session=session,
            )
            await self.supplier_profiles.create(
                {
                    "business_account_id": business["_id"],
                    "verification_status": SupplierVerificationStatus.UNVERIFIED,
                    "documents": [],
                    "service_areas": [],
                    "rating_summary": {
                        "average_rating": 0.0,
                        "review_count": 0,
                        "last_reviewed_at": None,
                    },
                    "verified_at": None,
                    "verified_by": None,
                    "rejection_reason": None,
                    "created_at": now,
                    "updated_at": now,
                },
                session=session,
            )
            return business

        return await run_in_transaction(work)

    async def _issue_session(
        self,
        *,
        user: dict[str, Any],
        business_account_id: ObjectId | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        raw_refresh = generate_refresh_token()
        now = utc_now()
        expires_at = now + timedelta(days=self.settings.refresh_token_expire_days)
        session = await self.sessions.create(
            {
                "user_id": user["_id"],
                "active_business_account_id": business_account_id,
                "refresh_token_hash": hash_token(raw_refresh),
                "expires_at": expires_at,
                "revoked_at": None,
                "last_used_at": now,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": now,
            }
        )
        access = create_access_token(
            settings=self.settings,
            user_id=str(user["_id"]),
            session_id=str(session["_id"]),
            business_account_id=str(business_account_id) if business_account_id else None,
        )
        return {
            "access_token": access,
            "refresh_token": raw_refresh,
            "session_id": str(session["_id"]),
            "access_token_expires_in_minutes": self.settings.access_token_expire_minutes,
        }


# ── BusinessService — companies & supplier verification ──────────────────────


class BusinessService:
    """Business account foundation — create / list / current / supplier verification."""

    def __init__(
        self,
        *,
        businesses: BusinessRepository | None = None,
        memberships: MembershipRepository | None = None,
        roles: RoleRepository | None = None,
        supplier_profiles: SupplierProfileRepository | None = None,
        auth: AuthService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.businesses = businesses or BusinessRepository()
        self.memberships = memberships or MembershipRepository()
        self.roles = roles or RoleRepository()
        self.supplier_profiles = supplier_profiles or SupplierProfileRepository()
        self.auth = auth or AuthService(
            businesses=self.businesses,
            memberships=self.memberships,
            roles=self.roles,
            supplier_profiles=self.supplier_profiles,
        )
        self.audit = audit or AuditService()

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        memberships = await self.memberships.list_for_user(user_id)
        if not memberships:
            return []
        business_ids = [m["business_account_id"] for m in memberships]
        rows = await self.businesses.collection.find(
            {"_id": {"$in": business_ids}}
        ).to_list(length=max(len(business_ids), 1))
        by_id = {row["_id"]: row for row in rows}
        supplier_ids = [
            row["_id"] for row in rows if row.get("type") == BusinessAccountType.SUPPLIER
        ]
        profiles_by_business: dict[Any, dict[str, Any]] = {}
        if supplier_ids:
            profile_rows = await self.supplier_profiles.find_many(
                {"business_account_id": {"$in": supplier_ids}},
                limit=max(len(supplier_ids), 1),
            )
            profiles_by_business = {
                row["business_account_id"]: row for row in profile_rows
            }
        results: list[dict[str, Any]] = []
        role_ids = list({m["role_id"] for m in memberships})
        role_rows = (
            await self.roles.find_many({"_id": {"$in": role_ids}}, limit=max(len(role_ids), 1))
            if role_ids
            else []
        )
        roles_by_id = {row["_id"]: row for row in role_rows}
        for membership in memberships:
            business = by_id.get(membership["business_account_id"])
            if business:
                payload = await _serialize_business_enriched(
                    business,
                    profiles=self.supplier_profiles,
                    profile=profiles_by_business.get(business["_id"]),
                )
                role = roles_by_id.get(membership["role_id"])
                payload["role_name"] = role["name"] if role else None
                results.append(payload)
        return results

    async def create_for_user(
        self,
        *,
        user_id: str,
        name: str,
        account_type: str = BusinessAccountType.BUYER,
        legal_name: str | None = None,
        tax_number: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        email_domain: str | None = None,
        address: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        if account_type == BusinessAccountType.PLATFORM:
            raise ForbiddenError("Platform businesses cannot be created through this API")
        existing = await self.memberships.list_for_user(user_id)
        if existing:
            # One trading business per account — invited platform memberships are rare;
            # any active membership means create is closed.
            for membership in existing:
                business = await self.businesses.get_by_id(membership["business_account_id"])
                if business and business.get("type") != BusinessAccountType.PLATFORM:
                    raise BusinessAlreadyExistsError()
        owner = await self.auth.users.get_by_id(user_id)
        owner_email = owner.get("email") if owner else None
        business = await self.auth._create_business_with_admin(
            name=name,
            owner_user_id=parse_object_id(user_id),
            account_type=BusinessAccountType(account_type),
            legal_name=legal_name,
            tax_number=tax_number,
            contact_email=contact_email,
            contact_phone=contact_phone,
            email_domain=email_domain,
            address=address,
            owner_email=owner_email,
        )
        await self.audit.log(
            action="BUSINESS_CREATED",
            resource_type="business_account",
            resource_id=business["_id"],
            business_account_id=business["_id"],
            user_id=user_id,
            ip_address=ip_address,
        )
        return await _serialize_business_enriched(business, profiles=self.supplier_profiles)

    async def get_current(self, business_account_id: str | None) -> dict[str, Any] | None:
        if not business_account_id:
            return None
        business = await self.businesses.get_by_id(business_account_id)
        if business is None:
            return None
        return await _serialize_business_enriched(business, profiles=self.supplier_profiles)

    async def get_for_user(self, *, user_id: str, business_id: str) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None:
            raise MembershipRequiredError()
        role = await self.roles.get_by_id(membership["role_id"])
        return {
            **(await _serialize_business_enriched(business, profiles=self.supplier_profiles)),
            "membership": {
                "id": str(membership["_id"]),
                "business_account_id": str(membership["business_account_id"]),
                "role_id": str(membership["role_id"]),
                "status": membership["status"],
            },
            "role_name": role["name"] if role else None,
        }

    async def update_for_user(
        self,
        *,
        user_id: str,
        business_id: str,
        name: str | None = None,
        legal_name: str | None = None,
        tax_number: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        address: dict[str, Any] | None = None,
        description: str | None = None,
        website: str | None = None,
        year_established: int | None = None,
        company_size: str | None = None,
        industry_categories: list[str] | None = None,
        business_tags: list[str] | None = None,
        email_domain: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None:
            raise MembershipRequiredError()
        if business.get("type") == BusinessAccountType.PLATFORM:
            raise ForbiddenError("Platform business identity cannot be updated here")
        if business.get("type") == BusinessAccountType.SUPPLIER:
            profile = await self.supplier_profiles.get_by_business(business_id)
            if (
                profile
                and profile.get("verification_status")
                == SupplierVerificationStatus.VERIFIED
            ):
                locked_changes = verified_supplier_identity_changes(
                    business,
                    name=name,
                    legal_name=legal_name,
                    tax_number=tax_number,
                    email_domain=email_domain,
                    address=address,
                )
                if locked_changes:
                    raise VerifiedBusinessLockedError(
                        "Legal identity on a verified supplier cannot be changed "
                        f"({', '.join(locked_changes)}). Update phone, description, "
                        "and other profile details instead."
                    )
                name = None
                legal_name = None
                tax_number = None
                email_domain = None
                address = None
        updates: dict[str, Any] = {"updated_at": utc_now()}
        if name is not None:
            updates["name"] = name.strip()
        if legal_name is not None:
            updates["legal_name"] = legal_name.strip()
        if tax_number is not None:
            updates["tax_number"] = tax_number
        if contact_email is not None:
            updates["contact_email"] = contact_email.lower().strip()
        if contact_phone is not None:
            updates["contact_phone"] = contact_phone.strip()
        if address is not None:
            updates["address"] = address
        if description is not None:
            updates["description"] = description.strip() or None
        if website is not None:
            updates["website"] = website.strip() or None
        if year_established is not None:
            updates["year_established"] = year_established
        if company_size is not None:
            updates["company_size"] = company_size.strip() or None
        if industry_categories is not None:
            updates["industry_categories"] = industry_categories
        if business_tags is not None:
            updates["business_tags"] = business_tags
        if email_domain is not None:
            from app.modules.identity.company_domain import validate_company_email_domain
            from app.modules.identity.exceptions import CompanyDomainRequiredError

            try:
                resolved = validate_company_email_domain(email_domain, required=True)
            except ValueError as exc:
                raise CompanyDomainRequiredError(str(exc)) from exc
            updates["email_domain"] = resolved
        updated = await self.businesses.update(business_id, updates)
        await self.audit.log(
            action="BUSINESS_UPDATED",
            resource_type="business_account",
            resource_id=business_id,
            business_account_id=business_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"fields": sorted(k for k in updates if k != "updated_at")},
        )
        return await _serialize_business_enriched(
            updated or business, profiles=self.supplier_profiles
        )

    async def set_business_media(
        self,
        *,
        user_id: str,
        business_id: str,
        kind: str,
        url: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Persist logo or cover URL on the business account."""
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None:
            raise MembershipRequiredError()
        if business.get("type") == BusinessAccountType.PLATFORM:
            raise ForbiddenError("Platform business identity cannot be updated here")
        if kind not in {"logo", "cover"}:
            raise BadRequestError("kind must be logo or cover")
        field = "logo_url" if kind == "logo" else "cover_url"
        updated = await self.businesses.update(
            business_id,
            {field: url, "updated_at": utc_now()},
        )
        if kind == "logo":
            from app.modules.identity.repository import UserRepository

            users = UserRepository()
            members = await self.memberships.list_for_business(business_id)
            await users.set_avatar_url_for_ids(
                [row.get("user_id") for row in members],
                url,
                updated_at=utc_now(),
            )
        await self.audit.log(
            action="BUSINESS_MEDIA_UPDATED",
            resource_type="business_account",
            resource_id=business_id,
            business_account_id=business_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"kind": kind},
        )
        return await _serialize_business_enriched(
            updated or business, profiles=self.supplier_profiles
        )

    async def submit_supplier_verification(
        self,
        *,
        user_id: str,
        business_id: str,
        documents: list[dict[str, str]],
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") != BusinessAccountType.SUPPLIER:
            raise ForbiddenError("Only supplier businesses can submit verification")
        profile = await self.supplier_profiles.get_by_business(business_id)
        if profile is None:
            raise ForbiddenError("Supplier profile not found")

        current = str(profile.get("verification_status") or SupplierVerificationStatus.UNVERIFIED)
        # Allow replacing the package while already pending.
        if current != SupplierVerificationStatus.PENDING:
            allowed = VERIFICATION_TRANSITIONS.get(current, set())
            if SupplierVerificationStatus.PENDING not in allowed:
                raise ForbiddenError(
                    f"Cannot submit verification from status '{current}'"
                )

        now = utc_now()
        from app.modules.identity.storage import (
            delete_verification_file_from_url,
            is_stored_verification_url,
        )

        types_seen: set[str] = set()
        doc_rows: list[dict[str, Any]] = []
        for row in documents:
            document_type = str(row.get("document_type") or "").strip()
            if document_type not in REQUIRED_SUPPLIER_DOCUMENT_TYPES:
                raise BadRequestError("Unknown verification document type")
            if document_type in types_seen:
                raise BadRequestError("Duplicate verification document type")
            types_seen.add(document_type)
            url = str(row.get("url") or "").strip()
            if not is_stored_verification_url(business_id, document_type, url):
                raise BadRequestError(
                    "Upload each document file before submitting so reviewers can open it."
                )
            doc_rows.append(
                {
                    "document_type": document_type,
                    "url": url,
                    "file_name": row.get("file_name"),
                    "uploaded_at": now,
                    "verified_at": None,
                }
            )
        if not REQUIRED_SUPPLIER_DOCUMENT_TYPES.issubset(types_seen):
            raise BadRequestError(
                "Commercial registration, tax certificate, and address proof are required."
            )

        previous = [
            item
            for item in (profile.get("documents") or [])
            if isinstance(item, dict)
        ]
        keep_urls = {row["url"] for row in doc_rows}
        for old in previous:
            old_url = old.get("url")
            if old_url and old_url not in keep_urls:
                delete_verification_file_from_url(str(old_url))

        await self.supplier_profiles.update(
            profile["_id"],
            {
                "verification_status": SupplierVerificationStatus.PENDING,
                "documents": doc_rows,
                "rejection_reason": None,
                "updated_at": now,
            },
        )
        # Keep company pending until platform staff approve.
        if business.get("status") != BusinessAccountStatus.PENDING:
            await self.businesses.update(
                business_id,
                {"status": BusinessAccountStatus.PENDING, "updated_at": now},
            )
        await self.audit.log(
            action="SUPPLIER_VERIFICATION_SUBMITTED",
            resource_type="supplier_profile",
            resource_id=profile["_id"],
            business_account_id=business_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"document_count": len(doc_rows)},
        )
        try:
            from app.modules.trust.notify import notify_platform_staff

            await notify_platform_staff(
                type="SUPPLIER_VERIFICATION_SUBMITTED",
                title=f"{business.get('name')} submitted verification documents",
                message="A supplier is waiting for review. Open the verification queue to approve or request changes.",
                reference_type="supplier_verification",
                reference_id=profile["_id"],
                cta_path="/admin/suppliers",
            )
        except Exception:
            pass
        refreshed = await self.businesses.get_by_id(business_id)
        return await _serialize_business_enriched(
            refreshed or business, profiles=self.supplier_profiles
        )

    async def withdraw_supplier_document(
        self,
        *,
        user_id: str,
        business_id: str,
        document_type: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") != BusinessAccountType.SUPPLIER:
            raise ForbiddenError("Only supplier businesses can manage verification documents")
        profile = await self.supplier_profiles.get_by_business(business_id)
        if profile is None:
            raise ForbiddenError("Supplier profile not found")

        current = str(profile.get("verification_status") or SupplierVerificationStatus.UNVERIFIED)
        if current == SupplierVerificationStatus.VERIFIED:
            raise VerifiedBusinessLockedError()
        if current not in {
            SupplierVerificationStatus.PENDING,
            SupplierVerificationStatus.UNVERIFIED,
            SupplierVerificationStatus.REJECTED,
        }:
            raise ForbiddenError(f"Cannot withdraw documents from status '{current}'")

        docs = [row for row in (profile.get("documents") or []) if isinstance(row, dict)]
        remaining = [row for row in docs if row.get("document_type") != document_type]
        if len(remaining) == len(docs):
            raise ForbiddenError("Document not found")
        from app.modules.identity.storage import delete_verification_file_from_url

        for removed in docs:
            if removed.get("document_type") == document_type:
                delete_verification_file_from_url(str(removed.get("url") or ""))

        present_types = {str(row.get("document_type")) for row in remaining}
        complete = REQUIRED_SUPPLIER_DOCUMENT_TYPES.issubset(present_types)
        if current == SupplierVerificationStatus.PENDING and not complete:
            next_status = SupplierVerificationStatus.UNVERIFIED
        else:
            next_status = current

        now = utc_now()
        await self.supplier_profiles.update(
            profile["_id"],
            {
                "documents": remaining,
                "verification_status": next_status,
                "updated_at": now,
            },
        )
        await self.audit.log(
            action="SUPPLIER_VERIFICATION_DOCUMENT_WITHDRAWN",
            resource_type="supplier_profile",
            resource_id=profile["_id"],
            business_account_id=business_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "document_type": document_type,
                "remaining_count": len(remaining),
                "verification_status": next_status,
            },
        )
        refreshed = await self.businesses.get_by_id(business_id)
        return await _serialize_business_enriched(
            refreshed or business, profiles=self.supplier_profiles
        )

    async def list_supplier_verifications(
        self,
        *,
        verification_status: str | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"type": BusinessAccountType.SUPPLIER}
        if verification_status:
            profile_rows = await self.supplier_profiles.find_many(
                {"verification_status": verification_status},
                limit=10_000,
                sort=[("updated_at", -1)],
            )
            if not profile_rows:
                return [], 0
            query["_id"] = {
                "$in": [row["business_account_id"] for row in profile_rows]
            }

        needle = (q or "").strip()
        if needle:
            rx = {"$regex": re.escape(needle), "$options": "i"}
            query["$or"] = [
                {"name": rx},
                {"legal_name": rx},
                {"contact_email": rx},
                {"email_domain": rx},
                {"tax_number": rx},
            ]

        total = await self.businesses.count(query)
        rows = await self.businesses.find_many(
            query,
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )
        if not rows:
            return [], total

        business_ids = [row["_id"] for row in rows]
        profile_rows = await self.supplier_profiles.find_many(
            {"business_account_id": {"$in": business_ids}},
            limit=max(len(business_ids), 1),
        )
        profiles_by_business = {
            row["business_account_id"]: row for row in profile_rows
        }
        results: list[dict[str, Any]] = []
        for business in rows:
            results.append(
                await _serialize_business_enriched(
                    business,
                    profiles=self.supplier_profiles,
                    profile=profiles_by_business.get(business["_id"]),
                )
            )
        return results, total

    async def list_trading_businesses(
        self,
        *,
        account_type: str | None = None,
        status: str | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Platform directory of buyer/supplier companies (excludes the platform tenant)."""
        query: dict[str, Any] = {
            "type": {"$in": [BusinessAccountType.BUYER, BusinessAccountType.SUPPLIER]}
        }
        if account_type in {BusinessAccountType.BUYER, BusinessAccountType.SUPPLIER}:
            query["type"] = account_type
        if status:
            query["status"] = status
        needle = (q or "").strip()
        if needle:
            rx = {"$regex": re.escape(needle), "$options": "i"}
            query["$or"] = [
                {"name": rx},
                {"legal_name": rx},
                {"contact_email": rx},
                {"email_domain": rx},
                {"tax_number": rx},
            ]

        total = await self.businesses.count(query)
        rows = await self.businesses.find_many(
            query,
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )
        if not rows:
            return [], total

        supplier_ids = [
            row["_id"] for row in rows if row.get("type") == BusinessAccountType.SUPPLIER
        ]
        profiles_by_business: dict[Any, dict[str, Any]] = {}
        if supplier_ids:
            profile_rows = await self.supplier_profiles.find_many(
                {"business_account_id": {"$in": supplier_ids}},
                limit=max(len(supplier_ids), 1),
            )
            profiles_by_business = {
                row["business_account_id"]: row for row in profile_rows
            }
        results: list[dict[str, Any]] = []
        for business in rows:
            results.append(
                await _serialize_business_enriched(
                    business,
                    profiles=self.supplier_profiles,
                    profile=profiles_by_business.get(business["_id"]),
                )
            )
        return results, total

    async def get_trading_business(self, business_id: str) -> dict[str, Any]:
        """Platform staff profile view of a buyer or supplier (not the platform tenant)."""
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") not in {
            BusinessAccountType.BUYER,
            BusinessAccountType.SUPPLIER,
        }:
            raise NotFoundError("Business not found")
        return await _serialize_business_enriched(
            business, profiles=self.supplier_profiles
        )

    async def get_public_company(self, business_id: str) -> dict[str, Any]:
        """Authenticated trading counterparties can open a buyer or supplier profile."""
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") not in {
            BusinessAccountType.BUYER,
            BusinessAccountType.SUPPLIER,
        }:
            raise NotFoundError("Business not found")
        verification_status: str | None = None
        if business.get("type") == BusinessAccountType.SUPPLIER:
            profile = await self.supplier_profiles.get_by_business(business["_id"])
            verification_status = (
                str(profile["verification_status"])
                if profile and profile.get("verification_status")
                else SupplierVerificationStatus.UNVERIFIED
            )
        return _serialize_public_company(
            business, verification_status=verification_status
        )

    async def review_supplier_verification(
        self,
        *,
        business_id: str,
        decision: str,
        actor_user_id: str,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") != BusinessAccountType.SUPPLIER:
            raise ForbiddenError("Supplier business not found")
        profile = await self.supplier_profiles.get_by_business(business_id)
        if profile is None:
            raise ForbiddenError("Supplier profile not found")

        current = str(profile.get("verification_status") or SupplierVerificationStatus.UNVERIFIED)
        if decision == "approve":
            target = SupplierVerificationStatus.VERIFIED
            business_status = BusinessAccountStatus.VERIFIED
        elif decision == "reject":
            target = SupplierVerificationStatus.REJECTED
            # Stay pending so the supplier can re-submit documents after fixes.
            business_status = BusinessAccountStatus.PENDING
        elif decision == "revoke":
            target = SupplierVerificationStatus.REVOKED
            # Lose marketplace rights until they re-submit and are approved again.
            business_status = BusinessAccountStatus.SUSPENDED
        else:
            raise ForbiddenError("decision must be approve, reject, or revoke")

        allowed = VERIFICATION_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ForbiddenError(
                f"Cannot {decision} verification from status '{current}'"
            )

        now = utc_now()
        profile_updates: dict[str, Any] = {
            "verification_status": target,
            "updated_at": now,
            "rejection_reason": (
                reason.strip()
                if decision in {"reject", "revoke"} and reason
                else None
            ),
        }
        if decision == "approve":
            profile_updates["verified_at"] = now
            profile_updates["verified_by"] = parse_object_id(actor_user_id)
            profile_updates["rejection_reason"] = None
        elif decision == "revoke":
            # Keep verified_at for audit trail of prior approval; clear for reject.
            profile_updates["verified_by"] = None
        else:
            profile_updates["verified_at"] = None
            profile_updates["verified_by"] = None

        await self.supplier_profiles.update(profile["_id"], profile_updates)
        await self.businesses.update(
            business_id,
            {"status": business_status, "updated_at": now},
        )

        deactivated = 0
        if decision == "revoke":
            try:
                from app.modules.catalog.service import CatalogService

                deactivated = await CatalogService().deactivate_all_for_business(
                    business_id,
                    reason="supplier_verification_revoked",
                )
            except Exception:
                deactivated = 0

        audit_action = {
            "approve": "SUPPLIER_VERIFICATION_APPROVED",
            "reject": "SUPPLIER_VERIFICATION_REJECTED",
            "revoke": "SUPPLIER_VERIFICATION_REVOKED",
        }[decision]
        await self.audit.log(
            action=audit_action,
            resource_type="supplier_profile",
            resource_id=profile["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                **({"reason": reason} if reason else {}),
                "products_deactivated": deactivated,
            },
        )
        refreshed = await self.businesses.get_by_id(business_id)
        try:
            from app.modules.trust.notify import notify

            if decision == "approve":
                await notify(
                    recipient_business_id=business_id,
                    type="SUPPLIER_VERIFIED",
                    title=f"{business.get('name')} is verified to sell on TradeBay",
                    message="Your supplier profile is approved. You can list products and quote on RFQs.",
                    reference_type="business",
                    reference_id=business_id,
                    cta_path="/settings",
                )
            elif decision == "revoke":
                await notify(
                    recipient_business_id=business_id,
                    type="SUPPLIER_REJECTED",
                    title=f"Selling rights revoked for {business.get('name')}",
                    message=(
                        reason.strip()
                        if reason
                        else "Your listings were taken offline. Update documents and resubmit for review."
                    ),
                    reference_type="business",
                    reference_id=business_id,
                    cta_path="/businesses/new/verify",
                )
            else:
                await notify(
                    recipient_business_id=business_id,
                    type="SUPPLIER_REJECTED",
                    title=f"Verification was not approved for {business.get('name')}",
                    message=(
                        reason.strip()
                        if reason
                        else "Please update your documents and resubmit."
                    ),
                    reference_type="business",
                    reference_id=business_id,
                    cta_path="/businesses/new/verify",
                )
        except Exception:
            pass
        return await _serialize_business_enriched(
            refreshed or business, profiles=self.supplier_profiles
        )

    async def assert_not_last_admin(
        self, *, business_account_id: str, membership: dict[str, Any]
    ) -> None:
        """Guard for future remove/demote. Does not implement those workflows."""
        await assert_not_last_admin(
            business_account_id=business_account_id,
            membership=membership,
            memberships=self.memberships,
            roles=self.roles,
        )
