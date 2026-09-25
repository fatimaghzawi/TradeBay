from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bson import Decimal128, ObjectId
from pymongo import MongoClient

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from _reset_demo_seed import (  # noqa: E402
    CATEGORIES,
    FEATURED_LANDING_SKUS,
    PRODUCTS_BY_SUPPLIER,
    SUPPLIER_DOMAINS,
    _load_dotenv,
    _product_description,
    _resolve_unit,
    _slugify,
    _asset_url,
)

RETIRE_PREFIXES = {
    "south": "SLW-",
    "tripoli": "TPH-",
    "keserwan": "KFC-",
}

def _env() -> None:
    for path in (REPO / ".env", BACKEND / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))

def _money(value: Decimal) -> Decimal128:
    return Decimal128(str(value))

def _price_docs(product_id: ObjectId, moq: int, price_dec: Decimal, now: datetime) -> list[dict]:
    return [
        {
            "_id": ObjectId(),
            "product_id": product_id,
            "min_quantity": moq,
            "max_quantity": moq * 4 - 1,
            "unit_price": _money(price_dec),
            "currency": "USD",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": ObjectId(),
            "product_id": product_id,
            "min_quantity": moq * 4,
            "max_quantity": None,
            "unit_price": _money((price_dec * Decimal("0.92")).quantize(Decimal("0.01"))),
            "currency": "USD",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]

def _image_docs(product_id: ObjectId, name: str, image_rel: str, cat_key: str, sku: str, now: datetime) -> list[dict]:
    return [
        {
            "_id": ObjectId(),
            "product_id": product_id,
            "url": _asset_url(image_rel),
            "alt_text": name,
            "is_primary": True,
            "display_order": 0,
            "created_at": now,
        }
    ]

def main() -> None:
    _env()
    _load_dotenv()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DATABASE", "tradebay")
    if not uri:
        raise SystemExit("MONGODB_URI missing")

    print(f"Connecting to {db_name}...", flush=True)
    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = client[db_name]
    db.command("ping")
    print("Mongo ping ok", flush=True)
    now = datetime.now(timezone.utc)

    slug_to_id: dict[str, ObjectId] = {}
    key_to_id: dict[str, ObjectId] = {}
    for spec in CATEGORIES:
        row = db["categories"].find_one({"slug": spec["slug"], "is_active": True})
        if row is None:
            row = db["categories"].find_one({"slug": spec["slug"]})
        if row is None:
            print(f"WARN category missing: {spec['slug']}")
            continue
        slug_to_id[spec["slug"]] = row["_id"]
        key_to_id[spec["key"]] = row["_id"]

    created = 0
    updated = 0
    images_written = 0
    deactivated = 0

    for supplier_key, rows in PRODUCTS_BY_SUPPLIER.items():
        domain = SUPPLIER_DOMAINS[supplier_key]
        business = db["business_accounts"].find_one(
            {"email_domain": domain.lower(), "type": "supplier"}
        )
        if business is None:
            print(f"WARN supplier missing: {supplier_key} ({domain})")
            continue
        profile = db["supplier_profiles"].find_one(
            {"business_account_id": business["_id"]}
        )
        if profile is None:
            print(f"WARN supplier profile missing: {business.get('name')}")
            continue
        owner = db["users"].find_one({"email": str(business.get("contact_email") or "").lower()})
        creator_id = owner["_id"] if owner else None
        wanted_skus = {str(row[0]).upper() for row in rows}

        created_here = 0
        updated_here = 0
        for sku, name, unit, origin, moq, lead, price, stock, image_rel, cat_key in rows:
            sku = str(sku).upper()
            cat_id = key_to_id.get(str(cat_key))
            if cat_id is None:
                print(f"WARN skip {sku}: category {cat_key} missing")
                continue
            resolved_unit = _resolve_unit(str(unit))
            moq_i = int(moq)
            lead_i = int(lead)
            price_dec = Decimal(str(price))
            stock_dec = Decimal(str(stock))
            payload = {
                "supplier_id": profile["_id"],
                "business_account_id": business["_id"],
                "category_id": cat_id,
                "sku": sku,
                "name": name,
                "slug": _slugify(f"{sku}-{name}"),
                "description": _product_description(
                    name, business["name"], origin, moq_i, resolved_unit, lead_i
                ),
                "unit": resolved_unit,
                "origin": origin,
                "moq": moq_i,
                "lead_time_days": lead_i,
                "status": "active",
                "is_featured": sku in FEATURED_LANDING_SKUS,
                "is_demo_seed": True,
                "data_source": "synthetic_demo",
                "updated_at": now,
            }
            existing = db["products"].find_one(
                {"business_account_id": business["_id"], "sku": sku}
            )
            rewrite_media = True
            if existing is None:
                product_id = ObjectId()
                payload["_id"] = product_id
                payload["created_at"] = now
                db["products"].insert_one(payload)
                inventory_id = ObjectId()
                db["inventories"].insert_one(
                    {
                        "_id": inventory_id,
                        "product_id": product_id,
                        "available_quantity": _money(stock_dec),
                        "reserved_quantity": _money(Decimal("0")),
                        "updated_at": now,
                    }
                )
                db["inventory_transactions"].insert_one(
                    {
                        "_id": ObjectId(),
                        "inventory_id": inventory_id,
                        "product_id": product_id,
                        "transaction_type": "initial_stock",
                        "quantity": _money(stock_dec),
                        "reference_type": "product",
                        "reference_id": product_id,
                        "previous_available": _money(Decimal("0")),
                        "previous_reserved": _money(Decimal("0")),
                        "new_available": _money(stock_dec),
                        "new_reserved": _money(Decimal("0")),
                        "reason": "Demo opening stock",
                        "created_by": creator_id,
                        "created_at": now,
                    }
                )
                created += 1
                created_here += 1
            else:
                product_id = existing["_id"]
                db["products"].update_one({"_id": product_id}, {"$set": payload})
                inv = db["inventories"].find_one({"product_id": product_id})
                if inv is None:
                    db["inventories"].insert_one(
                        {
                            "_id": ObjectId(),
                            "product_id": product_id,
                            "available_quantity": _money(stock_dec),
                            "reserved_quantity": _money(Decimal("0")),
                            "updated_at": now,
                        }
                    )
                else:
                    db["inventories"].update_one(
                        {"_id": inv["_id"]},
                        {
                            "$set": {
                                "available_quantity": _money(stock_dec),
                                "updated_at": now,
                            }
                        },
                    )
                img_n = db["product_images"].count_documents({"product_id": product_id})
                price_n = db["product_prices"].count_documents(
                    {"product_id": product_id, "is_active": True}
                )
                wanted_url = _asset_url(str(image_rel))
                primary = db["product_images"].find_one(
                    {"product_id": product_id, "is_primary": True}
                )
                rewrite_media = (
                    img_n != 1
                    or price_n < 2
                    or (primary or {}).get("url") != wanted_url
                )
                updated += 1
                updated_here += 1

            if rewrite_media:
                db["product_prices"].delete_many({"product_id": product_id})
                db["product_prices"].insert_many(_price_docs(product_id, moq_i, price_dec, now))
                db["product_images"].delete_many({"product_id": product_id})
                gallery = _image_docs(product_id, name, str(image_rel), str(cat_key), sku, now)
                db["product_images"].insert_many(gallery)
                images_written += len(gallery)

        retire_or: list[dict] = [{"is_demo_seed": True}]
        prefix = RETIRE_PREFIXES.get(supplier_key)
        if prefix:
            retire_or.append({"sku": {"$regex": f"^{prefix}"}})
        result = db["products"].update_many(
            {
                "business_account_id": business["_id"],
                "sku": {"$nin": list(wanted_skus)},
                "$or": retire_or,
            },
            {"$set": {"status": "inactive", "is_featured": False, "updated_at": now}},
        )
        deactivated += int(result.modified_count)
        print(
            f"OK {business['name']}: {len(rows)} SKUs "
            f"(created {created_here}, updated {updated_here}, retired {result.modified_count})",
            flush=True,
        )

    print()
    print(f"Created:      {created}")
    print(f"Updated:      {updated}")
    print(f"Images:       {images_written}")
    print(f"Deactivated:  {deactivated}")
    print(f"Database:     {db_name}")
    client.close()

if __name__ == "__main__":
    main()
