"""Wipe the TradeBay database and seed a coherent Lebanese B2B demo.

All trading companies, users, SKUs, RFQs, orders, and chats are SYNTHETIC.
Public Lebanese firms researched for category inspiration are documented in
`app/db/demo/SOURCES.md` and are never inserted as TradeBay members.

Creates:
  platform admin → synthetic suppliers/buyers → categories → products →
  prices → inventory → marketplace activity (RFQ → quote → PO → invoice).

Usage (from backend/):
  python _reset_demo_seed.py
"""

from __future__ import annotations

import asyncio
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from bson import ObjectId


def _load_dotenv() -> None:
    for path in (
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parent / ".env",
    ):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


DEMO_PASSWORD = "TradeBay123!"
ASSET_PREFIX = "/images/assets"
LOGO_PREFIX = "/images/logos"

# Business logos used as user profile images (company mark, not personal photo).
LOGOS = {
    "tradebay": f"{LOGO_PREFIX}/tradebay.svg",
    "levant": f"{LOGO_PREFIX}/cedrus-foods.png",
    "bekaa": f"{LOGO_PREFIX}/lebtech-solutions.png",
    "cedar": f"{LOGO_PREFIX}/beirut-build.png",
    "beirut": f"{LOGO_PREFIX}/beirut-mart.svg",
    "harbor": f"{LOGO_PREFIX}/harbor-hospitality.svg",
    "south": f"{LOGO_PREFIX}/tyre-fresh.png",
    "pack": f"{LOGO_PREFIX}/beirut-pack.png",
    "zahle": f"{LOGO_PREFIX}/bekaa-harvest.png",
    "tripoli": f"{LOGO_PREFIX}/safawi-plastics.png",
    "keserwan": f"{LOGO_PREFIX}/cedars-pharma.png",
    "saida": f"{LOGO_PREFIX}/mountain-spices.png",
    "baalbek": f"{LOGO_PREFIX}/sour-ceramics.png",
    "achrafieh": f"{LOGO_PREFIX}/levant-textile.png",
    "jbeil": f"{LOGO_PREFIX}/nahr-energy.png",
}


def _slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:140] or "item"


SUPPLIER_DOMAINS: dict[str, str] = {
    "levant": "cedrusfoods.com",
    "bekaa": "lebtechsolutions.com",
    "cedar": "beirutbuild.com",
    "south": "tyrefresh.com",
    "pack": "beirutpack.com",
    "zahle": "bekaaharvest.com",
    "tripoli": "safawiplastics.com",
    "keserwan": "cedarspharma.com",
    "saida": "mountainspices.com",
    "baalbek": "sourceramics.com",
    "achrafieh": "levanttextile.com",
    "jbeil": "nahrenergy.com",
}

def _resolve_unit(unit: str) -> str:
    if unit in {"piece", "box", "carton", "kg", "liter", "unit"}:
        return unit
    if unit in {"bag", "pack", "bundle", "roll"}:
        return "carton"
    return "unit"


def _asset_url(rel: str) -> str:
    if rel.startswith("/"):
        return rel
    return f"{ASSET_PREFIX}/{rel}"


def _gallery(primary: str, cat_key: str = "", sku: str = "", count: int = 1) -> list[str]:
    """One photo per SKU — the file that actually shows this product."""
    return [primary]


def _product_description(
    name: str,
    business_name: str,
    origin: str,
    moq: int,
    unit: str,
    lead: int,
) -> str:
    day_label = "day" if lead == 1 else "days"
    return (
        f"{name} supplied wholesale by {business_name}. "
        f"Origin: {origin}. Minimum order {moq} {unit}. "
        f"Typical lead time {lead} {day_label}. "
        "Demo catalog listing — not an official company price."
    )


def _addr(
    street: str,
    city: str,
    governorate: str,
    *,
    district: str | None = None,
    postal_code: str = "00000",
    country: str = "Lebanon",
) -> dict[str, str]:
    return {
        "street": street,
        "city": city,
        "district": district or city,
        "governorate": governorate,
        "postal_code": postal_code,
        "country": country,
    }


# ── Catalog blueprint (synced to public/images/assets) ─────────────────────

CATEGORIES: list[dict[str, Any]] = [
    {
        "key": "food",
        "name": "Food & Beverages",
        "slug": "food-beverages",
        "description": "Oils, spices, pantry goods, and Lebanese specialty foods.",
        "image": f"{ASSET_PREFIX}/cat/cat_food_beverages.png",
        "order": 10,
    },
    {
        "key": "produce",
        "name": "Fresh Produce",
        "slug": "fresh-produce",
        "description": "Fruits, vegetables, and market-fresh produce for wholesale.",
        "image": f"{ASSET_PREFIX}/cat/cat_fresh_produce.png",
        "order": 20,
    },
    {
        "key": "meat",
        "name": "Meat, Poultry & Seafood",
        "slug": "meat-poultry-seafood",
        "description": "Chilled and frozen protein for retail and hospitality.",
        "image": f"{ASSET_PREFIX}/cat/cat_meat_poultry_seafood.png",
        "order": 30,
    },
    {
        "key": "dairy",
        "name": "Dairy & Eggs",
        "slug": "dairy-eggs",
        "description": "Milk, cheese, yoghurt, and eggs for daily restock.",
        "image": f"{ASSET_PREFIX}/cat/cat_dairy_eggs.png",
        "order": 40,
    },
    {
        "key": "pantry",
        "name": "Grains, Pulses & Staples",
        "slug": "grains-pulses-staples",
        "description": "Rice, flour, pulses, oils, and dry goods.",
        "image": f"{ASSET_PREFIX}/cat/cat_grains_pulses_staples.png",
        "order": 50,
    },
    {
        "key": "beverages",
        "name": "Beverages",
        "slug": "beverages",
        "description": "Water, juices, coffee, tea, and bottled drinks.",
        "image": f"{ASSET_PREFIX}/cat/cat_beverages.png",
        "order": 60,
    },
    {
        "key": "packaging",
        "name": "Packaging & Supplies",
        "slug": "packaging-supplies",
        "description": "Cartons, tape, containers, and packing materials.",
        "image": f"{ASSET_PREFIX}/cat/cat_packaging_supplies.png",
        "order": 70,
    },
    {
        "key": "cleaning",
        "name": "Cleaning & Hygiene",
        "slug": "cleaning-hygiene",
        "description": "Janitorial chemicals, soaps, and facility hygiene.",
        "image": f"{ASSET_PREFIX}/cat/cat_cleaning_hygiene.png",
        "order": 80,
    },
    {
        "key": "care",
        "name": "Personal Care & Cosmetics",
        "slug": "personal-care-cosmetics",
        "description": "Hygiene, beauty, and personal-care wholesale packs.",
        "image": f"{ASSET_PREFIX}/cat/cat_personal_care_cosmetics.png",
        "order": 90,
    },
    {
        "key": "textiles",
        "name": "Textiles & Garments",
        "slug": "textiles-garments",
        "description": "Apparel, fabrics, and garment wholesale.",
        "image": f"{ASSET_PREFIX}/cat/cat_textiles_garments.png",
        "order": 100,
    },
    {
        "key": "elect",
        "name": "Electronics & Electrical",
        "slug": "electronics-electrical",
        "description": "Office tech, cables, peripherals, and electrical goods.",
        "image": f"{ASSET_PREFIX}/cat/cat_electronics_electrical.png",
        "order": 110,
    },
    {
        "key": "home",
        "name": "Home & Living",
        "slug": "home-living",
        "description": "Housewares, furniture, and living essentials.",
        "image": f"{ASSET_PREFIX}/cat/cat_home_living.png",
        "order": 120,
    },
    {
        "key": "office",
        "name": "Office Supplies",
        "slug": "office-supplies",
        "description": "Stationery, paper, and workplace consumables.",
        "image": f"{ASSET_PREFIX}/cat/cat_office_supplies.png",
        "order": 130,
    },
    {
        "key": "const",
        "name": "Construction & Building Materials",
        "slug": "construction-building-materials",
        "description": "Cement, hardware, and site supplies.",
        "image": f"{ASSET_PREFIX}/cat/cat_construction_building.png",
        "order": 140,
    },
    {
        "key": "auto",
        "name": "Automotive & Spare Parts",
        "slug": "automotive-spare-parts",
        "description": "Vehicle parts, tyres, oils, and garage supplies.",
        "image": f"{ASSET_PREFIX}/cat/cat_automotive_spare_parts.png",
        "order": 150,
    },
    {
        "key": "farming",
        "name": "Agriculture & Farming",
        "slug": "agriculture-farming",
        "description": "Seeds, inputs, and farm-adjacent goods.",
        "image": f"{ASSET_PREFIX}/cat/cat_agriculture_farming.png",
        "order": 160,
    },
    {
        "key": "pharma",
        "name": "Pharmaceuticals & Medical Supplies",
        "slug": "pharmaceuticals-medical-supplies",
        "description": "OTC, clinic consumables, and medical supplies.",
        "image": f"{ASSET_PREFIX}/cat/cat_pharmaceuticals_medical.png",
        "order": 170,
    },
    {
        "key": "industrial",
        "name": "Industrial Equipment & Tools",
        "slug": "industrial-equipment-tools",
        "description": "Power tools, workshop gear, and industrial equipment.",
        "image": f"{ASSET_PREFIX}/cat/cat_industrial_equipment.png",
        "order": 180,
    },
    {
        "key": "hospitality",
        "name": "Hospitality & Restaurant Supplies",
        "slug": "hospitality-restaurant-supplies",
        "description": "Disposables, tableware, and HORECA guest supplies.",
        "image": f"{ASSET_PREFIX}/cat/cat_hospitality_restaurant.png",
        "order": 190,
    },
    {
        "key": "pets",
        "name": "Pets & Animal Care",
        "slug": "pets-animal-care",
        "description": "Pet food, accessories, and animal-care wholesale.",
        "image": f"{ASSET_PREFIX}/cat/cat_pets_animal_care.png",
        "order": 200,
    },
]

# Each product: (sku, name, unit, origin, moq, lead, base_price, stock, image_rel, category_key)
# image_rel is under /images/assets/
FEATURED_LANDING_SKUS = {
    "LEV-OIL-1L",
    "ZFI-HONEY",
    "BKT-MON-24",
    "CDR-BLOCK-20",
    "TYR-FISH-ICE",
    "MSP-TEA-HERB",
}

