
from __future__ import annotations

from typing import Any

from app.core.exceptions import ForbiddenError

PROTECTED_COLLECTIONS = frozenset(
    {
        "audit_logs",
        "customer_invoices",
        "payments",
        "credit_notes",
        "refunds",
        "financial_transactions",
        "commission_records",
        "platform_transactions",
        "orders",
        "order_items",
        "rfqs",
        "quotations",
        "users",
        "business_accounts",
        "supplier_profiles",
    }
)

                                                                 
SOFT_DELETE_FILTERS: dict[str, dict[str, Any]] = {
    "roles": {"deleted_at": None, "is_active": {"$ne": False}},
    "product_prices": {"deleted_at": None},
    "product_images": {"deleted_at": None},
    "messages": {"deleted_at": None},
    "products": {"status": {"$ne": "inactive"}},
    "categories": {"is_active": {"$ne": False}},
    "users": {"status": {"$nin": ["deactivated"]}},
    "business_memberships": {"status": {"$nin": ["removed"]}},
}

def assert_not_protected_hard_delete(collection: str) -> None:
    if collection in PROTECTED_COLLECTIONS:
        raise ForbiddenError(
            "This record is kept for audit and commercial history and cannot be deleted."
        )

def exclude_soft_deleted(collection: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(query or {})
    extra = SOFT_DELETE_FILTERS.get(collection)
    if extra:
        for key, value in extra.items():
            merged.setdefault(key, value)
    return merged
