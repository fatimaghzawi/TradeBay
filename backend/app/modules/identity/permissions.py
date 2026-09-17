"""Permission catalog and system-role grants.

Authorization uses atomic `resource.action` codes only — never role-name checks.
Platform-only codes are never granted to trading-company roles.
"""

from __future__ import annotations

from app.core.constants import PermissionAction as A
from app.core.constants import PermissionResource as R
from app.modules.identity.constants import (
    SYSTEM_ROLE_BUSINESS_ADMIN,
    SYSTEM_ROLE_FINANCE,
    SYSTEM_ROLE_PLATFORM_ADMIN,
    SYSTEM_ROLE_PLATFORM_OPERATOR,
    SYSTEM_ROLE_SALES_MANAGER,
    SYSTEM_ROLE_SALES_REPRESENTATIVE,
    SYSTEM_ROLE_VIEWER,
)


def permission_code(resource: str, action: str) -> str:
    return f"{resource}.{action}"


# Full catalog — seeded at API startup. One dialect only (`resource.action`).
DEFAULT_PERMISSION_CATALOG: list[tuple[str, str, str]] = [
    (R.USERS, A.READ, "View users"),
    (R.USERS, A.INVITE, "Invite users"),
    (R.USERS, A.UPDATE, "Update users"),
    (R.USERS, A.REMOVE, "Remove users"),
    (R.ROLES, A.READ, "View roles"),
    (R.ROLES, A.MANAGE, "Manage roles"),
    (R.BUSINESSES, A.READ, "View businesses"),
    (R.BUSINESSES, A.MANAGE, "Manage business settings"),
    (R.PRODUCTS, A.READ, "View products"),
    (R.PRODUCTS, A.MANAGE, "Manage products"),
    (R.CATEGORIES, A.READ, "View categories"),
    (R.CATEGORIES, A.MANAGE, "Manage categories"),
    (R.INVENTORY, A.READ, "View inventory"),
    (R.INVENTORY, A.MANAGE, "Manage inventory"),
    (R.RFQS, A.READ, "View RFQs"),
    (R.RFQS, A.CREATE, "Create RFQs"),
    (R.RFQS, A.UPDATE, "Update or publish RFQs"),
    (R.RFQS, A.RESPOND, "Respond to RFQs"),
    (R.QUOTATIONS, A.READ, "View quotations"),
    (R.QUOTATIONS, A.CREATE, "Create quotations"),
    (R.QUOTATIONS, A.UPDATE, "Update quotations"),
    (R.QUOTATIONS, A.ACCEPT, "Accept a quotation and create the purchase order"),
    (R.ORDERS, A.READ, "View orders"),
    (R.ORDERS, A.CONFIRM, "Confirm a pending purchase order (supplier)"),
    (R.ORDERS, A.CANCEL, "Cancel an eligible order"),
    (R.SHIPMENTS, A.READ, "View shipments"),
    (R.SHIPMENTS, A.UPDATE, "Update shipment tracking"),
    (R.INVOICES, A.READ, "View invoices"),
    (R.INVOICES, A.CREATE, "Issue invoices"),
    (R.PAYMENTS, A.READ, "View payments"),
    (R.PAYMENTS, A.CREATE, "Record payments"),
    (R.CREDIT_NOTES, A.READ, "View credit notes"),
    (R.CREDIT_NOTES, A.CREATE, "Issue credit notes"),
    (R.REFUNDS, A.READ, "View refunds"),
    (R.REFUNDS, A.CREATE, "Request or record refunds"),
    (R.COMMISSIONS, A.READ, "View commission records"),
    (R.PAYABLES, A.READ, "View supplier payables"),
    (R.SETTLEMENTS, A.READ, "View settlement batches"),
    (R.SETTLEMENTS, A.APPROVE, "Approve settlement batches"),
    (R.REVIEWS, A.READ, "View reviews"),
    (R.REVIEWS, A.CREATE, "Leave a review"),
    (R.DISPUTES, A.READ, "View disputes"),
    (R.DISPUTES, A.CREATE, "Open a dispute"),
    (R.DISPUTES, A.RESOLVE, "Resolve disputes"),
    (R.NOTIFICATIONS, A.READ, "View notifications"),
    (R.SUPPLIERS, A.READ, "View supplier profiles"),
    (R.SUPPLIERS, A.VERIFY, "Verify or revoke supplier selling rights"),
    (R.SETTINGS, A.MANAGE, "Manage platform settings"),
    (R.CONVERSATIONS, A.READ, "View conversations"),
    (R.CONVERSATIONS, A.CREATE, "Start conversations"),
    (R.MESSAGES, A.CREATE, "Send messages"),
    (R.NEGOTIATIONS, A.READ, "View negotiations"),
    (R.NEGOTIATIONS, A.CREATE, "Open a negotiation"),
    (R.NEGOTIATIONS, A.MANAGE, "Counter, accept, or reject offers"),
    (R.SOURCING, A.READ, "View sourcing requests"),
    (R.SOURCING, A.CREATE, "Create sourcing requests"),
    (R.BUSINESS_PLANS, A.READ, "View business plans"),
    (R.BUSINESS_PLANS, A.CREATE, "Create business plans"),
    (R.BUSINESS_PLANS, A.MANAGE, "Update or convert business plans"),
]

# Platform-wide — never granted to trading-company roles.
PLATFORM_ONLY: frozenset[tuple[str, str]] = frozenset(
    {
        (R.SUPPLIERS, A.VERIFY),
        (R.DISPUTES, A.RESOLVE),
        (R.SETTLEMENTS, A.APPROVE),
        (R.SETTINGS, A.MANAGE),
        (R.CATEGORIES, A.MANAGE),
    }
)