PRODUCTS_BY_SUPPLIER: dict[str, list[tuple[Any, ...]]] = {
    # Names and photos are 1:1 with the asset file. One image per SKU.
    "levant": [
        ("LEV-OIL-1L", "Extra Virgin Olive Oil 1L", "carton", "Lebanon", 12, 3, "18.50", "480", "food/foodd1.png", "food"),
        ("LEV-BREAD-MIX", "Bakery Bread Assortment", "carton", "Lebanon", 8, 2, "16.40", "140", "food/food1.png", "food"),
        ("LEV-PASTRY-MIX", "Pastry and Cake Assortment", "carton", "Lebanon", 8, 3, "19.80", "110", "food/food2.png", "food"),
        ("LEV-PANTRY-JAR", "Dry Goods Jars Assortment", "carton", "Lebanon", 10, 4, "14.50", "160", "food/food3.png", "pantry"),
        ("LEV-PASTA-5", "Durum Pasta Assortment", "carton", "Italy", 10, 5, "12.60", "300", "food/food4.png", "pantry"),
        ("LEV-MILK-PLANT", "Plant Milk and Nut Mix", "carton", "Lebanon", 8, 3, "15.20", "120", "food/food5.png", "dairy"),
        ("LEV-CHOC-MIX", "Assorted Chocolate", "carton", "Belgium", 6, 6, "22.00", "90", "food/food6.png", "food"),
    ],
    "bekaa": [
        ("BKT-CAM-DSLR", "Digital Camera Kit", "piece", "Japan", 2, 12, "640.00", "18", "elect/elect0.png", "elect"),
        ("BKT-LAPTOP-I5", "Business Laptop 14in", "piece", "China", 2, 14, "520.00", "28", "elect/elect1.png", "elect"),
        ("BKT-PHONE-5G", "5G Smartphone", "piece", "China", 4, 10, "280.00", "40", "elect/elect2.png", "elect"),
        ("BKT-EARBUDS", "True Wireless Earbuds", "piece", "China", 12, 6, "42.00", "160", "elect/elect3.png", "elect"),
        ("BKT-WATCH", "Smart Watch", "piece", "China", 8, 7, "89.00", "70", "elect/elect4.png", "elect"),
        ("BKT-HEADSET", "Wireless Over-Ear Headphones", "piece", "China", 8, 6, "58.00", "90", "elect/elect5.png", "elect"),
        ("BKT-TABLET-10", "Tablet 11in with Stylus", "piece", "China", 4, 11, "165.00", "36", "elect/elect6.png", "elect"),
        ("BKT-MON-24", "27in Office Monitor", "piece", "China", 4, 10, "145.00", "45", "elect/elect7.png", "elect"),
        ("BKT-CONSOLE", "Portable Game Console", "piece", "China", 4, 12, "210.00", "24", "elect/elect8.png", "elect"),
        ("BKT-ACTION", "Action Camera", "piece", "China", 6, 8, "96.00", "50", "elect/elect9.png", "elect"),
        ("BKT-PRINT-INK", "Color Inkjet Printer", "piece", "Vietnam", 2, 12, "89.00", "22", "elect/elect10.png", "elect"),
        ("BKT-ROUTER", "Dual-Band Wi-Fi Router", "piece", "China", 6, 8, "54.00", "60", "elect/elect11.png", "elect"),
        ("BKT-KB-RGB", "Keyboard and Mouse Set", "box", "China", 10, 5, "38.00", "120", "elect/elect12.png", "elect"),
    ],
    "cedar": [
        ("CDR-BLOCK-20", "Clay Bricks and Concrete Blocks", "piece", "Lebanon", 200, 3, "0.85", "8000", "const/const1.png", "const"),
        ("CDR-REBAR-12", "Steel Rebar Bundle", "unit", "Turkey", 10, 5, "48.00", "180", "const/const2.png", "const"),
        ("CDR-TIMBER", "Structural Timber Beams", "piece", "Russia", 20, 6, "24.00", "220", "const/const3.png", "const"),
        ("CDR-PAINT-20", "Paint Buckets and Roller Kit", "piece", "Lebanon", 8, 4, "34.00", "110", "const/const4.png", "const"),
        ("CDR-DRILL-18", "Cordless Drill Kit", "piece", "China", 4, 8, "89.00", "40", "const/const5.png", "industrial"),
        ("CDR-TOOLS", "Site Hand Tool Set", "box", "China", 8, 5, "28.00", "95", "const/const6.png", "industrial"),
        ("CDR-PPE", "Safety Helmet and PPE Kit", "box", "China", 12, 4, "18.50", "160", "const/const7.png", "const"),
        ("CDR-LADDER", "Aluminium Step Ladder", "piece", "China", 6, 7, "42.00", "55", "const/const10.png", "industrial"),
        ("CDR-SAW-CIRC", "Circular Saw", "piece", "China", 4, 8, "72.00", "35", "const/const11.png", "industrial"),
        ("CDR-PAVER", "Concrete Paving Bricks", "piece", "Lebanon", 150, 3, "0.95", "5000", "const/const12.png", "const"),
    ],
    "south": [
        ("TYR-FISH-ICE", "Chilled Whole Fish on Ice", "kg", "Lebanon", 10, 1, "14.50", "80", "food/food8.png", "meat"),
        ("TYR-CHICKEN", "Fresh Whole Chicken", "piece", "Lebanon", 8, 1, "9.80", "70", "food/food9.png", "meat"),
        ("TYR-BEEF-STK", "Fresh Beef Steaks", "kg", "Lebanon", 6, 1, "18.40", "45", "food/food10.png", "meat"),
    ],
    "pack": [
        ("SPK-TAPE", "Packing Tape Dispenser", "piece", "Lebanon", 24, 4, "4.80", "400", "office/office3.png", "packaging"),
        ("SPK-STORE", "Airtight Food Storage Set", "box", "Lebanon", 10, 5, "16.50", "180", "home/home2.png", "packaging"),
    ],
    "zahle": [
        ("ZFI-HONEY", "Bekaa Wildflower Honey", "carton", "Lebanon", 8, 3, "21.00", "90", "food/foodd2.png", "food"),
    ],
    "tripoli": [
        ("SAF-MOP", "Plastic Spin Mop and Bucket", "piece", "Lebanon", 12, 5, "14.80", "160", "home/home7.png", "cleaning"),
    ],
    "keserwan": [
        ("PHR-COTTON", "Cotton Pads and Swabs", "box", "Lebanon", 16, 5, "6.40", "280", "care/care4.png", "pharma"),
        ("PHR-SUN", "Sunscreen Lotion Pair", "box", "EU", 12, 6, "11.20", "190", "care/care6.png", "pharma"),
    ],
    "saida": [
        ("MSP-TEA-HERB", "Mountain Herbal Tea", "carton", "Lebanon", 12, 2, "9.60", "220", "food/food7.png", "beverages"),
    ],
    "baalbek": [
        ("SRC-DINNER", "Ceramic Dinnerware Set", "box", "Lebanon", 8, 8, "28.00", "90", "home/home5.png", "home"),
        ("SRC-GLASS", "Glass Pitcher and Tumbler Set", "box", "Lebanon", 10, 6, "16.80", "110", "home/homw6.png", "home"),
        ("SRC-CLOCK", "Wall Clock", "piece", "Lebanon", 8, 7, "18.40", "70", "home/home12.png", "home"),
    ],
    "achrafieh": [
        ("LTX-CUSHION", "Cushion and Throw Set", "box", "Turkey", 8, 9, "24.00", "80", "home/home9.png", "textiles"),
        ("LTX-CURTAIN", "Blackout Curtain Pair", "piece", "Turkey", 6, 10, "32.00", "60", "home/home10.png", "textiles"),
        ("LTX-RUG", "Woven Area Rug", "piece", "Turkey", 4, 12, "78.00", "40", "home/home11.png", "textiles"),
    ],
    "jbeil": [
        ("NHR-CABLE", "Electrical Cable and Socket Kit", "box", "Turkey", 8, 7, "36.00", "90", "const/const8.png", "elect"),
        ("NHR-LIGHT", "LED Work Lights and Floodlight", "box", "China", 6, 8, "42.00", "70", "const/const9.png", "elect"),
        ("NHR-BULB", "LED Bulb E27", "piece", "China", 24, 5, "3.80", "400", "elect/elect13.png", "elect"),
    ],
}


