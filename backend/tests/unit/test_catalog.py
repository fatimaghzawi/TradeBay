
from __future__ import annotations

from app.modules.catalog.service import CatalogService, _ranges_overlap, _slugify


def test_slugify_basic() -> None:
    assert _slugify("USB-C Charger!") == "usb-c-charger"
    assert _slugify("  Keyboards  ") == "keyboards"

def test_price_ranges_overlap_logic() -> None:
    assert _ranges_overlap(50, 99, 80, 120) is True
    assert _ranges_overlap(50, 99, 100, 200) is False
    assert _ranges_overlap(500, None, 400, 600) is True
    assert _ranges_overlap(500, None, 100, 499) is False

def test_resolve_unit_price_picks_correct_tier() -> None:
    service = CatalogService()
    tiers = [
        {
            "id": "1",
            "min_quantity": 50,
            "max_quantity": 99,
            "unit_price": "4.50",
            "is_active": True,
        },
        {
            "id": "2",
            "min_quantity": 100,
            "max_quantity": 499,
            "unit_price": "4.10",
            "is_active": True,
        },
        {
            "id": "3",
            "min_quantity": 500,
            "max_quantity": None,
            "unit_price": "3.70",
            "is_active": True,
        },
    ]
    assert service.resolve_unit_price(tiers, 75)["id"] == "1"
    assert service.resolve_unit_price(tiers, 250)["id"] == "2"
    assert service.resolve_unit_price(tiers, 800)["id"] == "3"
    assert service.resolve_unit_price(tiers, 10) is None

def test_serialize_product_includes_featured_flag() -> None:
    from datetime import datetime, timezone

    from app.modules.catalog.service import serialize_product
    from bson import ObjectId

    oid = ObjectId()
    now = datetime.now(timezone.utc)
    payload = serialize_product(
        {
            "_id": oid,
            "supplier_id": oid,
            "business_account_id": oid,
            "category_id": oid,
            "sku": "LEV-OIL-1L",
            "name": "Extra Virgin Olive Oil 1L",
            "slug": "lev-oil-1l",
            "moq": 12,
            "lead_time_days": 3,
            "status": "active",
            "is_featured": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert payload["is_featured"] is True

    missing = serialize_product(
        {
            "_id": oid,
            "supplier_id": oid,
            "business_account_id": oid,
            "category_id": oid,
            "sku": "PLAIN",
            "name": "Plain",
            "slug": "plain",
            "moq": 1,
            "lead_time_days": 0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert missing["is_featured"] is False