ALL_CODES: frozenset[tuple[str, str]] = frozenset((r, a) for r, a, _ in DEFAULT_PERMISSION_CATALOG)
READ_CODES: frozenset[tuple[str, str]] = frozenset((r, a) for r, a, _ in DEFAULT_PERMISSION_CATALOG if a == A.READ)
TRADING_CODES: frozenset[tuple[str, str]] = ALL_CODES - PLATFORM_ONLY


def _sales_manager_codes() -> frozenset[tuple[str, str]]:
    return frozenset(
        {
            (R.USERS, A.READ),
            (R.USERS, A.INVITE),
            (R.ROLES, A.READ),
            (R.BUSINESSES, A.READ),
            (R.PRODUCTS, A.READ),
            (R.PRODUCTS, A.MANAGE),
            (R.CATEGORIES, A.READ),
            (R.INVENTORY, A.READ),
            (R.INVENTORY, A.MANAGE),
            (R.RFQS, A.READ),
            (R.RFQS, A.CREATE),
            (R.RFQS, A.UPDATE),
            (R.RFQS, A.RESPOND),
            (R.QUOTATIONS, A.READ),
            (R.QUOTATIONS, A.CREATE),
            (R.QUOTATIONS, A.UPDATE),
            (R.QUOTATIONS, A.ACCEPT),
            (R.ORDERS, A.READ),
            (R.ORDERS, A.CONFIRM),
            (R.ORDERS, A.CANCEL),
            (R.SHIPMENTS, A.READ),
            (R.SHIPMENTS, A.UPDATE),
            (R.INVOICES, A.READ),
            (R.PAYMENTS, A.READ),
            (R.REVIEWS, A.READ),
            (R.REVIEWS, A.CREATE),
            (R.DISPUTES, A.READ),
            (R.DISPUTES, A.CREATE),
            (R.NOTIFICATIONS, A.READ),
            (R.SUPPLIERS, A.READ),
            (R.CONVERSATIONS, A.READ),
            (R.CONVERSATIONS, A.CREATE),
            (R.MESSAGES, A.CREATE),
            (R.NEGOTIATIONS, A.READ),
            (R.NEGOTIATIONS, A.CREATE),
            (R.NEGOTIATIONS, A.MANAGE),
            (R.SOURCING, A.READ),
            (R.SOURCING, A.CREATE),
            (R.BUSINESS_PLANS, A.READ),
            (R.BUSINESS_PLANS, A.CREATE),
            (R.BUSINESS_PLANS, A.MANAGE),
        }
    )


def _sales_representative_codes() -> frozenset[tuple[str, str]]:
    return frozenset(
        {
            (R.USERS, A.READ),
            (R.BUSINESSES, A.READ),
            (R.PRODUCTS, A.READ),
            (R.CATEGORIES, A.READ),
            (R.INVENTORY, A.READ),
            (R.RFQS, A.READ),
            (R.RFQS, A.RESPOND),
            (R.QUOTATIONS, A.READ),
            (R.QUOTATIONS, A.CREATE),
            (R.QUOTATIONS, A.UPDATE),
            (R.ORDERS, A.READ),
            (R.SHIPMENTS, A.READ),
            (R.NOTIFICATIONS, A.READ),
            (R.SUPPLIERS, A.READ),
            (R.CONVERSATIONS, A.READ),
            (R.CONVERSATIONS, A.CREATE),
            (R.MESSAGES, A.CREATE),
            (R.NEGOTIATIONS, A.READ),
            (R.NEGOTIATIONS, A.CREATE),
            (R.NEGOTIATIONS, A.MANAGE),
            (R.SOURCING, A.READ),
            (R.SOURCING, A.CREATE),
            (R.REVIEWS, A.READ),
            (R.DISPUTES, A.READ),
        }
    )


def _finance_codes() -> frozenset[tuple[str, str]]:
    return READ_CODES | {
        (R.INVOICES, A.CREATE),
        (R.PAYMENTS, A.CREATE),
        (R.CREDIT_NOTES, A.CREATE),
        (R.REFUNDS, A.CREATE),
    }


def _platform_operator_codes() -> frozenset[tuple[str, str]]:
    return READ_CODES | PLATFORM_ONLY | {
        (R.DISPUTES, A.CREATE),
    }


SYSTEM_ROLE_GRANTS: dict[str, frozenset[tuple[str, str]]] = {
    SYSTEM_ROLE_BUSINESS_ADMIN: TRADING_CODES,
    SYSTEM_ROLE_SALES_MANAGER: _sales_manager_codes(),
    SYSTEM_ROLE_SALES_REPRESENTATIVE: _sales_representative_codes(),
    SYSTEM_ROLE_FINANCE: _finance_codes(),
    SYSTEM_ROLE_VIEWER: READ_CODES,
    SYSTEM_ROLE_PLATFORM_ADMIN: ALL_CODES,
    SYSTEM_ROLE_PLATFORM_OPERATOR: _platform_operator_codes(),
}

TRADING_SYSTEM_ROLES: tuple[str, ...] = (
    SYSTEM_ROLE_BUSINESS_ADMIN,
    SYSTEM_ROLE_SALES_MANAGER,
    SYSTEM_ROLE_SALES_REPRESENTATIVE,
    SYSTEM_ROLE_FINANCE,
    SYSTEM_ROLE_VIEWER,
)

PLATFORM_SYSTEM_ROLES: tuple[str, ...] = (
    SYSTEM_ROLE_PLATFORM_ADMIN,
    SYSTEM_ROLE_PLATFORM_OPERATOR,
)
