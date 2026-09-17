"""Identity application services."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError
from app.core.security import (
    create_access_token,
    generate_invitation_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.seed import seed_trading_roles
from app.db.transactions import run_in_transaction
from app.modules.identity.constants import (
    AUTH_TOKEN_MAX_ATTEMPTS,
    EMAIL_VERIFY_TTL_HOURS,
    PASSWORD_RESET_TTL_HOURS,
    SYSTEM_ROLE_BUSINESS_ADMIN,
    AuthTokenPurpose,
    BusinessAccountStatus,
    BusinessAccountType,
    MembershipStatus,
    SupplierVerificationStatus,
    UserStatus,
    is_business_operational,
)
from app.modules.identity.email import get_email_sender
from app.modules.identity.exceptions import (
    AccountInactiveError,
    BusinessInactiveError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    MembershipRequiredError,
    SessionRevokedError,
)
from app.modules.identity.guards import assert_not_last_admin
from app.modules.identity.rate_limit import challenge_limiter
from app.modules.identity.repository import (
    AuthTokenRepository,
    BusinessRepository,
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


def _serialize_user(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "status": doc["status"],
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


def _serialize_business(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "type": doc["type"],
        "status": doc["status"],
        "legal_name": doc.get("legal_name"),
        "tax_number": doc.get("tax_number"),
        "contact_email": doc.get("contact_email"),
        "contact_phone": doc.get("contact_phone"),
        "address": _serialize_address(doc.get("address") if isinstance(doc.get("address"), dict) else None),
    }


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
        self.supplier_profiles = supplier_profiles or SupplierProfileRepository()
        self.audit = audit or AuditService()
        self.settings = settings or get_settings()

    async def register(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        business_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        normalized = email.lower().strip()
        if await self.users.get_by_email(normalized):
            raise EmailAlreadyRegisteredError()

        now = utc_now()
        user = await self.users.create(
            {
                "email": normalized,
                "password_hash": hash_password(password),
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "phone": None,
                "status": UserStatus.PENDING,
                "email_verified_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        raw_verify = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFICATION)
        await get_email_sender().send(
            to=normalized,
            template="email_verification",
            context={"user_id": str(user["_id"]), "token": raw_verify},
        )

        business: dict[str, Any] | None = None
        if business_name:
            business = await self._create_business_with_admin(
                name=business_name.strip(),
                owner_user_id=user["_id"],
                account_type=BusinessAccountType.BUYER,
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
        )
        await event_bus.publish(DomainEvent(name=USER_REGISTERED, payload={"user_id": str(user["_id"])}))

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

        await self.sessions.revoke(session["_id"], utc_now())
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
                active_business = _serialize_business(business_doc)
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
            "user": _serialize_user(user),
            "active_business": active_business,
            "membership": membership,
            "role_name": role_name,
            "permissions": permission_codes,
        }

    async def verify_email(self, *, raw_token: str, ip_address: str | None = None) -> dict[str, Any]:
        token_row = await self._consume_auth_token(raw_token, AuthTokenPurpose.EMAIL_VERIFICATION)
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
            context={"user_id": str(user["_id"]), "token": raw},
        )

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
            context={"user_id": str(user["_id"]), "token": raw},
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
        await self.audit.log(
            action="USER_LOGOUT_ALL",
            resource_type="user",
            resource_id=user_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={"revoked_count": revoked, "include_current": include_current},
        )
        return {"revoked": revoked}

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
            context={"user_id": str(user["_id"]), "token": raw},
        )

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
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()
        access = create_access_token(
            settings=self.settings,
            user_id=str(user["_id"]),
            session_id=str(session["_id"]),
            business_account_id=str(business["_id"]),
        )
        return {
            "business": _serialize_business(business),
            "access_token": access,
            "access_token_expires_in_minutes": self.settings.access_token_expire_minutes,
        }

    async def _issue_auth_token(self, user_id: ObjectId, purpose: AuthTokenPurpose) -> str:
        raw = generate_invitation_token()
        now = utc_now()
        hours = (
            EMAIL_VERIFY_TTL_HOURS
            if purpose == AuthTokenPurpose.EMAIL_VERIFICATION
            else PASSWORD_RESET_TTL_HOURS
        )
        await self.auth_tokens.invalidate_open(user_id, purpose, at=now)
        await self.auth_tokens.create(
            {
                "user_id": user_id,
                "purpose": purpose,
                "token_hash": hash_token(raw),
                "expires_at": now + timedelta(hours=hours),
                "used_at": None,
                "invalidated_at": None,
                "attempts": 0,
                "created_at": now,
            }
        )
        return raw

    async def _require_open_auth_token(self, raw_token: str, purpose: AuthTokenPurpose) -> dict[str, Any]:
        row = await self.auth_tokens.get_by_hash(hash_token(raw_token))
        now = utc_now()
        if row is None:
            raise InvalidCredentialsError()
        attempts = int(row.get("attempts") or 0) + 1
        await self.auth_tokens.update(row["_id"], {"attempts": attempts})
        if (
            row.get("purpose") != purpose
            or row.get("used_at") is not None
            or row.get("invalidated_at") is not None
            or as_utc(row["expires_at"]) < now
            or attempts > AUTH_TOKEN_MAX_ATTEMPTS
        ):
            raise InvalidCredentialsError()
        return row

    async def _consume_auth_token(self, raw_token: str, purpose: AuthTokenPurpose) -> dict[str, Any]:
        row = await self._require_open_auth_token(raw_token, purpose)
        await self.auth_tokens.update(row["_id"], {"used_at": utc_now()})
        return row

    async def _permission_codes_for_role(self, role_id: ObjectId) -> list[str]:
        permission_ids = await self.role_permissions.list_permission_ids_for_role(role_id)
        codes: list[str] = []
        for pid in permission_ids:
            perm = await self.permissions.get_by_id(pid)
            if perm:
                codes.append(f"{perm['resource']}.{perm['action']}")
        return sorted(set(codes))

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
        address: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "name": name,
            "type": account_type,
            "status": BusinessAccountStatus.VERIFIED,
            "legal_name": (legal_name or name).strip() if legal_name or name else name,
            "tax_number": tax_number,
            "contact_email": contact_email.lower().strip() if contact_email else None,
            "contact_phone": contact_phone.strip() if contact_phone else None,
            "address": address,
            "created_at": now,
            "updated_at": now,
        }

        async def work(session: MongoSession) -> dict[str, Any]:
            business = await self.businesses.create(payload, session=session)
            roles = await seed_trading_roles(business["_id"], session=session)
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


class BusinessService:
    """Business account foundation — create / list / current."""

    def __init__(
        self,
        *,
        businesses: BusinessRepository | None = None,
        memberships: MembershipRepository | None = None,
        roles: RoleRepository | None = None,
        auth: AuthService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.businesses = businesses or BusinessRepository()
        self.memberships = memberships or MembershipRepository()
        self.roles = roles or RoleRepository()
        self.auth = auth or AuthService(
            businesses=self.businesses,
            memberships=self.memberships,
            roles=self.roles,
        )
        self.audit = audit or AuditService()

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        memberships = await self.memberships.list_for_user(user_id)
        results: list[dict[str, Any]] = []
        for membership in memberships:
            business = await self.businesses.get_by_id(membership["business_account_id"])
            if business:
                results.append(_serialize_business(business))
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
        address: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        if account_type == BusinessAccountType.PLATFORM:
            raise ForbiddenError("Platform businesses cannot be created through this API")
        business = await self.auth._create_business_with_admin(
            name=name,
            owner_user_id=parse_object_id(user_id),
            account_type=BusinessAccountType(account_type),
            legal_name=legal_name,
            tax_number=tax_number,
            contact_email=contact_email,
            contact_phone=contact_phone,
            address=address,
        )
        await self.audit.log(
            action="BUSINESS_CREATED",
            resource_type="business_account",
            resource_id=business["_id"],
            business_account_id=business["_id"],
            user_id=user_id,
            ip_address=ip_address,
        )
        return _serialize_business(business)

    async def get_current(self, business_account_id: str | None) -> dict[str, Any] | None:
        if not business_account_id:
            return None
        business = await self.businesses.get_by_id(business_account_id)
        return _serialize_business(business) if business else None

    async def get_for_user(self, *, user_id: str, business_id: str) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None:
            raise MembershipRequiredError()
        role = await self.roles.get_by_id(membership["role_id"])
        return {
            **_serialize_business(business),
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
        return _serialize_business(updated or business)

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
