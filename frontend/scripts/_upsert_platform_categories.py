from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from _reset_demo_seed import CATEGORIES, _load_dotenv  # noqa: E402

                                     
LEGACY_SLUGS: dict[str, str] = {
    "food-beverages": "food-beverages",
    "packaged-foods": "food-beverages",
    "electronics": "electronics-electrical",
    "home-kitchen": "home-living",
    "office-supplies": "office-supplies",
    "construction": "construction-building-materials",
    "personal-care": "personal-care-cosmetics",
    "cleaning": "cleaning-hygiene",
    "farming": "agriculture-farming",
    "packaging": "packaging-supplies",
    "hospitality-supplies": "hospitality-restaurant-supplies",
    "beverages": "beverages",
    "pantry-staples": "grains-pulses-staples",
    "hardware": "construction-building-materials",
    "stationery": "office-supplies",
    "janitorial": "cleaning-hygiene",
    "agri-inputs": "agriculture-farming",
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

def main() -> None:
    _env()
    _load_dotenv()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DATABASE", "tradebay")
    if not uri:
        raise SystemExit("MONGODB_URI missing")
    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = client[db_name]
    cats = db["categories"]
    products = db["products"]
    now = datetime.now(timezone.utc)

    wanted_slugs = {spec["slug"] for spec in CATEGORIES}
    id_by_slug: dict[str, ObjectId] = {}

    for spec in CATEGORIES:
        slug = spec["slug"]
        existing = cats.find_one({"slug": slug})
        if existing is None:
                                                                           
            legacy = [
                old for old, new in LEGACY_SLUGS.items() if new == slug and old != slug
            ]
            for old in legacy:
                row = cats.find_one({"slug": old})
                if row is not None:
                    existing = row
                    break
        payload = {
            "name": spec["name"],
            "slug": slug,
            "description": spec["description"],
            "parent_category_id": None,
            "is_active": True,
            "display_order": spec["order"],
            "image_url": spec["image"],
            "updated_at": now,
        }
        if existing is None:
            doc_id = ObjectId()
            cats.insert_one({"_id": doc_id, "created_at": now, **payload})
            action = "created"
        else:
            doc_id = existing["_id"]
            cats.update_one({"_id": doc_id}, {"$set": payload})
            action = "updated"
        id_by_slug[slug] = doc_id
        print(f"{action:8} {slug:36} {spec['name']}")

    remapped = 0
    for old_slug, new_slug in LEGACY_SLUGS.items():
        if old_slug == new_slug:
            continue
        old = cats.find_one({"slug": old_slug})
        target_id = id_by_slug.get(new_slug)
        if old is None or target_id is None:
            continue
        if old["_id"] == target_id:
            continue
        result = products.update_many(
            {"category_id": old["_id"]},
            {"$set": {"category_id": target_id, "updated_at": now}},
        )
        remapped += result.modified_count
        cats.update_one(
            {"_id": old["_id"]},
            {"$set": {"is_active": False, "updated_at": now}},
        )
        print(f"merged   {old_slug} -> {new_slug} ({result.modified_count} products)")

    deactivated = 0
    for row in cats.find({}):
        if row.get("slug") in wanted_slugs:
            continue
        cats.update_one(
            {"_id": row["_id"]},
            {"$set": {"is_active": False, "updated_at": now}},
        )
        deactivated += 1

    active = cats.count_documents({"is_active": True, "parent_category_id": None})
    print(f"\nActive root categories: {active}")
    print(f"Products remapped: {remapped}")
    print(f"Legacy categories deactivated: {deactivated}")
    client.close()

if __name__ == "__main__":
    main()