async def main() -> None:
    _load_dotenv()
    # Give Atlas more room for drop + bulk seed.
    os.environ["MONGODB_SEED_MODE"] = "1"

    from app.core.config import get_settings, reset_settings_cache
    from app.db.demo.kyc import write_cover, write_logo, write_verification_pack
    from app.core.security import hash_password
    from app.db.mongodb import mongo_manager
    from app.db.seed import seed_trading_roles
    from app.modules.catalog.constants import (
        InventoryReferenceType,
        InventoryTransactionType,
        ProductStatus,
    )
    from app.modules.identity.constants import (
        SYSTEM_ROLE_BUSINESS_ADMIN,
        SYSTEM_ROLE_PLATFORM_ADMIN,
        BusinessAccountStatus,
        BusinessAccountType,
        InvitationStatus,
        MembershipStatus,
        SupplierVerificationStatus,
        UserStatus,
    )
    from app.modules.identity.permissions import TRADING_SYSTEM_ROLES
    from app.shared.types.money import to_decimal128
    from app.shared.utils.datetime import utc_now
    from datetime import timedelta
    from motor.motor_asyncio import AsyncIOMotorClient

    reset_settings_cache()
    settings = get_settings()
    db_name = settings.mongodb_database
    if "test" in db_name.lower():
        raise SystemExit(f"Refusing to wipe test database: {db_name}")

    print(f"Connecting… ({db_name})")
    client: AsyncIOMotorClient = AsyncIOMotorClient(
        settings.mongodb_uri,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        socketTimeoutMS=120000,
        maxPoolSize=20,
        retryWrites=True,
        tz_aware=True,
    )
    await client.admin.command("ping")
    print(f"Dropping database `{db_name}`…")
    await client.drop_database(db_name)
    client.close()

    import shutil

    from app.modules.identity.storage import VERIFICATION_DIR

    if VERIFICATION_DIR.exists():
        shutil.rmtree(VERIFICATION_DIR, ignore_errors=True)

    print("Reconnecting (indexes + platform seed)…")
    reset_settings_cache()
    # Temporarily widen Motor timeouts used by mongo_manager
    original_connect = mongo_manager.connect

    async def connect_slow(settings_arg=None):
        from app.core.config import get_settings as gs
        from app.db.indexes import ensure_indexes
        from app.db.seed import seed_startup
        from app.core.logging import get_logger

        log = get_logger(__name__)
        cfg = settings_arg or gs()
        loop = asyncio.get_running_loop()
        if mongo_manager._client is not None:
            await mongo_manager.disconnect()
        mongo_manager._client = AsyncIOMotorClient(
            cfg.mongodb_uri,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=120000,
            maxPoolSize=30,
            minPoolSize=2,
            retryWrites=True,
            tz_aware=True,
        )
        mongo_manager._database = mongo_manager._client[cfg.mongodb_database]
        mongo_manager._loop = loop
        await mongo_manager.client.admin.command("ping")
        log.info("mongodb_connected", database=cfg.mongodb_database)
        await ensure_indexes(mongo_manager.database)
        mongo_manager._indexes_ready = True
        log.info("mongodb_indexes_ensured")
        await seed_startup()
        log.info("mongodb_seed_ensured")

    mongo_manager.connect = connect_slow  # type: ignore[method-assign]
    await mongo_manager.connect()
    db = mongo_manager.database
    now = utc_now()
    password_hash = hash_password(DEMO_PASSWORD)

    platform = await db["business_accounts"].find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise SystemExit("Platform business missing after seed_startup")
    platform_admin_role = await db["roles"].find_one(
        {
            "business_account_id": platform["_id"],
            "name": SYSTEM_ROLE_PLATFORM_ADMIN,
        }
    )
    if platform_admin_role is None:
        raise SystemExit("Platform Admin role missing")

    async def create_user(
        email: str,
        first: str,
        last: str,
        *,
        phone: str | None = None,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        existing = await db["users"].find_one({"email": email.lower()})
        if existing is not None:
            updates: dict[str, Any] = {"updated_at": now}
            if phone:
                updates["phone"] = phone
            if avatar_url:
                updates["avatar_url"] = avatar_url
            updates["first_name"] = first
            updates["last_name"] = last
            updates["status"] = UserStatus.ACTIVE
            updates["email_verified_at"] = existing.get("email_verified_at") or now
            updates["is_demo_seed"] = True
            updates["data_source"] = "synthetic_demo"
            await db["users"].update_one({"_id": existing["_id"]}, {"$set": updates})
            existing.update(updates)
            return existing
        user = {
            "_id": ObjectId(),
            "email": email.lower(),
            "personal_email": email.lower(),
            "password_hash": password_hash,
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "avatar_url": avatar_url,
            "status": UserStatus.ACTIVE,
            "email_verified_at": now,
            "is_demo_seed": True,
            "data_source": "synthetic_demo",
            "created_at": now,
            "updated_at": now,
        }
        await db["users"].insert_one(user)
        return user

    async def create_business(
        *,
        name: str,
        account_type: BusinessAccountType,
        owner: dict[str, Any],
        domain: str,
        legal_name: str,
        tax_number: str,
        phone: str,
        address: dict[str, str],
        logo_url: str | None = None,
        cover_url: str | None = None,
        registration_number: str | None = None,
        verification: str = "unverified",
        rejection_reason: str | None = None,
        service_areas: list[str] | None = None,
        description: str | None = None,
        industry_categories: list[str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
        verification = verification.lower()
        if account_type == BusinessAccountType.BUYER:
            status = BusinessAccountStatus.VERIFIED
        elif verification == "verified":
            status = BusinessAccountStatus.VERIFIED
        elif verification == "rejected":
            status = BusinessAccountStatus.REJECTED
        elif verification == "revoked":
            status = BusinessAccountStatus.SUSPENDED
        else:
            status = BusinessAccountStatus.PENDING
        if account_type == BusinessAccountType.SUPPLIER:
            if verification == "verified":
                profile_status = SupplierVerificationStatus.VERIFIED
            elif verification == "pending":
                profile_status = SupplierVerificationStatus.PENDING
            elif verification == "rejected":
                profile_status = SupplierVerificationStatus.REJECTED
            elif verification == "revoked":
                profile_status = SupplierVerificationStatus.REVOKED
            else:
                profile_status = SupplierVerificationStatus.UNVERIFIED
        else:
            profile_status = SupplierVerificationStatus.UNVERIFIED
        business = {
            "_id": ObjectId(),
            "name": name,
            "type": account_type,
            "status": status,
            "legal_name": legal_name,
            "tax_number": tax_number,
            "registration_number": registration_number or f"CR-{tax_number[-5:]}",
            "contact_email": owner["email"],
            "contact_phone": phone,
            "email_domain": domain.lower(),
            "logo_url": logo_url,
            "cover_url": cover_url,
            "address": address,
            "description": description,
            "industry_categories": industry_categories or [],
            "is_demo_seed": True,
            "data_source": "synthetic_demo",
            "created_at": now,
            "updated_at": now,
        }
        await db["business_accounts"].insert_one(business)
        if logo_url and not owner.get("avatar_url"):
            await db["users"].update_one(
                {"_id": owner["_id"]},
                {"$set": {"avatar_url": logo_url, "updated_at": now}},
            )
            owner["avatar_url"] = logo_url
        roles = await seed_trading_roles(business["_id"], fresh=True)
        admin_role = roles[SYSTEM_ROLE_BUSINESS_ADMIN]
        await db["business_memberships"].insert_one(
            {
                "_id": ObjectId(),
                "user_id": owner["_id"],
                "business_account_id": business["_id"],
                "role_id": admin_role["_id"],
                "status": MembershipStatus.ACTIVE,
                "joined_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        wants_docs = account_type == BusinessAccountType.SUPPLIER and verification in {
            "verified",
            "pending",
            "rejected",
            "revoked",
        }
        documents = (
            write_verification_pack(
                business_id=str(business["_id"]),
                company_name=name,
                legal_name=legal_name,
                tax_number=tax_number,
                registration_number=str(business["registration_number"]),
                address=address,
                verified=verification in {"verified", "revoked"},
            )
            if wants_docs
            else []
        )
        profile = {
            "_id": ObjectId(),
            "business_account_id": business["_id"],
            "verification_status": profile_status,
            "documents": documents,
            "service_areas": service_areas or [],
            "rating_summary": {
                "average_rating": 0.0,
                "review_count": 0,
                "last_reviewed_at": None,
            },
            "verified_at": now if verification in {"verified", "revoked"} else None,
            "verified_by": platform_admin_role["_id"]
            if verification in {"verified", "revoked"}
            else None,
            "rejection_reason": rejection_reason,
            "is_demo_seed": True,
            "data_source": "synthetic_demo",
            "created_at": now,
            "updated_at": now,
        }
        await db["supplier_profiles"].insert_one(profile)
        return business, profile, roles

    async def staff_team(
        business: dict[str, Any],
        roles: dict[str, dict[str, Any]],
        domain: str,
        logo_url: str | None,
        members: list[tuple[str, str, str, str, str, int]],
    ) -> None:
        """members: role, first, last, local_part, phone, joined_days_ago"""
        for role_name, first, last, local, phone, days in members:
            user = await create_user(
                f"{local}@{domain}",
                first,
                last,
                phone=phone,
                avatar_url=logo_url,
            )
            await add_member(user, business, roles, role_name, joined_days_ago=days)

    async def add_member(
        user: dict[str, Any],
        business: dict[str, Any],
        roles: dict[str, dict[str, Any]],
        role_name: str,
        *,
        status: str = MembershipStatus.ACTIVE,
        joined_days_ago: int = 0,
    ) -> dict[str, Any]:
        role = roles[role_name]
        joined = now - timedelta(days=joined_days_ago)
        doc = {
            "_id": ObjectId(),
            "user_id": user["_id"],
            "business_account_id": business["_id"],
            "role_id": role["_id"],
            "status": status,
            "joined_at": joined if status != MembershipStatus.INVITED else None,
            "created_at": joined,
            "updated_at": now,
        }
        await db["business_memberships"].insert_one(doc)
        return doc

    async def invite(
        *,
        business: dict[str, Any],
        roles: dict[str, dict[str, Any]],
        role_name: str,
        invited_by: dict[str, Any],
        invited_email: str,
        status: str = InvitationStatus.PENDING,
        days_ago: int = 0,
        expires_in_days: int = 7,
        delivery_email: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        token = generate_refresh_token()
        created = now - timedelta(days=days_ago)
        doc = {
            "_id": ObjectId(),
            "business_account_id": business["_id"],
            "invited_email": invited_email.lower(),
            "delivery_email": (delivery_email or invited_email).lower(),
            "role_id": roles[role_name]["_id"],
            "invited_by_user_id": invited_by["_id"],
            "token_hash": hash_token(token),
            "status": status,
            "expires_at": created + timedelta(days=expires_in_days),
            "accepted_at": created + timedelta(hours=6)
            if status == InvitationStatus.ACCEPTED
            else None,
            "created_at": created,
        }
        await db["invitations"].insert_one(doc)
        return doc, token

    from app.core.security import generate_refresh_token, hash_token

    # ── Platform staff ─────────────────────────────────────────────────────
    await db["business_accounts"].update_one(
        {"_id": platform["_id"]},
        {
            "$set": {
                "logo_url": LOGOS["tradebay"],
                "is_demo_seed": True,
                "data_source": "synthetic_demo",
                "updated_at": now,
            }
        },
    )
    platform["logo_url"] = LOGOS["tradebay"]

    platform_admin = await create_user(
        "admin@tradebay.com",
        "Platform",
        "Admin",
        phone="+96171100001",
        avatar_url=LOGOS["tradebay"],
    )
    if not await db["business_memberships"].find_one(
        {"user_id": platform_admin["_id"], "business_account_id": platform["_id"]}
    ):
        await db["business_memberships"].insert_one(
            {
                "_id": ObjectId(),
                "user_id": platform_admin["_id"],
                "business_account_id": platform["_id"],
                "role_id": platform_admin_role["_id"],
                "status": MembershipStatus.ACTIVE,
                "joined_at": now - timedelta(days=120),
                "created_at": now - timedelta(days=120),
                "updated_at": now,
            }
        )
    platform_ops_role = await db["roles"].find_one(
        {
            "business_account_id": platform["_id"],
            "name": "Platform Operator",
        }
    )
    if platform_ops_role:
        ops = await create_user(
            "ops@tradebay.com",
            "Rania",
            "Awad",
            phone="+96171100002",
            avatar_url=LOGOS["tradebay"],
        )
        await db["business_memberships"].insert_one(
            {
                "_id": ObjectId(),
                "user_id": ops["_id"],
                "business_account_id": platform["_id"],
                "role_id": platform_ops_role["_id"],
                "status": MembershipStatus.ACTIVE,
                "joined_at": now - timedelta(days=60),
                "created_at": now - timedelta(days=60),
                "updated_at": now,
            }
        )

    # ── Company owners ─────────────────────────────────────────────────────
    karim = await create_user(
        "karim@cedrusfoods.com",
        "Karim",
        "Haddad",
        phone="+96171110001",
        avatar_url=LOGOS["levant"],
    )
    rami = await create_user(
        "rami@lebtechsolutions.com",
        "Rami",
        "Sfeir",
        phone="+96171120001",
        avatar_url=LOGOS["bekaa"],
    )
    maya = await create_user(
        "maya@beirutbuild.com",
        "Maya",
        "Nasr",
        phone="+96171130001",
        avatar_url=LOGOS["cedar"],
    )
    sara = await create_user(
        "sara@beirutmart.com",
        "Sara",
        "Mansour",
        phone="+96171140001",
        avatar_url=LOGOS["beirut"],
    )
    omar = await create_user(
        "omar@harborhospitality.lb",
        "Omar",
        "Fadel",
        phone="+96171150001",
        avatar_url=LOGOS["harbor"],
    )

    # ── Businesses ─────────────────────────────────────────────────────────
    levant, levant_profile, levant_roles = await create_business(
        name="Cedrus Foods",
        account_type=BusinessAccountType.SUPPLIER,
        owner=karim,
        domain="cedrusfoods.com",
        legal_name="Cedrus Foods SAL",
        tax_number="LB-VAT-440221",
        registration_number="CR-BEY-44022",
        phone="+96114401001",
        address=_addr(
            "Industrial Zone, Block C, Street 12",
            "Mkalles",
            "Mount Lebanon",
            district="Metn",
            postal_code="1200",
        ),
        logo_url=LOGOS["levant"],
        cover_url=write_cover(slug="cedrus-foods", palette_index=0),
        verification="verified",
        service_areas=["Beirut", "Mount Lebanon", "Bekaa"],
        description="Cedrus Foods supplies Lebanese oils, pantry staples, and specialty foods. Taste Lebanon always.",
        industry_categories=["Food & Beverage"],
    )
    bekaa, bekaa_profile, bekaa_roles = await create_business(
        name="LebTech Solutions",
        account_type=BusinessAccountType.SUPPLIER,
        owner=rami,
        domain="lebtechsolutions.com",
        legal_name="LebTech Solutions SAL",
        tax_number="LB-VAT-551033",
        registration_number="CR-ZAH-55103",
        phone="+96114402001",
        address=_addr(
            "Main Road, Tech Park Building 4",
            "Zahle",
            "Bekaa",
            district="Zahle",
            postal_code="1800",
        ),
        logo_url=LOGOS["bekaa"],
        cover_url=write_cover(slug="lebtech-solutions", palette_index=3),
        verification="verified",
        service_areas=["Bekaa", "Beirut", "North"],
        description="LebTech Solutions provides technology and digital services for a stronger Lebanon.",
        industry_categories=["IT & Digital Services"],
    )
    cedar, cedar_profile, cedar_roles = await create_business(
        name="Beirut Build",
        account_type=BusinessAccountType.SUPPLIER,
        owner=maya,
        domain="beirutbuild.com",
        legal_name="Beirut Build SAL",
        tax_number="LB-VAT-662144",
        registration_number="CR-BEY-66214",
        phone="+96114403001",
        address=_addr(
            "Port Free Zone Gate 4, Quai 2",
            "Beirut",
            "Beirut",
            district="Medawar",
            postal_code="1100",
        ),
        logo_url=LOGOS["cedar"],
        cover_url=write_cover(slug="beirut-build", palette_index=2),
        verification="verified",
        service_areas=["Beirut", "Mount Lebanon", "South"],
        description="Beirut Build supplies construction materials and site hardware. Building a stronger tomorrow.",
        industry_categories=["Construction & Materials"],
    )
    beirut_mart, _, beirut_roles = await create_business(
        name="Beirut Mart Retail",
        account_type=BusinessAccountType.BUYER,
        owner=sara,
        domain="beirutmart.com",
        legal_name="Beirut Mart Retail SAL",
        tax_number="LB-VAT-773255",
        registration_number="CR-BEY-77325",
        phone="+96114404001",
        address=_addr(
            "Hamra Street 42, Picard Building",
            "Beirut",
            "Beirut",
            district="Ras Beirut",
            postal_code="1103",
        ),
        logo_url=LOGOS["beirut"],
        cover_url=write_cover(slug="beirut-mart", palette_index=1),
    )
    harbor, _, harbor_roles = await create_business(
        name="Harbor Hospitality Group",
        account_type=BusinessAccountType.BUYER,
        owner=omar,
        domain="harborhospitality.lb",
        legal_name="Harbor Hospitality Group SAL",
        tax_number="LB-VAT-884366",
        registration_number="CR-BEY-88436",
        phone="+96114405001",
        address=_addr(
            "Raouche Corniche, Harbor Tower 8",
            "Beirut",
            "Beirut",
            district="Raouche",
            postal_code="2038",
        ),
        logo_url=LOGOS["harbor"],
        cover_url=write_cover(slug="harbor-hospitality", palette_index=11),
    )

    logo_south = LOGOS["south"]
    logo_pack = LOGOS["pack"]
    logo_zahle = LOGOS["zahle"]
    logo_tripoli = LOGOS["tripoli"]
    logo_keserwan = LOGOS["keserwan"]
    logo_cafe = write_logo(slug="cedar-cafe", initials="CC", palette_index=0, mark="cedar")
    logo_grocery = write_logo(slug="nabatieh-grocery", initials="NG", palette_index=14, mark="circle")
    logo_hotel = write_logo(slug="jounieh-hotel", initials="JH", palette_index=11, mark="diamond")
    logo_pharma = write_logo(slug="tripoli-pharma", initials="PH", palette_index=3, mark="bar")
    logo_catering = write_logo(slug="tyre-catering", initials="TC", palette_index=2, mark="circle")
    logo_byblos = write_logo(slug="byblos-boutique", initials="BB", palette_index=4, mark="diamond")
    logo_metn = write_logo(slug="metn-office-hub", initials="MH", palette_index=8, mark="bar")
    logo_saida = LOGOS["saida"]
    logo_baalbek = LOGOS["baalbek"]
    logo_achrafieh = LOGOS["achrafieh"]
    logo_jbeil = LOGOS["jbeil"]

    hassan = await create_user(
        "hassan@tyrefresh.com", "Hassan", "Chehab",
        phone="+96176110001", avatar_url=logo_south,
    )
    samer = await create_user(
        "samer@beirutpack.com", "Samer", "Azar",
        phone="+96176120001", avatar_url=logo_pack,
    )
    youssef = await create_user(
        "youssef@bekaaharvest.com", "Youssef", "Maalouf",
        phone="+96176130001", avatar_url=logo_zahle,
    )
    rana = await create_user(
        "rana@safawiplastics.com", "Rana", "Trabulsi",
        phone="+96176140001", avatar_url=logo_tripoli,
    )
    karine = await create_user(
        "karine@cedarspharma.com", "Karine", "Gemayel",
        phone="+96176150001", avatar_url=logo_keserwan,
    )
    lara = await create_user(
        "lara@cedarcafe.com", "Lara", "Younes",
        phone="+96176210001", avatar_url=logo_cafe,
    )
    nabil = await create_user(
        "nabil@nabatiehgrocery.com", "Nabil", "Fahes",
        phone="+96176220001", avatar_url=logo_grocery,
    )
    rita = await create_user(
        "rita@jouniehhotelhouse.com", "Rita", "Kassis",
        phone="+96176230001", avatar_url=logo_hotel,
    )
    dany = await create_user(
        "dany@tripolipharma.com", "Dany", "Mikhael",
        phone="+96176240001", avatar_url=logo_pharma,
    )
    fadia = await create_user(
        "fadia@tyrecatering.com", "Fadia", "Saba",
        phone="+96176250001", avatar_url=logo_catering,
    )
    joud = await create_user(
        "joud@byblosboutique.com", "Joud", "Frem",
        phone="+96176260001", avatar_url=logo_byblos,
    )
    mira = await create_user(
        "mira@metnofficehub.com", "Mira", "Tannous",
        phone="+96176270001", avatar_url=logo_metn,
    )
    ziad_saida = await create_user(
        "ziad@mountainspices.com", "Ziad", "Bizri",
        phone="+96176310001", avatar_url=logo_saida,
    )
    ghassan = await create_user(
        "ghassan@sourceramics.com", "Ghassan", "Jaafar",
        phone="+96176320001", avatar_url=logo_baalbek,
    )
    nadine = await create_user(
        "nadine@levanttextile.com", "Nadine", "Sfeir",
        phone="+96176330001", avatar_url=logo_achrafieh,
    )
    bassam = await create_user(
        "bassam@nahrenergy.com", "Bassam", "Awad",
        phone="+96176340001", avatar_url=logo_jbeil,
    )

    south, south_profile, south_roles = await create_business(
        name="Tyre Fresh",
        account_type=BusinessAccountType.SUPPLIER,
        owner=hassan,
        domain="tyrefresh.com",
        legal_name="Tyre Fresh SARL",
        tax_number="LB-VAT-110187",
        registration_number="CR-TYR-11018",
        phone="+96177200001",
        address=_addr(
            "Al-Jalil Street, Cold Store 7",
            "Tyre",
            "South",
            district="Tyre",
            postal_code="1600",
        ),
        logo_url=logo_south,
        cover_url=write_cover(slug="tyre-fresh", palette_index=6),
        verification="verified",
        service_areas=["South", "Nabatieh", "Beirut"],
        description="Tyre Fresh supplies chilled seafood and fresh protein from the Lebanese coast.",
        industry_categories=["Seafood & Fresh Protein"],
    )
    pack, pack_profile, pack_roles = await create_business(
        name="Beirut Pack",
        account_type=BusinessAccountType.SUPPLIER,
        owner=samer,
        domain="beirutpack.com",
        legal_name="Beirut Pack SARL",
        tax_number="LB-VAT-110288",
        registration_number="CR-BAA-11028",
        phone="+96177200002",
        address=_addr(
            "Industrial Zone, Haret Hreik Road 18",
            "Baabda",
            "Mount Lebanon",
            district="Baabda",
            postal_code="1003",
        ),
        logo_url=logo_pack,
        cover_url=write_cover(slug="beirut-pack", palette_index=7),
        verification="verified",
        service_areas=["Beirut", "Mount Lebanon", "Keserwan"],
        description="Beirut Pack makes smart packaging for a greener future — cups, cartons, and labels.",
        industry_categories=["Packaging Solutions"],
    )
    zahle_farm, zahle_profile, zahle_roles = await create_business(
        name="Bekaa Harvest",
        account_type=BusinessAccountType.SUPPLIER,
        owner=youssef,
        domain="bekaaharvest.com",
        legal_name="Bekaa Harvest SARL",
        tax_number="LB-VAT-110389",
        registration_number="CR-ZAH-11038",
        phone="+96177200003",
        address=_addr(
            "Midan Street, Agricultural Depot 2",
            "Zahle",
            "Bekaa",
            district="Maallaqa",
            postal_code="1800",
        ),
        logo_url=logo_zahle,
        cover_url=write_cover(slug="bekaa-harvest", palette_index=9),
        verification="verified",
        service_areas=["Bekaa", "Baalbek"],
        description="Bekaa Harvest is rooted in Lebanon’s land — produce, seeds, and farm inputs from the Bekaa.",
        industry_categories=["Agriculture & Produce"],
    )
    tripoli_paper, tripoli_profile, tripoli_roles = await create_business(
        name="Safawi Plastics",
        account_type=BusinessAccountType.SUPPLIER,
        owner=rana,
        domain="safawiplastics.com",
        legal_name="Safawi Plastics SARL",
        tax_number="LB-VAT-110490",
        registration_number="CR-TRI-11049",
        phone="+96177200004",
        address=_addr(
            "Azmi Street, Tall Quarter, Floor 3",
            "Tripoli",
            "North",
            district="Tall",
            postal_code="1300",
        ),
        logo_url=logo_tripoli,
        cover_url=write_cover(slug="safawi-plastics", palette_index=15),
        verification="verified",
        service_areas=["North", "Beirut"],
        description="Safawi Plastics manufactures sustainable plastic solutions for a cleaner Lebanon.",
        industry_categories=["Plastic Manufacturing"],
    )
    keserwan, keserwan_profile, keserwan_roles = await create_business(
        name="Cedars Pharma",
        account_type=BusinessAccountType.SUPPLIER,
        owner=karine,
        domain="cedarspharma.com",
        legal_name="Cedars Pharma SAL",
        tax_number="LB-VAT-110591",
        registration_number="CR-JOU-11059",
        phone="+96177200005",
        address=_addr(
            "Maameltein Coastal Road, Hangar 5",
            "Jounieh",
            "Mount Lebanon",
            district="Keserwan",
            postal_code="1400",
        ),
        logo_url=logo_keserwan,
        cover_url=write_cover(slug="cedars-pharma", palette_index=5),
        verification="verified",
        service_areas=["Keserwan", "Metn", "Beirut"],
        description="Cedars Pharma supplies people-first healthcare products for a brighter Lebanon.",
        industry_categories=["Pharmaceuticals"],
    )
    cafe, _, cafe_roles = await create_business(
        name="Cedar Café Collective",
        account_type=BusinessAccountType.BUYER,
        owner=lara,
        domain="cedarcafe.com",
        legal_name="Cedar Café Collective SARL",
        tax_number="LB-VAT-220187",
        registration_number="CR-ZAH-22018",
        phone="+96178110001",
        address=_addr(
            "Boulevard Street 19, Midan",
            "Zahle",
            "Bekaa",
            district="Zahle",
            postal_code="1801",
        ),
        logo_url=logo_cafe,
        cover_url=write_cover(slug="cedar-cafe", palette_index=0),
    )
    grocery, _, grocery_roles = await create_business(
        name="Nabatieh Grocery Co-op",
        account_type=BusinessAccountType.BUYER,
        owner=nabil,
        domain="nabatiehgrocery.com",
        legal_name="Nabatieh Grocery Co-op SARL",
        tax_number="LB-VAT-220288",
        registration_number="CR-NAB-22028",
        phone="+96178110002",
        address=_addr(
            "Main Square, Co-op Building",
            "Nabatieh",
            "Nabatieh",
            district="Nabatieh",
            postal_code="1700",
        ),
        logo_url=logo_grocery,
        cover_url=write_cover(slug="nabatieh-grocery", palette_index=14),
    )
    hotel, _, hotel_roles = await create_business(
        name="Jounieh Hotel House",
        account_type=BusinessAccountType.BUYER,
        owner=rita,
        domain="jouniehhotelhouse.com",
        legal_name="Jounieh Hotel House SARL",
        tax_number="LB-VAT-220389",
        registration_number="CR-JOU-22038",
        phone="+96178110003",
        address=_addr(
            "Maameltein Bay, Hotel House 3",
            "Jounieh",
            "Mount Lebanon",
            district="Keserwan",
            postal_code="1401",
        ),
        logo_url=logo_hotel,
        cover_url=write_cover(slug="jounieh-hotel", palette_index=11),
    )
    pharmacy, _, pharmacy_roles = await create_business(
        name="Tripoli Pharma Retail",
        account_type=BusinessAccountType.BUYER,
        owner=dany,
        domain="tripolipharma.com",
        legal_name="Tripoli Pharma Retail SARL",
        tax_number="LB-VAT-220490",
        registration_number="CR-TRI-22049",
        phone="+96178110004",
        address=_addr(
            "Syriac Street, Mina, Shop 12",
            "Tripoli",
            "North",
            district="Mina",
            postal_code="1301",
        ),
        logo_url=logo_pharma,
        cover_url=write_cover(slug="tripoli-pharma", palette_index=3),
    )
    catering, _, catering_roles = await create_business(
        name="Tyre Catering Kitchen",
        account_type=BusinessAccountType.BUYER,
        owner=fadia,
        domain="tyrecatering.com",
        legal_name="Tyre Catering Kitchen SARL",
        tax_number="LB-VAT-220591",
        registration_number="CR-TYR-22059",
        phone="+96178110005",
        address=_addr(
            "Al-Jalil Street, Kitchen Compound",
            "Tyre",
            "South",
            district="Tyre",
            postal_code="1601",
        ),
        logo_url=logo_catering,
        cover_url=write_cover(slug="tyre-catering", palette_index=2),
    )
    byblos_shop, _, byblos_roles = await create_business(
        name="Byblos Boutique Retail",
        account_type=BusinessAccountType.BUYER,
        owner=joud,
        domain="byblosboutique.com",
        legal_name="Byblos Boutique Retail SARL",
        tax_number="LB-VAT-220692",
        registration_number="CR-JBE-22069",
        phone="+96178110006",
        address=_addr(
            "Old Souk, Pepe Abed Street 8",
            "Byblos",
            "Mount Lebanon",
            district="Jbeil",
            postal_code="1402",
        ),
        logo_url=logo_byblos,
        cover_url=write_cover(slug="byblos-boutique", palette_index=4),
    )
    metn_hub, _, metn_roles = await create_business(
        name="Metn Office Hub",
        account_type=BusinessAccountType.BUYER,
        owner=mira,
        domain="metnofficehub.com",
        legal_name="Metn Office Hub SARL",
        tax_number="LB-VAT-220793",
        registration_number="CR-JDE-22079",
        phone="+96178110007",
        address=_addr(
            "Dora Highway, City Mall Annex 2",
            "Jdeideh",
            "Mount Lebanon",
            district="Metn",
            postal_code="1201",
        ),
        logo_url=logo_metn,
        cover_url=write_cover(slug="metn-office-hub", palette_index=8),
    )
    saida, saida_profile, saida_roles = await create_business(
        name="Mountain Spices",
        account_type=BusinessAccountType.SUPPLIER,
        owner=ziad_saida,
        domain="mountainspices.com",
        legal_name="Mountain Spices SAL",
        tax_number="LB-VAT-330187",
        registration_number="CR-HAM-33018",
        phone="+96177210001",
        address=_addr(
            "Main Road, Spice House 3",
            "Hammana",
            "Mount Lebanon",
            district="Baabda",
            postal_code="1204",
        ),
        logo_url=logo_saida,
        cover_url=write_cover(slug="mountain-spices", palette_index=12),
        verification="pending",
        service_areas=["Mount Lebanon", "Beirut"],
        description="Mountain Spices offers authentic Lebanese flavors — za’atar, herbs, and pantry spices.",
        industry_categories=["Spices & Herbs"],
    )
    baalbek, baalbek_profile, baalbek_roles = await create_business(
        name="Sour Ceramics",
        account_type=BusinessAccountType.SUPPLIER,
        owner=ghassan,
        domain="sourceramics.com",
        legal_name="Sour Ceramics SARL",
        tax_number="LB-VAT-330288",
        registration_number="CR-TYR-33028",
        phone="+96177210002",
        address=_addr(
            "Old Port Road, Kiln Yard",
            "Tyre",
            "South",
            district="Tyre",
            postal_code="1603",
        ),
        logo_url=logo_baalbek,
        cover_url=write_cover(slug="sour-ceramics", palette_index=8),
        verification="rejected",
        rejection_reason="Commercial register extract is expired (issued 2019). Upload a current Ministry of Justice extract and matching tax certificate.",
        service_areas=["South", "Beirut"],
        description="Sour Ceramics brings tradition to modern living with tiles and home décor from Tyre.",
        industry_categories=["Ceramics & Home Decor"],
    )
    achrafieh, achrafieh_profile, achrafieh_roles = await create_business(
        name="Levant Textile",
        account_type=BusinessAccountType.SUPPLIER,
        owner=nadine,
        domain="levanttextile.com",
        legal_name="Levant Textile SAL",
        tax_number="LB-VAT-330389",
        registration_number="CR-BEY-33038",
        phone="+96177210003",
        address=_addr(
            "Sassine Square, Independence Street 14",
            "Beirut",
            "Beirut",
            district="Achrafieh",
            postal_code="1105",
        ),
        logo_url=logo_achrafieh,
        cover_url=write_cover(slug="levant-textile", palette_index=1),
        verification="unverified",
        service_areas=["Beirut", "Mount Lebanon"],
        description="Levant Textile weaves a brighter tomorrow — fabrics and garments for Lebanese trade.",
        industry_categories=["Textiles & Garments"],
    )
    jbeil, jbeil_profile, jbeil_roles = await create_business(
        name="Nahr Energy",
        account_type=BusinessAccountType.SUPPLIER,
        owner=bassam,
        domain="nahrenergy.com",
        legal_name="Nahr Energy SARL",
        tax_number="LB-VAT-330490",
        registration_number="CR-JBE-33049",
        phone="+96177210004",
        address=_addr(
            "Fouad Chehab Highway, Port Store 1",
            "Byblos",
            "Mount Lebanon",
            district="Jbeil",
            postal_code="1403",
        ),
        logo_url=logo_jbeil,
        cover_url=write_cover(slug="nahr-energy", palette_index=7),
        verification="revoked",
        rejection_reason="Selling rights revoked after the commercial register was not renewed. Resubmit a current extract to reopen review.",
        service_areas=["Keserwan", "Jbeil", "Beirut"],
        description="Nahr Energy delivers clean energy solutions for a brighter Lebanon.",
        industry_categories=["Energy & Renewables"],
    )

    demo_admin = await create_user(
        "admin@demo.tradebay.com",
        "Demo",
        "Admin",
        phone="+96171100002",
        avatar_url=LOGOS["tradebay"],
    )
    await db["business_memberships"].insert_one(
        {
            "_id": ObjectId(),
            "user_id": demo_admin["_id"],
            "business_account_id": platform["_id"],
            "role_id": platform_admin_role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    supplier1 = await create_user(
        "supplier1@demo.tradebay.com",
        "Demo",
        "Supplier",
        phone="+96176120006",
        avatar_url=logo_pack,
    )
    await add_member(supplier1, pack, pack_roles, "Sales Representative", joined_days_ago=2)
    buyer1 = await create_user(
        "buyer1@demo.tradebay.com",
        "Demo",
        "Buyer",
        phone="+96171150005",
        avatar_url=LOGOS["harbor"],
    )
    await add_member(buyer1, harbor, harbor_roles, "Viewer", joined_days_ago=2)

    # ── Full teams (every trading system role + extras) ────────────────────
    # Cedrus Foods
    nora = await create_user(
        "nora@cedrusfoods.com", "Nora", "Khoury", phone="+96171110002", avatar_url=LOGOS["levant"]
    )
    samir = await create_user(
        "samir@cedrusfoods.com", "Samir", "Farah", phone="+96171110003", avatar_url=LOGOS["levant"]
    )
    rima = await create_user(
        "rima@cedrusfoods.com", "Rima", "Saleh", phone="+96171110004", avatar_url=LOGOS["levant"]
    )
    elias = await create_user(
        "elias@cedrusfoods.com", "Elias", "Bitar", phone="+96171110005", avatar_url=LOGOS["levant"]
    )
    ziad_removed = await create_user(
        "ziad.ex@cedrusfoods.com",
        "Ziad",
        "ExMember",
        phone="+96171110006",
        avatar_url=LOGOS["levant"],
    )
    await add_member(nora, levant, levant_roles, "Sales Manager", joined_days_ago=90)
    await add_member(samir, levant, levant_roles, "Sales Representative", joined_days_ago=45)
    await add_member(rima, levant, levant_roles, "Finance", joined_days_ago=60)
    await add_member(elias, levant, levant_roles, "Viewer", joined_days_ago=20)
    await add_member(
        ziad_removed,
        levant,
        levant_roles,
        "Sales Representative",
        status=MembershipStatus.REMOVED,
        joined_days_ago=100,
    )

    # LebTech Solutions
    lina = await create_user(
        "lina@lebtechsolutions.com", "Lina", "Abi", phone="+96171120002", avatar_url=LOGOS["bekaa"]
    )
    tony = await create_user(
        "tony@lebtechsolutions.com", "Tony", "Karam", phone="+96171120003", avatar_url=LOGOS["bekaa"]
    )
    maja = await create_user(
        "maja@lebtechsolutions.com", "Maja", "Harb", phone="+96171120004", avatar_url=LOGOS["bekaa"]
    )
    gina = await create_user(
        "gina@lebtechsolutions.com", "Gina", "Bou", phone="+96171120005", avatar_url=LOGOS["bekaa"]
    )
    await add_member(lina, bekaa, bekaa_roles, "Sales Representative", joined_days_ago=40)
    await add_member(tony, bekaa, bekaa_roles, "Sales Manager", joined_days_ago=70)
    await add_member(maja, bekaa, bekaa_roles, "Finance", joined_days_ago=35)
    await add_member(
        gina,
        bekaa,
        bekaa_roles,
        "Viewer",
        status=MembershipStatus.SUSPENDED,
        joined_days_ago=50,
    )
    nour_bekaa = await create_user(
        "nour@lebtechsolutions.com", "Nour", "Salem", phone="+96171120006", avatar_url=LOGOS["bekaa"]
    )
    await add_member(nour_bekaa, bekaa, bekaa_roles, "Viewer", joined_days_ago=12)

    # Beirut Build
    fadi = await create_user(
        "fadi@beirutbuild.com", "Fadi", "Shami", phone="+96171130002", avatar_url=LOGOS["cedar"]
    )
    youmna = await create_user(
        "youmna@beirutbuild.com", "Youmna", "Abiad", phone="+96171130003", avatar_url=LOGOS["cedar"]
    )
    walid = await create_user(
        "walid@beirutbuild.com", "Walid", "Nassar", phone="+96171130004", avatar_url=LOGOS["cedar"]
    )
    rania_cedar = await create_user(
        "rania@beirutbuild.com", "Rania", "Khalil", phone="+96171130005", avatar_url=LOGOS["cedar"]
    )
    await add_member(fadi, cedar, cedar_roles, "Sales Manager", joined_days_ago=55)
    await add_member(youmna, cedar, cedar_roles, "Sales Representative", joined_days_ago=30)
    await add_member(walid, cedar, cedar_roles, "Finance", joined_days_ago=25)
    await add_member(rania_cedar, cedar, cedar_roles, "Viewer", joined_days_ago=14)

    # Beirut Mart
    nader = await create_user(
        "nader@beirutmart.com", "Nader", "Chami", phone="+96171140002", avatar_url=LOGOS["beirut"]
    )
    layal = await create_user(
        "layal@beirutmart.com", "Layal", "Haddad", phone="+96171140003", avatar_url=LOGOS["beirut"]
    )
    mark = await create_user(
        "mark@beirutmart.com", "Mark", "Harb", phone="+96171140004", avatar_url=LOGOS["beirut"]
    )
    rana_mart = await create_user(
        "rana@beirutmart.com", "Rana", "Moussawi", phone="+96171140005", avatar_url=LOGOS["beirut"]
    )
    await add_member(nader, beirut_mart, beirut_roles, "Sales Manager", joined_days_ago=80)
    await add_member(layal, beirut_mart, beirut_roles, "Finance", joined_days_ago=40)
    await add_member(mark, beirut_mart, beirut_roles, "Viewer", joined_days_ago=15)
    await add_member(rana_mart, beirut_mart, beirut_roles, "Sales Representative", joined_days_ago=22)

    # Harbor Hospitality
    hiba = await create_user(
        "procurement@harborhospitality.lb",
        "Hiba",
        "Rahal",
        phone="+96171150002",
        avatar_url=LOGOS["harbor"],
    )
    karen = await create_user(
        "karen@harborhospitality.lb",
        "Karen",
        "Saliba",
        phone="+96171150003",
        avatar_url=LOGOS["harbor"],
    )
    joe = await create_user(
        "joe@harborhospitality.lb",
        "Joe",
        "Khoury",
        phone="+96171150004",
        avatar_url=LOGOS["harbor"],
    )
    await add_member(hiba, harbor, harbor_roles, "Sales Manager", joined_days_ago=65)
    await add_member(karen, harbor, harbor_roles, "Finance", joined_days_ago=28)
    await add_member(joe, harbor, harbor_roles, "Sales Representative", joined_days_ago=12)

    await staff_team(south, south_roles, "tyrefresh.com", logo_south, [
        ("Sales Manager", "Ali", "Saab", "ali.saab", "+96176110002", 80),
        ("Sales Representative", "Hala", "Zein", "hala.zein", "+96176110003", 40),
        ("Finance", "Rami", "Itani", "rami.itani", "+96176110004", 55),
        ("Viewer", "Sana", "Hamdan", "sana.hamdan", "+96176110005", 18),
    ])
    await staff_team(pack, pack_roles, "beirutpack.com", logo_pack, [
        ("Sales Manager", "Jad", "Khoury", "jad.khoury", "+96176120002", 70),
        ("Sales Representative", "Maya", "Rahme", "maya.rahme", "+96176120003", 32),
        ("Finance", "Elie", "Haddad", "elie.haddad", "+96176120004", 48),
        ("Viewer", "Nour", "Abi", "nour.abi", "+96176120005", 12),
    ])
    await staff_team(zahle_farm, zahle_roles, "bekaaharvest.com", logo_zahle, [
        ("Sales Manager", "Charbel", "Karam", "charbel.karam", "+96176130002", 62),
        ("Sales Representative", "Rania", "Abboud", "rania.abboud", "+96176130003", 28),
        ("Finance", "Fouad", "Hajj", "fouad.hajj", "+96176130004", 44),
        ("Viewer", "Lama", "Saadeh", "lama.saadeh", "+96176130005", 9),
    ])
    await staff_team(tripoli_paper, tripoli_roles, "safawiplastics.com", logo_tripoli, [
        ("Sales Manager", "Mahmoud", "Dabbous", "mahmoud.dabbous", "+96176140002", 51),
        ("Sales Representative", "Sara", "Osman", "sara.osman", "+96176140003", 22),
        ("Finance", "Hadi", "Merhi", "hadi.merhi", "+96176140004", 37),
        ("Viewer", "Diala", "Kabbara", "diala.kabbara", "+96176140005", 14),
    ])
    await staff_team(keserwan, keserwan_roles, "cedarspharma.com", logo_keserwan, [
        ("Sales Manager", "Pierre", "Khalife", "pierre.khalife", "+96176150002", 58),
        ("Sales Representative", "Carla", "Zoghbi", "carla.zoghbi", "+96176150003", 21),
        ("Finance", "Georges", "Aoun", "georges.aoun", "+96176150004", 33),
        ("Viewer", "Tania", "Chedid", "tania.chedid", "+96176150005", 11),
    ])
    await staff_team(cafe, cafe_roles, "cedarcafe.com", logo_cafe, [
        ("Sales Manager", "Marwan", "Eid", "marwan.eid", "+96176210002", 46),
        ("Sales Representative", "Yara", "Nasrallah", "yara.nasrallah", "+96176210003", 19),
        ("Finance", "Bassel", "Hamieh", "bassel.hamieh", "+96176210004", 27),
        ("Viewer", "Reine", "Azzi", "reine.azzi", "+96176210005", 8),
    ])
    await staff_team(grocery, grocery_roles, "nabatiehgrocery.com", logo_grocery, [
        ("Sales Manager", "Hussein", "Safa", "hussein.safa", "+96176220002", 53),
        ("Sales Representative", "Fatima", "Zein", "fatima.zein", "+96176220003", 24),
        ("Finance", "Hassan", "Fawaz", "hassan.fawaz", "+96176220004", 31),
        ("Viewer", "Aya", "Hamoud", "aya.hamoud", "+96176220005", 10),
    ])
    await staff_team(hotel, hotel_roles, "jouniehhotelhouse.com", logo_hotel, [
        ("Sales Manager", "Michel", "Abi Raad", "michel.abiraad", "+96176230002", 41),
        ("Sales Representative", "Paula", "Khoury", "paula.khoury", "+96176230003", 16),
        ("Finance", "Antoine", "Sarkis", "antoine.sarkis", "+96176230004", 29),
        ("Viewer", "Celine", "Bou", "celine.bou", "+96176230005", 7),
    ])
    await staff_team(pharmacy, pharmacy_roles, "tripolipharma.com", logo_pharma, [
        ("Sales Manager", "Omar", "Kabbara", "omar.kabbara", "+96176240002", 38),
        ("Sales Representative", "Lina", "Masri", "lina.masri", "+96176240003", 17),
        ("Finance", "Samer", "Halabi", "samer.halabi", "+96176240004", 26),
        ("Viewer", "Dima", "Noureddine", "dima.noureddine", "+96176240005", 6),
    ])
    await staff_team(catering, catering_roles, "tyrecatering.com", logo_catering, [
        ("Sales Manager", "Rami", "Zaytoun", "rami.zaytoun", "+96176250002", 35),
        ("Sales Representative", "Hiba", "Jaber", "hiba.jaber", "+96176250003", 15),
        ("Finance", "Walid", "Chreim", "walid.chreim", "+96176250004", 23),
        ("Viewer", "Nadine", "Fakhoury", "nadine.fakhoury", "+96176250005", 5),
    ])
    await staff_team(byblos_shop, byblos_roles, "byblosboutique.com", logo_byblos, [
        ("Sales Manager", "Elie", "Torbey", "elie.torbey", "+96176260002", 34),
        ("Sales Representative", "Joelle", "Karam", "joelle.karam", "+96176260003", 13),
        ("Finance", "Rana", "Ghanem", "rana.ghanem", "+96176260004", 20),
        ("Viewer", "Tony", "Feghali", "tony.feghali", "+96176260005", 4),
    ])
    await staff_team(metn_hub, metn_roles, "metnofficehub.com", logo_metn, [
        ("Sales Manager", "Serge", "Daou", "serge.daou", "+96176270002", 36),
        ("Sales Representative", "Carine", "Haddad", "carine.haddad", "+96176270003", 14),
        ("Finance", "Patrick", "Abou", "patrick.abou", "+96176270004", 21),
        ("Viewer", "Mira", "Khoury", "mira.khoury", "+96176270005", 3),
    ])
    await staff_team(saida, saida_roles, "mountainspices.com", logo_saida, [
        ("Sales Manager", "Karim", "Saad", "karim.saad", "+96176310002", 30),
        ("Sales Representative", "Nour", "Itani", "nour.itani", "+96176310003", 11),
        ("Finance", "Fadi", "Bizri", "fadi.bizri", "+96176310004", 19),
        ("Viewer", "Lina", "Chehab", "lina.chehab", "+96176310005", 2),
    ])
    await staff_team(baalbek, baalbek_roles, "sourceramics.com", logo_baalbek, [
        ("Sales Manager", "Abbas", "Shamas", "abbas.shamas", "+96176320002", 42),
        ("Sales Representative", "Zeina", "Jaafar", "zeina.jaafar", "+96176320003", 18),
        ("Finance", "Hassan", "Hamade", "hassan.hamade", "+96176320004", 25),
        ("Viewer", "Rim", "Yaghi", "rim.yaghi", "+96176320005", 6),
    ])
    await staff_team(achrafieh, achrafieh_roles, "levanttextile.com", logo_achrafieh, [
        ("Sales Manager", "Nicolas", "Saba", "nicolas.saba", "+96176330002", 28),
        ("Sales Representative", "Maria", "Abdelnour", "maria.abdelnour", "+96176330003", 12),
        ("Finance", "Jean", "Sfeir", "jean.sfeir", "+96176330004", 16),
        ("Viewer", "Lea", "Khoury", "lea.khoury", "+96176330005", 4),
    ])
    await staff_team(jbeil, jbeil_roles, "nahrenergy.com", logo_jbeil, [
        ("Sales Manager", "Ralph", "Awad", "ralph.awad", "+96176340002", 33),
        ("Sales Representative", "Tia", "Karam", "tia.karam", "+96176340003", 10),
        ("Finance", "Charbel", "Fakhry", "charbel.fakhry", "+96176340004", 22),
        ("Viewer", "Joanna", "Salameh", "joanna.salameh", "+96176340005", 5),
    ])

    # ── Invitations (pending / accepted / revoked / expired) ───────────────
    _, invite_token = await invite(
        business=beirut_mart,
        roles=beirut_roles,
        role_name="Viewer",
        invited_by=sara,
        invited_email="jad@beirutmart.com",
        status=InvitationStatus.PENDING,
        days_ago=1,
    )
    await invite(
        business=levant,
        roles=levant_roles,
        role_name="Sales Representative",
        invited_by=karim,
        invited_email="newrep@cedrusfoods.com",
        delivery_email="newrep.personal@gmail.com",
        status=InvitationStatus.PENDING,
        days_ago=2,
    )
    await invite(
        business=bekaa,
        roles=bekaa_roles,
        role_name="Viewer",
        invited_by=rami,
        invited_email="intern@lebtechsolutions.com",
        status=InvitationStatus.REVOKED,
        days_ago=10,
    )
    await invite(
        business=cedar,
        roles=cedar_roles,
        role_name="Finance",
        invited_by=maya,
        invited_email="old.finance@beirutbuild.com",
        status=InvitationStatus.EXPIRED,
        days_ago=20,
        expires_in_days=7,
    )
    await invite(
        business=harbor,
        roles=harbor_roles,
        role_name="Viewer",
        invited_by=omar,
        invited_email="karen@harborhospitality.lb",
        status=InvitationStatus.ACCEPTED,
        days_ago=28,
    )

    # Custom role on Levant (beyond system roles)
    custom_role_id = ObjectId()
    await db["roles"].insert_one(
        {
            "_id": custom_role_id,
            "business_account_id": levant["_id"],
            "name": "Warehouse Lead",
            "description": "Custom role — stock counts and inbound receiving.",
            "is_system_role": False,
            "created_at": now - timedelta(days=14),
            "updated_at": now - timedelta(days=14),
        }
    )
    # Grant a few inventory/product read+manage style permissions if present
    perm_rows = await db["permissions"].find(
        {"resource": {"$in": ["inventory", "products", "categories"]}}
    ).to_list(length=50)
    if perm_rows:
        await db["role_permissions"].insert_many(
            [
                {
                    "_id": ObjectId(),
                    "role_id": custom_role_id,
                    "permission_id": p["_id"],
                    "created_at": now,
                }
                for p in perm_rows
                if p.get("action") in {"read", "manage"}
            ],
            ordered=False,
        )
    warehouse_lead = await create_user(
        "warehouse@cedrusfoods.com",
        "Tarek",
        "Nader",
        phone="+96171110007",
        avatar_url=LOGOS["levant"],
    )
    await db["business_memberships"].insert_one(
        {
            "_id": ObjectId(),
            "user_id": warehouse_lead["_id"],
            "business_account_id": levant["_id"],
            "role_id": custom_role_id,
            "status": MembershipStatus.ACTIVE,
            "joined_at": now - timedelta(days=10),
            "created_at": now - timedelta(days=10),
            "updated_at": now,
        }
    )

    member_count = await db["business_memberships"].count_documents({})
    invite_count = await db["invitations"].count_documents({})
    print(f"Seeded memberships: {member_count}, invitations: {invite_count}")


    # ── Categories ─────────────────────────────────────────────────────────
    cat_ids: dict[str, ObjectId] = {}
    for spec in CATEGORIES:
        parent_id = cat_ids[spec["parent"]] if spec.get("parent") else None
        doc = {
            "_id": ObjectId(),
            "name": spec["name"],
            "slug": spec["slug"],
            "description": spec["description"],
            "parent_category_id": parent_id,
            "is_active": True,
            "display_order": spec["order"],
            "image_url": spec["image"],
            "created_at": now,
            "updated_at": now,
        }
        await db["categories"].insert_one(doc)
        cat_ids[spec["key"]] = doc["_id"]

    supplier_map = {
        "levant": (levant, levant_profile),
        "bekaa": (bekaa, bekaa_profile),
        "cedar": (cedar, cedar_profile),
        "south": (south, south_profile),
        "pack": (pack, pack_profile),
        "zahle": (zahle_farm, zahle_profile),
        "tripoli": (tripoli_paper, tripoli_profile),
        "keserwan": (keserwan, keserwan_profile),
        "saida": (saida, saida_profile),
        "baalbek": (baalbek, baalbek_profile),
        "achrafieh": (achrafieh, achrafieh_profile),
        "jbeil": (jbeil, jbeil_profile),
    }
    creator_map = {
        "levant": karim["_id"],
        "bekaa": rami["_id"],
        "cedar": maya["_id"],
        "south": hassan["_id"],
        "pack": samer["_id"],
        "zahle": youssef["_id"],
        "tripoli": rana["_id"],
        "keserwan": karine["_id"],
        "saida": ziad_saida["_id"],
        "baalbek": ghassan["_id"],
        "achrafieh": nadine["_id"],
        "jbeil": bassam["_id"],
    }

    product_docs: list[dict[str, Any]] = []
    price_docs: list[dict[str, Any]] = []
    image_docs: list[dict[str, Any]] = []
    inventory_docs: list[dict[str, Any]] = []
    tx_docs: list[dict[str, Any]] = []

    for supplier_key, rows in PRODUCTS_BY_SUPPLIER.items():
        business, profile = supplier_map[supplier_key]
        creator = creator_map[supplier_key]
        for (
            sku,
            name,
            unit,
            origin,
            moq,
            lead,
            price,
            stock,
            image_rel,
            cat_key,
        ) in rows:
            product_id = ObjectId()
            inventory_id = ObjectId()
            stock_dec = Decimal(stock)
            price_dec = Decimal(price)
            resolved_unit = _resolve_unit(str(unit))
            sellable = (
                str(profile.get("verification_status"))
                == SupplierVerificationStatus.VERIFIED
            )
            product_docs.append(
                {
                    "_id": product_id,
                    "supplier_id": profile["_id"],
                    "business_account_id": business["_id"],
                    "category_id": cat_ids[cat_key],
                    "sku": sku,
                    "name": name,
                    "slug": _slugify(f"{sku}-{name}"),
                    "description": _product_description(
                        name,
                        business["name"],
                        origin,
                        int(moq),
                        resolved_unit,
                        int(lead),
                    ),
                    "unit": resolved_unit,
                    "origin": origin,
                    "moq": int(moq),
                    "lead_time_days": int(lead),
                    "status": ProductStatus.ACTIVE if sellable else ProductStatus.INACTIVE,
                    "is_featured": bool(sellable and sku in FEATURED_LANDING_SKUS),
                    "is_demo_seed": True,
                    "data_source": "synthetic_demo",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            price_docs.extend(
                [
                    {
                        "_id": ObjectId(),
                        "product_id": product_id,
                        "min_quantity": int(moq),
                        "max_quantity": int(moq) * 4 - 1,
                        "unit_price": to_decimal128(price_dec),
                        "currency": "USD",
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "_id": ObjectId(),
                        "product_id": product_id,
                        "min_quantity": int(moq) * 4,
                        "max_quantity": None,
                        "unit_price": to_decimal128(
                            (price_dec * Decimal("0.92")).quantize(Decimal("0.01"))
                        ),
                        "currency": "USD",
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                ]
            )
            image_docs.append(
                {
                    "_id": ObjectId(),
                    "product_id": product_id,
                    "url": _asset_url(str(image_rel)),
                    "alt_text": name,
                    "is_primary": True,
                    "display_order": 0,
                    "created_at": now,
                }
            )
            inventory_docs.append(
                {
                    "_id": inventory_id,
                    "product_id": product_id,
                    "available_quantity": to_decimal128(stock_dec),
                    "reserved_quantity": to_decimal128(Decimal("0")),
                    "updated_at": now,
                }
            )
            tx_docs.append(
                {
                    "_id": ObjectId(),
                    "inventory_id": inventory_id,
                    "product_id": product_id,
                    "transaction_type": InventoryTransactionType.INITIAL_STOCK,
                    "quantity": to_decimal128(stock_dec),
                    "reference_type": InventoryReferenceType.PRODUCT,
                    "reference_id": product_id,
                    "previous_available": to_decimal128(Decimal("0")),
                    "previous_reserved": to_decimal128(Decimal("0")),
                    "new_available": to_decimal128(stock_dec),
                    "new_reserved": to_decimal128(Decimal("0")),
                    "reason": "Demo opening stock",
                    "created_by": creator,
                    "created_at": now,
                }
            )

    if product_docs:
        await db["products"].insert_many(product_docs, ordered=False)
        await db["product_prices"].insert_many(price_docs, ordered=False)
        await db["product_images"].insert_many(image_docs, ordered=False)
        await db["inventories"].insert_many(inventory_docs, ordered=False)
        await db["inventory_transactions"].insert_many(tx_docs, ordered=False)

    product_count = len(product_docs)
    image_count = len(image_docs)

    # Sample audit events so Audit Trail is not empty
    await db["audit_logs"].insert_many(
        [
            {
                "_id": ObjectId(),
                "business_account_id": levant["_id"],
                "user_id": karim["_id"],
                "action": "BUSINESS_UPDATED",
                "resource_type": "business",
                "resource_id": levant["_id"],
                "metadata": {
                    "actor_name": "Karim Haddad",
                    "actor_email": karim["email"],
                    "business_name": levant["name"],
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=5),
            },
            {
                "_id": ObjectId(),
                "business_account_id": beirut_mart["_id"],
                "user_id": sara["_id"],
                "action": "USER_INVITED",
                "resource_type": "invitation",
                "resource_id": None,
                "metadata": {
                    "actor_name": "Sara Mansour",
                    "actor_email": sara["email"],
                    "invited_email": "jad@beirutmart.com",
                    "role_name": "Viewer",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=1),
            },
            {
                "_id": ObjectId(),
                "business_account_id": levant["_id"],
                "user_id": karim["_id"],
                "action": "INVITATION_ACCEPTED",
                "resource_type": "invitation",
                "resource_id": None,
                "metadata": {
                    "actor_name": "Nora Khoury",
                    "actor_email": nora["email"],
                    "invited_email": nora["email"],
                    "role_name": "Sales Manager",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=90),
            },
            {
                "_id": ObjectId(),
                "business_account_id": bekaa["_id"],
                "user_id": rami["_id"],
                "action": "MEMBER_ROLE_CHANGED",
                "resource_type": "membership",
                "resource_id": None,
                "metadata": {
                    "actor_name": "Rami Sfeir",
                    "member_name": "Lina Abi",
                    "member_email": lina["email"],
                    "old_role_name": "Viewer",
                    "new_role_name": "Sales Representative",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=20),
            },
            {
                "_id": ObjectId(),
                "business_account_id": levant["_id"],
                "user_id": karim["_id"],
                "action": "MEMBER_REMOVED",
                "resource_type": "membership",
                "resource_id": None,
                "metadata": {
                    "actor_name": "Karim Haddad",
                    "member_name": "Ziad ExMember",
                    "member_email": ziad_removed["email"],
                    "role_name": "Sales Representative",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=8),
            },
            {
                "_id": ObjectId(),
                "business_account_id": bekaa["_id"],
                "user_id": rami["_id"],
                "action": "MEMBERSHIP_SUSPENDED",
                "resource_type": "membership",
                "resource_id": None,
                "metadata": {
                    "actor_name": "Rami Sfeir",
                    "member_name": "Gina Bou",
                    "member_email": gina["email"],
                    "role_name": "Viewer",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=3),
            },
            {
                "_id": ObjectId(),
                "business_account_id": levant["_id"],
                "user_id": karim["_id"],
                "action": "ROLE_CREATED",
                "resource_type": "role",
                "resource_id": custom_role_id,
                "metadata": {
                    "actor_name": "Karim Haddad",
                    "role_name": "Warehouse Lead",
                },
                "ip_address": "127.0.0.1",
                "created_at": now - timedelta(days=14),
            },
        ]
    )

    user_count = await db["users"].count_documents({})
    biz_count = await db["business_accounts"].count_documents({})
    print("\n=== Catalog seed complete ===")
    print(f"Database: {db_name}")
    print(f"Users:       {user_count}")
    print(f"Businesses:  {biz_count}")
    print(f"Memberships: {member_count}")
    print(f"Invitations: {invite_count}")
    print(f"Categories:  {len(cat_ids)}")
    print(f"Products:    {product_count}")
    print(f"Images:      {image_count}")

    print("\nSeeding marketplace activity via domain services…")
    from app.db.demo.activity import seed_marketplace_activity

    try:
        activity = await seed_marketplace_activity(
            buyers={
                "beirut": (beirut_mart, sara),
                "harbor": (harbor, omar),
                "cafe": (cafe, lara),
                "grocery": (grocery, nabil),
                "hotel": (hotel, rita),
                "pharmacy": (pharmacy, dany),
                "catering": (catering, fadia),
            },
            suppliers={
                "levant": (levant, karim),
                "bekaa": (bekaa, rami),
                "cedar": (cedar, maya),
                "south": (south, hassan),
                "pack": (pack, samer),
                "zahle": (zahle_farm, youssef),
                "keserwan": (keserwan, karine),
                "saida": (saida, ziad_saida),
            },
        )
    except Exception:
        import traceback

        traceback.print_exc()
        raise

    print("\n=== Demo seed complete ===")
    print(f"Password for all users: {DEMO_PASSWORD}")
    print("\nLogins:")
    print("  Platform admin     admin@demo.tradebay.com")
    print("  Platform admin     admin@tradebay.com")
    print("  Platform operator  ops@tradebay.com")
    print("  Demo supplier      supplier1@demo.tradebay.com")
    print("  Demo buyer         buyer1@demo.tradebay.com")
    print("  Cedrus Foods       karim@cedrusfoods.com")
    print("  LebTech Solutions  rami@lebtechsolutions.com")
    print("  Beirut Build       maya@beirutbuild.com")
    print("  Beirut Pack        samer@beirutpack.com")
    print("  Beirut Mart admin  sara@beirutmart.com")
    print("  Harbor admin       omar@harborhospitality.lb")
    print("  Cafe buyer         lara@cedarcafe.com")
    print("  Grocery buyer      nabil@nabatiehgrocery.com")
    print(f"\nPending invite token (jad@beirutmart.com): {invite_token}")
    print("All companies are synthetic demo records (is_demo_seed=true).")
    print("Public source notes: backend/app/db/demo/SOURCES.md")
    print("Activity counts:", activity)
    print("Images served from frontend: /images/assets/…")

    # Silence unused
    _ = (TRADING_SYSTEM_ROLES, bekaa_roles, harbor_roles, cedar_profile)

    await mongo_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
