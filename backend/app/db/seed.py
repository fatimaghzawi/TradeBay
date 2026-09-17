"""Idempotent startup seed: permissions, platform tenant, and settings."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.core.logging import get_logger
from app.modules.identity.constants import (
    SYSTEM_ROLE_PLATFORM_ADMIN,
    BusinessAccountStatus,
    BusinessAccountType,
)
from app.modules.identity.permissions import (
    DEFAULT_PERMISSION_CATALOG,
    PLATFORM_SYSTEM_ROLES,
    SYSTEM_ROLE_GRANTS,
    TRADING_SYSTEM_ROLES,
)
from app.modules.identity.repository import (
    BusinessRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
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


async def seed_startup() -> None:
    await seed_permissions()
    permission_index = await _permission_index()
    platform = await seed_platform_business(permission_index)
    await seed_settings()
    logger.info(
        "startup_seed_complete",
        platform_business_id=str(platform["_id"]) if platform else None,
    )


async def seed_permissions() -> None:
    repo = PermissionRepository()
    now = utc_now()
    for resource, action, description in DEFAULT_PERMISSION_CATALOG:
        existing = await repo.get_by_resource_action(resource, action)
        if existing is None:
            await repo.create(
                {
                    "resource": resource,
                    "action": action,
                    "description": description,
                    "created_at": now,
                }
            )


async def seed_trading_roles(
    business_account_id: ObjectId,
    *,
    permission_index: dict[str, ObjectId] | None = None,
    session: MongoSession = None,
) -> dict[str, dict[str, Any]]:
    """Create the five undeletable system roles for a trading company."""
    index = permission_index or await _permission_index()
    return await _seed_roles_for_business(
        business_account_id, TRADING_SYSTEM_ROLES, index, session=session
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
                "address": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    index = permission_index or await _permission_index()
    await _seed_roles_for_business(existing["_id"], PLATFORM_SYSTEM_ROLES, index)
    # Platform staff also need a Viewer-class read role set; Admin/Operator cover it.
    _ = SYSTEM_ROLE_PLATFORM_ADMIN
    return existing


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
    repo = PermissionRepository()
    rows = await repo.find_many({}, limit=500)
    return {f"{row['resource']}.{row['action']}": row["_id"] for row in rows}


async def _seed_roles_for_business(
    business_account_id: ObjectId,
    role_names: tuple[str, ...],
    permission_index: dict[str, ObjectId],
    *,
    session: MongoSession = None,
) -> dict[str, dict[str, Any]]:
    roles = RoleRepository()
    grants = RolePermissionRepository()
    now = utc_now()
    created: dict[str, dict[str, Any]] = {}
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
                    "created_at": now,
                    "updated_at": now,
                },
                session=session,
            )
        created[name] = role
        wanted = SYSTEM_ROLE_GRANTS.get(name, frozenset())
        existing_ids = {
            str(pid)
            for pid in await grants.list_permission_ids_for_role(role["_id"], session=session)
        }
        for resource, action in wanted:
            pid = permission_index.get(f"{resource}.{action}")
            if pid is None or str(pid) in existing_ids:
                continue
            await grants.create(
                {"role_id": role["_id"], "permission_id": pid, "created_at": now},
                session=session,
            )
            existing_ids.add(str(pid))
    return created
