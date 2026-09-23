"""Idempotent startup seed: permissions, platform tenant, admin login, and settings."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo.errors import BulkWriteError, DuplicateKeyError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import (
    SYSTEM_ROLE_PLATFORM_ADMIN,
    BusinessAccountStatus,
    BusinessAccountType,
    MembershipStatus,
    UserStatus,
)
from app.modules.identity.permissions import (
    DEFAULT_PERMISSION_CATALOG,
    PLATFORM_SYSTEM_ROLES,
    SYSTEM_ROLE_GRANTS,
    TRADING_SYSTEM_ROLES,
)
from app.modules.identity.repository import (
    BusinessRepository,
    MembershipRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.modules.settings.constants import SINGLETON_KEY
from app.modules.settings.repository import (
    BusinessSettingsRepository,
    PlatformSettingsRepository,
    TaxSettingsRepository,
)
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now

logger = get_logger(__name__)

PLATFORM_BUSINESS_NAME = "TradeBay"
PLATFORM_ADMIN_EMAIL = "admin@tradebay.com"
PLATFORM_ADMIN_PASSWORD = "AdminPass123!"  # override via PLATFORM_ADMIN_PASSWORD env in real deploys
_permission_index_cache: dict[str, ObjectId] | None = None


def _platform_admin_password() -> str:
    import os

    return (os.environ.get("PLATFORM_ADMIN_PASSWORD") or PLATFORM_ADMIN_PASSWORD).strip()

# Demo SKUs shown on the public landing rail until a supplier flags others.
_FEATURED_LANDING_SKUS = (
    "LEV-OIL-1L",
    "ZFI-HONEY",
    "BKT-MON-24",
    "CDR-BLOCK-20",
    "TYR-FISH-ICE",
    "MSP-TEA-HERB",
)


async def seed_startup() -> None:
    await seed_permissions()
    permission_index = await _permission_index()
    platform = await seed_platform_business(permission_index)
    platform_admin = await seed_platform_admin(platform)
    trading_roles = await seed_existing_trading_business_roles(permission_index)
    await seed_settings()
    featured = await seed_featured_landing_products()
    logger.info(
        "startup_seed_complete",
        platform_business_id=str(platform["_id"]) if platform else None,
        permissions=len(permission_index),
        trading_businesses_seeded=trading_roles,
        featured_landing_products=featured,
        platform_admin=platform_admin,
    )


async def seed_featured_landing_products() -> int:
    """Flag known demo SKUs as featured when none are marked yet."""
    products = mongo_manager.collection(CollectionName.PRODUCTS)
    already = await products.count_documents({"is_featured": True})
    if already:
        return 0
    result = await products.update_many(
        {"sku": {"$in": list(_FEATURED_LANDING_SKUS)}, "status": "active"},
        {"$set": {"is_featured": True}},
    )
    return int(result.modified_count)


async def seed_existing_trading_business_roles(
    permission_index: dict[str, ObjectId] | None = None,
) -> int:
    """Ensure every buyer/supplier business has system roles + up-to-date grants."""
    index = permission_index or await _permission_index()
    businesses = BusinessRepository()
    rows = await businesses.find_many(
        {"type": {"$in": [BusinessAccountType.BUYER, BusinessAccountType.SUPPLIER]}},
        limit=500,
    )
    for business in rows:
        await _seed_roles_for_business(business["_id"], TRADING_SYSTEM_ROLES, index)
    return len(rows)


async def seed_permissions() -> None:
    global _permission_index_cache
    repo = PermissionRepository()
    now = utc_now()
    for resource, action, description in DEFAULT_PERMISSION_CATALOG:
        existing = await repo.get_by_resource_action(resource, action)
        if existing is None:
            try:
                await repo.create(
                    {
                        "resource": resource,
                        "action": action,
                        "description": description,
                        "created_at": now,
                    }
                )
            except DuplicateKeyError:
                pass
    _permission_index_cache = None


async def seed_trading_roles(
    business_account_id: ObjectId,
    *,
    permission_index: dict[str, ObjectId] | None = None,
    session: MongoSession = None,
    fresh: bool = False,
) -> dict[str, dict[str, Any]]:
    """Create the five undeletable system roles for a trading company."""
    index = permission_index or await _permission_index()
    return await _seed_roles_for_business(
        business_account_id,
        TRADING_SYSTEM_ROLES,
        index,
        session=session,
        fresh=fresh,
    )


async def seed_platform_business(
    permission_index: dict[str, ObjectId] | None = None,
) -> dict[str, Any]:
    businesses = BusinessRepository()
    existing = await businesses.find_one({"type": BusinessAccountType.PLATFORM})
    now = utc_now()
    if existing is None:
        existing = await businesses.create(
            {
                "name": PLATFORM_BUSINESS_NAME,
                "type": BusinessAccountType.PLATFORM,
                "status": BusinessAccountStatus.VERIFIED,
                "legal_name": PLATFORM_BUSINESS_NAME,
                "tax_number": None,
                "logo_url": "/images/logos/tradebay.svg",
                "address": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    elif not existing.get("logo_url"):
        existing = (
            await businesses.update(
                existing["_id"],
                {"logo_url": "/images/logos/tradebay.svg", "updated_at": now},
            )
            or existing
        )
    index = permission_index or await _permission_index()
    await _seed_roles_for_business(existing["_id"], PLATFORM_SYSTEM_ROLES, index)
    return existing


async def seed_platform_admin(platform: dict[str, Any] | None) -> str:
    """Ensure the local platform admin login exists (skipped in production/test).

    Creates the user and Platform Admin membership when missing. Does not reset
    an existing password on every API restart.
    """
    settings = get_settings()
    if settings.is_production or settings.is_test or platform is None:
        return "skipped"
    email = PLATFORM_ADMIN_EMAIL
    users = UserRepository()
    memberships = MembershipRepository()
    roles = RoleRepository()
    now = utc_now()
    user = await users.get_by_email(email)
    created_user = False
    if user is None:
        user = await users.create(
            {
                "email": email,
                "personal_email": email,
                "password_hash": hash_password(_platform_admin_password()),
                "first_name": "Platform",
                "last_name": "Admin",
                "phone": None,
                "status": UserStatus.ACTIVE,
                "email_verified_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        created_user = True
    role = await roles.find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    if role is None:
        return "missing_role"
    membership = await memberships.get_for_user_business(user["_id"], platform["_id"])
    if membership is None:
        await memberships.create(
            {
                "user_id": user["_id"],
                "business_account_id": platform["_id"],
                "role_id": role["_id"],
                "status": MembershipStatus.ACTIVE,
                "joined_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        return "created" if created_user else "membership_created"
    if membership.get("status") != MembershipStatus.ACTIVE or membership.get("role_id") != role["_id"]:
        await memberships.update(
            membership["_id"],
            {
                "role_id": role["_id"],
                "status": MembershipStatus.ACTIVE,
                "updated_at": now,
            },
        )
        return "membership_updated"
    return "created" if created_user else "exists"


async def seed_settings() -> None:
    now = utc_now()
    platform_settings = PlatformSettingsRepository()
    if await platform_settings.find_one({"key": SINGLETON_KEY}) is None:
        await platform_settings.create(
            {
                "key": SINGLETON_KEY,
                "platform_name": "TradeBay",
                "default_currency": "USD",
                "commission_rate": to_decimal128(Decimal("0.05")),
                "commission_type": "percentage",
                "commission_base": "order_total",
                "minimum_order_value": to_decimal128(Decimal("0")),
                "payment_provider": None,
                "payment_provider_active": False,
                "updated_by": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    letterhead = BusinessSettingsRepository()
    if await letterhead.find_one({"key": SINGLETON_KEY}) is None:
        await letterhead.create(
            {
                "key": SINGLETON_KEY,
                "business_name": "TradeBay",
                "business_email": None,
                "business_phone": None,
                "address": None,
                "tax_registration_number": None,
                "invoice_prefix": "TB-INV",
                "updated_by": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    tax = TaxSettingsRepository()
    if await tax.find_one({"is_active": True}) is None:
        await tax.create(
            {
                "name": "VAT",
                "rate": to_decimal128(Decimal("0.11")),
                "type": "VAT",
                "is_active": True,
                "effective_from": now,
                "effective_until": None,
                "updated_by": None,
                "created_at": now,
                "updated_at": now,
            }
        )


async def _permission_index() -> dict[str, ObjectId]:
    global _permission_index_cache
    if _permission_index_cache is not None:
        return _permission_index_cache
    repo = PermissionRepository()
    rows = await repo.find_many({}, limit=500)
    _permission_index_cache = {
        f"{row['resource']}.{row['action']}": row["_id"] for row in rows
    }
    return _permission_index_cache


async def _seed_roles_for_business(
    business_account_id: ObjectId,
    role_names: tuple[str, ...],
    permission_index: dict[str, ObjectId],
    *,
    session: MongoSession = None,
    fresh: bool = False,
) -> dict[str, dict[str, Any]]:
    """Seed system roles + grants.

    `fresh=True` skips existence checks (new business create path) and bulk-inserts
    roles + grants in two round-trips — critical on high-latency Atlas.
    """
    roles = RoleRepository()
    grants = RolePermissionRepository()
    now = utc_now()
    created: dict[str, dict[str, Any]] = {}
    grant_docs: list[dict[str, Any]] = []

    if fresh:
        role_docs: list[dict[str, Any]] = []
        for name in role_names:
            role = {
                "_id": ObjectId(),
                "business_account_id": business_account_id,
                "name": name,
                "description": f"System role: {name}",
                "is_system_role": True,
                "is_active": True,
                "deleted_at": None,
                "created_at": now,
                "updated_at": now,
            }
            role_docs.append(role)
            created[name] = role
            for resource, action in SYSTEM_ROLE_GRANTS.get(name, frozenset()):
                pid = permission_index.get(f"{resource}.{action}")
                if pid is None:
                    continue
                grant_docs.append(
                    {
                        "_id": ObjectId(),
                        "role_id": role["_id"],
                        "permission_id": pid,
                        "created_at": now,
                    }
                )
        if role_docs:
            await roles.collection.insert_many(role_docs, session=session, ordered=True)
        if grant_docs:
            await grants.collection.insert_many(grant_docs, session=session, ordered=False)
        return created

    for name in role_names:
        role = await roles.find_one(
            {"business_account_id": business_account_id, "name": name},
            session=session,
        )
        if role is None:
            role = await roles.create(
                {
                    "business_account_id": business_account_id,
                    "name": name,
                    "description": f"System role: {name}",
                    "is_system_role": True,
                    "is_active": True,
                    "deleted_at": None,
                    "created_at": now,
                    "updated_at": now,
                },
                session=session,
            )
        created[name] = role
        wanted = SYSTEM_ROLE_GRANTS.get(name, frozenset())
        wanted_ids = {
            permission_index[f"{resource}.{action}"]
            for resource, action in wanted
            if f"{resource}.{action}" in permission_index
        }
        existing_rows = await grants.find_many(
            {"role_id": role["_id"]},
            limit=500,
            session=session,
        )
        existing_ids = {row["permission_id"] for row in existing_rows}
        # Drop grants that no longer belong to this system role (e.g. Sales Rep
        # accidentally holding admin permissions).
        stale_ids = existing_ids - wanted_ids
        if stale_ids:
            await grants.collection.delete_many(
                {"role_id": role["_id"], "permission_id": {"$in": list(stale_ids)}},
                session=session,
            )
            existing_ids -= stale_ids
        for pid in wanted_ids:
            if pid in existing_ids:
                continue
            grant_docs.append(
                {
                    "_id": ObjectId(),
                    "role_id": role["_id"],
                    "permission_id": pid,
                    "created_at": now,
                }
            )
            existing_ids.add(pid)
    if grant_docs:
        try:
            await grants.collection.insert_many(grant_docs, session=session, ordered=False)
        except (BulkWriteError, DuplicateKeyError):
            pass
    return created
