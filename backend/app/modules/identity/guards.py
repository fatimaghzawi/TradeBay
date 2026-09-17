"""Membership invariants that future invite / remove / demote flows must call.

These are the documented rules, not the full workflows. Call `assert_not_last_admin`
before removing a membership or changing its role.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.modules.identity.constants import SYSTEM_ROLE_BUSINESS_ADMIN, MembershipStatus
from app.modules.identity.exceptions import LastAdminError
from app.modules.identity.repository import MembershipRepository, RoleRepository
from app.shared.utils.objectid import parse_object_id


def would_remove_last_admin(
    *,
    membership_role_id: ObjectId,
    admin_role_id: ObjectId,
    active_admin_count: int,
) -> bool:
    """True when this membership is the only remaining active Business Admin."""
    return membership_role_id == admin_role_id and active_admin_count <= 1


async def assert_not_last_admin(
    *,
    business_account_id: str | ObjectId,
    membership: dict[str, Any],
    memberships: MembershipRepository | None = None,
    roles: RoleRepository | None = None,
) -> None:
    """Refuse to remove or demote the last active Business Admin of a company."""
    memberships = memberships or MembershipRepository()
    roles = roles or RoleRepository()
    business_id = parse_object_id(str(business_account_id))
    admin_role = await roles.find_one(
        {
            "business_account_id": business_id,
            "name": SYSTEM_ROLE_BUSINESS_ADMIN,
            "is_system_role": True,
        }
    )
    if admin_role is None:
        return
    if membership.get("role_id") != admin_role["_id"]:
        return
    count = await memberships.count(
        {
            "business_account_id": business_id,
            "role_id": admin_role["_id"],
            "status": MembershipStatus.ACTIVE,
        }
    )
    if would_remove_last_admin(
        membership_role_id=membership["role_id"],
        admin_role_id=admin_role["_id"],
        active_admin_count=count,
    ):
        raise LastAdminError()
