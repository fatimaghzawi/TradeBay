"""Identity application services."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    generate_invitation_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.seed import seed_trading_roles
from app.modules.identity.constants import (
    SYSTEM_ROLE_BUSINESS_ADMIN,
    AuthTokenPurpose,
    BusinessAccountStatus,
    BusinessAccountType,
    MembershipStatus,
    SupplierVerificationStatus,
    UserStatus,
)
from app.modules.identity.exceptions import (
    AccountInactiveError,
    BusinessInactiveError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    MembershipRequiredError,
    SessionRevokedError,
)
from app.modules.identity.guards import assert_not_last_admin
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


def _serialize_business(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "type": doc["type"],
        "status": doc["status"],
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
        raw_verify = await self._issue_auth_token(user["_id"], AuthTokenPurpose.EMAIL_VERIFY)

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
            **({"verification_token": raw_verify} if not self.settings.is_production else {}),
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

    async def logout(self, *, session_id: str) -> None:
        await self.sessions.revoke(session_id, utc_now())

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

        # Rotate refresh token
        await self.sessions.revoke(session["_id"], utc_now())
        tokens = await self._issue_session(
            user=user,
            business_account_id=session.get("active_business_account_id"),
            ip_address=ip_address,
            user_agent=user_agent,
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

    async def verify_email(self, *, raw_token: str) -> dict[str, Any]:
        token_row = await self._consume_auth_token(raw_token, AuthTokenPurpose.EMAIL_VERIFY)
        now = utc_now()
        user = await self.users.update(
            token_row["user_id"],
            {"status": UserStatus.ACTIVE, "email_verified_at": now, "updated_at": now},
        )
        if user is None:
            raise InvalidCredentialsError()
        return {"user": _serialize_user(user)}

    async def request_password_reset(self, *, email: str) -> None:
        user = await self.users.get_by_email(email.lower().strip())
        if user is None:
            return
        if user["status"] in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
            return
        await self._issue_auth_token(user["_id"], AuthTokenPurpose.PASSWORD_RESET)

    async def reset_password(self, *, raw_token: str, new_password: str) -> None:
        token_row = await self._consume_auth_token(raw_token, AuthTokenPurpose.PASSWORD_RESET)
        now = utc_now()
        await self.users.update(
            token_row["user_id"],
            {"password_hash": hash_password(new_password), "updated_at": now},
        )

    async def switch_business(self, *, session_id: str, user_id: str, business_id: str) -> dict[str, Any]:
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            raise MembershipRequiredError()
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("status") != BusinessAccountStatus.ACTIVE:
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
        hours = 24 if purpose == AuthTokenPurpose.EMAIL_VERIFY else 2
        await self.auth_tokens.create(
            {
                "user_id": user_id,
                "purpose": purpose,
                "token_hash": hash_token(raw),
                "expires_at": now + timedelta(hours=hours),
                "used_at": None,
                "created_at": now,
            }
        )
        return raw

    async def _consume_auth_token(self, raw_token: str, purpose: AuthTokenPurpose) -> dict[str, Any]:
        row = await self.auth_tokens.get_by_hash(hash_token(raw_token))
        now = utc_now()
        if (
            row is None
            or row.get("purpose") != purpose
            or row.get("used_at") is not None
            or as_utc(row["expires_at"]) < now
        ):
            raise InvalidCredentialsError()
        await self.auth_tokens.update(row["_id"], {"used_at": now})
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
    ) -> dict[str, Any]:
        now = utc_now()
        business = await self.businesses.create(
            {
                "name": name,
                "type": account_type,
                "status": BusinessAccountStatus.ACTIVE,
                "legal_name": name,
                "tax_number": None,
                "address": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        roles = await seed_trading_roles(business["_id"])
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
            }
        )
        # Every trading company may later sell; selling itself is gated by verification.
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
            }
        )
        return business

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
    ) -> dict[str, Any]:
        business = await self.auth._create_business_with_admin(
            name=name,
            owner_user_id=parse_object_id(user_id),
            account_type=BusinessAccountType(account_type),
        )
        await self.audit.log(
            action="BUSINESS_CREATED",
            resource_type="business_account",
            resource_id=business["_id"],
            business_account_id=business["_id"],
            user_id=user_id,
        )
        return _serialize_business(business)

    async def get_current(self, business_account_id: str | None) -> dict[str, Any] | None:
        if not business_account_id:
            return None
        business = await self.businesses.get_by_id(business_account_id)
        return _serialize_business(business) if business else None

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
