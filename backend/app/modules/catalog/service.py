"""Catalog & inventory business logic."""

from __future__ import annotations

import asyncio
import re
from decimal import Decimal
from typing import Any

from bson import Decimal128
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import BadRequestError, ForbiddenError
from app.db.transactions import run_in_transaction
from app.modules.catalog.constants import (
    BUYER_VISIBLE_PRODUCT_STATUSES,
    InventoryReferenceType,
    InventoryTransactionType,
    ProductStatus,
)
from app.modules.catalog.exceptions import (
    CategoryCycleError,
    CategoryInactiveError,
    CategoryNotFoundError,
    CategorySlugTakenError,
    DuplicateSkuError,
    InsufficientReservedError,
    InsufficientStockError,
    InvalidLeadTimeError,
    InvalidMoqError,
    InvalidPriceRangeError,
    InvalidStockQuantityError,
    InvalidUnitPriceError,
    InventoryNotFoundError,
    OverlappingPriceTierError,
    PriceNotFoundError,
    ProductNotFoundError,
    ProductNotOwnedError,
    ProductNotPublishableError,
)
from app.modules.catalog.repository import (
    CategoryRepository,
    InventoryRepository,
    InventoryTransactionRepository,
    ProductImageRepository,
    ProductPriceRepository,
    ProductRepository,
)
from app.modules.catalog.storage import delete_stored_file
from app.modules.identity.constants import BusinessAccountType, SupplierVerificationStatus
from app.modules.identity.repository import BusinessRepository, SupplierProfileRepository
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


def _slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:140] or "item"


def _money_str(value: Any) -> str:
    if isinstance(value, Decimal128):
        return format(value.to_decimal(), "f")
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _oid_str(value: Any | None) -> str | None:
    if value is None:
        return None
    return str(value)


def serialize_category(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "slug": doc["slug"],
        "description": doc.get("description"),
        "parent_category_id": _oid_str(doc.get("parent_category_id")),
        "is_active": bool(doc.get("is_active", True)),
        "display_order": int(doc.get("display_order") or 0),
        "image_url": doc.get("image_url"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def serialize_image(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "product_id": str(doc["product_id"]),
        "url": doc["url"],
        "alt_text": doc.get("alt_text"),
        "is_primary": bool(doc.get("is_primary", False)),
        "display_order": int(doc.get("display_order") or 0),
        "created_at": doc.get("created_at"),
    }


def serialize_price(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "product_id": str(doc["product_id"]),
        "min_quantity": int(doc["min_quantity"]),
        "max_quantity": doc.get("max_quantity"),
        "unit_price": _money_str(doc["unit_price"]),
        "currency": doc.get("currency") or "USD",
        "is_active": bool(doc.get("is_active", True)),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def serialize_inventory(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "product_id": str(doc["product_id"]),
        "available_quantity": _money_str(doc.get("available_quantity", 0)),
        "reserved_quantity": _money_str(doc.get("reserved_quantity", 0)),
        "updated_at": doc.get("updated_at"),
    }


def serialize_transaction(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "inventory_id": str(doc["inventory_id"]),
        "product_id": str(doc["product_id"]),
        "transaction_type": doc["transaction_type"],
        "quantity": _money_str(doc["quantity"]),
        "reference_type": doc.get("reference_type"),
        "reference_id": _oid_str(doc.get("reference_id")),
        "previous_available": _money_str(doc["previous_available"]),
        "previous_reserved": _money_str(doc["previous_reserved"]),
        "new_available": _money_str(doc["new_available"]),
        "new_reserved": _money_str(doc["new_reserved"]),
        "reason": doc.get("reason"),
        "created_by": _oid_str(doc.get("created_by")),
        "created_at": doc.get("created_at"),
    }


def serialize_product(
    doc: dict[str, Any],
    *,
    inventory: dict[str, Any] | None = None,
    prices: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
    supplier_name: str | None = None,
    supplier_logo_url: str | None = None,
    supplier_city: str | None = None,
    supplier_governorate: str | None = None,
    supplier_verified: bool = False,
) -> dict[str, Any]:
    payload = {
        "id": str(doc["_id"]),
        "supplier_id": str(doc["supplier_id"]),
        "business_account_id": str(doc["business_account_id"]),
        "supplier_name": supplier_name,
        "supplier_logo_url": supplier_logo_url,
        "supplier_city": supplier_city,
        "supplier_governorate": supplier_governorate,
        "supplier_verified": bool(supplier_verified),
        "category_id": str(doc["category_id"]),
        "sku": doc["sku"],
        "name": doc["name"],
        "slug": doc["slug"],
        "description": doc.get("description"),
        "unit": doc.get("unit") or "unit",
        "origin": doc.get("origin"),
        "moq": int(doc.get("moq") or 1),
        "lead_time_days": int(doc.get("lead_time_days") or 0),
        "status": doc.get("status") or ProductStatus.DRAFT,
        "is_featured": bool(doc.get("is_featured")),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if inventory is not None:
        payload["inventory"] = serialize_inventory(inventory)
    if prices is not None:
        payload["prices"] = [serialize_price(row) for row in prices]
    if images is not None:
        payload["images"] = [serialize_image(row) for row in images]
        primary = next((row for row in images if row.get("is_primary")), None)
        if primary is None and images:
            primary = images[0]
        payload["primary_image_url"] = primary.get("url") if primary else None
    return payload


def _ranges_overlap(
    a_min: int,
    a_max: int | None,
    b_min: int,
    b_max: int | None,
) -> bool:
    a_hi = a_max if a_max is not None else 10**12
    b_hi = b_max if b_max is not None else 10**12
    return a_min <= b_hi and b_min <= a_hi


class CatalogService:
    """Categories, products, prices, and inventory mutations."""

    def __init__(
        self,
        *,
        categories: CategoryRepository | None = None,
        products: ProductRepository | None = None,
        prices: ProductPriceRepository | None = None,
        inventories: InventoryRepository | None = None,
        transactions: InventoryTransactionRepository | None = None,
        businesses: BusinessRepository | None = None,
        supplier_profiles: SupplierProfileRepository | None = None,
    ) -> None:
        self.categories = categories or CategoryRepository()
        self.products = products or ProductRepository()
        self.prices = prices or ProductPriceRepository()
        self.images = ProductImageRepository()
        self.inventories = inventories or InventoryRepository()
        self.transactions = transactions or InventoryTransactionRepository()
        self.businesses = businesses or BusinessRepository()
        self.supplier_profiles = supplier_profiles or SupplierProfileRepository()

    # —— Categories ————————————————————————————————————————————————————————

    async def _supplier_info_by_business_ids(
        self, business_ids: list[Any]
    ) -> dict[str, dict[str, Any]]:
        unique = list({bid for bid in business_ids if bid is not None})
        if not unique:
            return {}
        rows = await self.businesses.find_many(
            {"_id": {"$in": unique}},
            limit=max(len(unique), 1),
        )
        profiles = await self.supplier_profiles.find_many(
            {"business_account_id": {"$in": unique}},
            limit=max(len(unique), 1),
        )
        verified_ids = {
            str(p["business_account_id"])
            for p in profiles
            if p.get("verification_status") == SupplierVerificationStatus.VERIFIED
        }
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            address = row.get("address") if isinstance(row.get("address"), dict) else {}
            bid = str(row["_id"])
            out[bid] = {
                "name": row.get("name"),
                "logo_url": row.get("logo_url"),
                "city": (address.get("city") or None) if address else None,
                "governorate": (
                    address.get("governorate") or address.get("state") or None
                )
                if address
                else None,
                "verified": bid in verified_ids,
            }
        return out

    async def _verified_supplier_business_oids(self) -> list[Any]:
        profiles = await self.supplier_profiles.find_many(
            {"verification_status": SupplierVerificationStatus.VERIFIED},
            limit=5000,
        )
        return [p["business_account_id"] for p in profiles if p.get("business_account_id")]

    async def deactivate_all_for_business(
        self,
        business_id: str,
        *,
        reason: str | None = None,
    ) -> int:
        """Soft-deactivate every listing for a supplier (revoke / loss of selling rights)."""
        oid = parse_object_id(business_id)
        now = utc_now()
        result = await self.products.collection.update_many(
            {
                "business_account_id": oid,
                "status": {"$ne": ProductStatus.INACTIVE},
            },
            {
                "$set": {
                    "status": ProductStatus.INACTIVE,
                    "updated_at": now,
                    "deactivated_reason": reason or "supplier_selling_rights_revoked",
                }
            },
        )
        try:
            from app.modules.cart.repository import CartItemRepository

            await CartItemRepository().delete_for_supplier(business_id)
        except Exception:
            pass
        return int(result.modified_count)

    # ── Categories ─────────────────────────────────────────────────────────

    async def create_category(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        parent_category_id: str | None,
        display_order: int,
        is_active: bool,
    ) -> dict[str, Any]:
        resolved_slug = _slugify(slug or name)
        if await self.categories.get_by_slug(resolved_slug):
            raise CategorySlugTakenError()
        parent_oid = None
        if parent_category_id:
            parent = await self.categories.get_by_id(parent_category_id)
            if parent is None:
                raise CategoryNotFoundError()
            parent_oid = parent["_id"]
        now = utc_now()
        try:
            doc = await self.categories.create(
                {
                    "name": name.strip(),
                    "slug": resolved_slug,
                    "description": description,
                    "parent_category_id": parent_oid,
                    "is_active": is_active,
                    "display_order": display_order,
                    "image_url": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except DuplicateKeyError as exc:
            raise CategorySlugTakenError() from exc
        return serialize_category(doc)

    async def list_categories(
        self,
        *,
        parent_category_id: str | None = None,
        active_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if parent_category_id == "":
            query["parent_category_id"] = None
        elif parent_category_id:
            query["parent_category_id"] = parse_object_id(parent_category_id)
        if active_only:
            query["is_active"] = True
        total = await self.categories.count(query)
        rows = await self.categories.find_many(
            query,
            skip=(page - 1) * page_size,
            limit=page_size,
            sort=[("display_order", 1), ("name", 1)],
        )
        return [serialize_category(row) for row in rows], total

    async def get_category(self, category_id: str) -> dict[str, Any]:
        doc = await self.categories.get_by_id(category_id)
        if doc is None:
            raise CategoryNotFoundError()
        return serialize_category(doc)

    async def update_category(
        self,
        category_id: str,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        parent_category_id: str | None = None,
        clear_parent: bool = False,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        doc = await self.categories.get_by_id(category_id)
        if doc is None:
            raise CategoryNotFoundError()
        updates: dict[str, Any] = {"updated_at": utc_now()}
        if name is not None:
            updates["name"] = name.strip()
        if slug is not None:
            resolved = _slugify(slug)
            existing = await self.categories.get_by_slug(resolved)
            if existing and str(existing["_id"]) != category_id:
                raise CategorySlugTakenError()
            updates["slug"] = resolved
        if description is not None:
            updates["description"] = description
        if display_order is not None:
            updates["display_order"] = display_order
        if is_active is not None:
            updates["is_active"] = is_active
        if clear_parent:
            updates["parent_category_id"] = None
        elif parent_category_id is not None:
            if parent_category_id == category_id:
                raise CategoryCycleError()
            parent = await self.categories.get_by_id(parent_category_id)
            if parent is None:
                raise CategoryNotFoundError()
            await self._assert_no_cycle(category_id, parent_category_id)
            updates["parent_category_id"] = parent["_id"]
        try:
            updated = await self.categories.update(category_id, updates)
        except DuplicateKeyError as exc:
            raise CategorySlugTakenError() from exc
        assert updated is not None
        return serialize_category(updated)

    async def delete_category(self, category_id: str) -> None:
        """Soft-delete: deactivate. Document and media stay for reactivation."""
        doc = await self.categories.get_by_id(category_id)
        if doc is None:
            raise CategoryNotFoundError()
        children = await self.categories.count(
            {
                "parent_category_id": parse_object_id(category_id),
                "is_active": {"$ne": False},
            }
        )
        if children:
            raise BadRequestError("Category has child categories; reassign or delete them first")
        products = await self.products.count({"category_id": parse_object_id(category_id)})
        if products:
            raise BadRequestError("Category has products; reassign them first")
        await self.categories.update(
            category_id,
            {"is_active": False, "updated_at": utc_now()},
        )

    async def set_category_image(self, category_id: str, *, url: str) -> dict[str, Any]:
        doc = await self.categories.get_by_id(category_id)
        if doc is None:
            raise CategoryNotFoundError()
        previous = doc.get("image_url")
        updated = await self.categories.update(
            category_id,
            {"image_url": url, "updated_at": utc_now()},
        )
        if updated is None:
            raise CategoryNotFoundError()
        if previous and previous != url:
            delete_stored_file(previous)
        return serialize_category(updated)

    async def clear_category_image(self, category_id: str) -> dict[str, Any]:
        doc = await self.categories.get_by_id(category_id)
        if doc is None:
            raise CategoryNotFoundError()
        previous = doc.get("image_url")
        updated = await self.categories.update(
            category_id,
            {"image_url": None, "updated_at": utc_now()},
        )
        if updated is None:
            raise CategoryNotFoundError()
        delete_stored_file(previous)
        return serialize_category(updated)

    # —— Category graph helpers ————————————————————————————————————————————

    async def _assert_no_cycle(self, category_id: str, new_parent_id: str) -> None:
        cursor = new_parent_id
        seen: set[str] = {category_id}
        while cursor:
            if cursor in seen:
                raise CategoryCycleError()
            seen.add(cursor)
            parent = await self.categories.get_by_id(cursor)
            if parent is None:
                raise CategoryNotFoundError()
            parent_ref = parent.get("parent_category_id")
            cursor = str(parent_ref) if parent_ref else ""

    async def _require_active_category(self, category_id: str) -> dict[str, Any]:
        category = await self.categories.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundError()
        if not category.get("is_active", True):
            raise CategoryInactiveError()
        return category

    # ── Products ───────────────────────────────────────────────────────────

    async def create_product(
        self,
        *,
        business_id: str,
        category_id: str,
        sku: str,
        name: str,
        slug: str | None,
        description: str | None,
        unit: str,
        origin: str | None,
        moq: int,
        lead_time_days: int,
        status: str,
        is_featured: bool = False,
    ) -> dict[str, Any]:
        if moq < 1:
            raise InvalidMoqError()
        if lead_time_days < 0:
            raise InvalidLeadTimeError()
        business = await self.businesses.get_by_id(business_id)
        if business is None or business.get("type") != BusinessAccountType.SUPPLIER:
            raise ForbiddenError("Only supplier companies can create products")
        profile = await self.supplier_profiles.get_by_business(business_id)
        if profile is None:
            raise ForbiddenError("Supplier profile not found")
        await self._require_active_category(category_id)
        if status == ProductStatus.ACTIVE:
            raise ProductNotPublishableError("save as draft first, then add pricing and stock before publishing")

        now = utc_now()
        resolved_slug = _slugify(slug or name)
        payload = {
            "supplier_id": profile["_id"],
            "business_account_id": parse_object_id(business_id),
            "category_id": parse_object_id(category_id),
            "sku": sku.strip().upper(),
            "name": name.strip(),
            "slug": resolved_slug,
            "description": description,
            "unit": unit,
            "origin": origin.strip() if origin else None,
            "moq": moq,
            "lead_time_days": lead_time_days,
            "status": ProductStatus.DRAFT,
            "is_featured": bool(is_featured),
            "created_at": now,
            "updated_at": now,
        }

        async def work(session: MongoSession) -> tuple[dict[str, Any], dict[str, Any]]:
            try:
                product = await self.products.create(payload, session=session)
            except DuplicateKeyError as exc:
                raise DuplicateSkuError(payload["sku"]) from exc
            inventory = await self.inventories.create(
                {
                    "product_id": product["_id"],
                    "available_quantity": to_decimal128(Decimal("0")),
                    "reserved_quantity": to_decimal128(Decimal("0")),
                    "updated_at": now,
                },
                session=session,
            )
            return product, inventory

        product, inventory = await run_in_transaction(work)
        return serialize_product(product, inventory=inventory, prices=[])

    async def list_products(
        self,
        *,
        viewer_business_id: str | None,
        viewer_business_type: str | None,
        can_manage: bool,
        supplier_business_id: str | None = None,
        category_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
        featured: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        include_details: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if supplier_business_id:
            query["business_account_id"] = parse_object_id(supplier_business_id)
        if category_id:
            query["category_id"] = parse_object_id(category_id)
        if q:
            query["name"] = {"$regex": re.escape(q.strip()), "$options": "i"}
        if featured is True:
            query["is_featured"] = True

        # Suppliers manage / view their own catalog only (never the full marketplace).
        is_supplier_viewer = (
            viewer_business_type == BusinessAccountType.SUPPLIER
            and viewer_business_id is not None
        )
        is_platform_viewer = viewer_business_type == BusinessAccountType.PLATFORM
        viewing_own = is_supplier_viewer and (
            supplier_business_id is None
            or supplier_business_id == viewer_business_id
        )
        if viewing_own and "business_account_id" not in query:
            query["business_account_id"] = parse_object_id(viewer_business_id)

        # Platform staff may inspect the full marketplace catalog (all suppliers /
        # statuses). Supplier managers may include draft/inactive for their own rows.
        manage_own = can_manage and viewing_own
        platform_oversight = bool(is_platform_viewer)
        if (manage_own or platform_oversight) and status:
            query["status"] = status
        elif manage_own or platform_oversight:
            pass
        else:
            # Buyers / public browse: active listings from verified suppliers only.
            # Inactive / revoked listings never appear in marketplace browsing.
            query["status"] = ProductStatus.ACTIVE
            if status and status != ProductStatus.ACTIVE:
                return [], 0
            verified_oids = await self._verified_supplier_business_oids()
            if not verified_oids:
                return [], 0
            if "business_account_id" in query:
                requested = query["business_account_id"]
                if str(requested) not in {str(v) for v in verified_oids}:
                    return [], 0
            else:
                query["business_account_id"] = {"$in": verified_oids}

        total = await self.products.count(query)
        rows = await self.products.find_many(
            query,
            skip=(page - 1) * page_size,
            limit=page_size,
            sort=[("updated_at", -1)],
        )
        suppliers = await self._supplier_info_by_business_ids(
            [row.get("business_account_id") for row in rows]
        )

        inventories_by_product: dict[Any, dict[str, Any]] = {}
        prices_by_product: dict[Any, list[dict[str, Any]]] = {}
        images_by_product: dict[Any, list[dict[str, Any]]] = {}
        if include_details and rows:
            product_ids = [row["_id"] for row in rows]
            invent_rows, price_rows, image_rows = await asyncio.gather(
                self.inventories.find_many(
                    {"product_id": {"$in": product_ids}},
                    limit=max(len(product_ids), 1),
                ),
                self.prices.find_many(
                    {"product_id": {"$in": product_ids}},
                    limit=max(len(product_ids) * 20, 1),
                    sort=[("min_quantity", 1)],
                ),
                self.images.find_many(
                    {"product_id": {"$in": product_ids}, "deleted_at": None},
                    limit=max(len(product_ids) * 20, 1),
                    sort=[("display_order", 1), ("created_at", 1)],
                ),
            )
            for inv in invent_rows:
                inventories_by_product[inv["product_id"]] = inv
            for price in price_rows:
                prices_by_product.setdefault(price["product_id"], []).append(price)
            for image in image_rows:
                images_by_product.setdefault(image["product_id"], []).append(image)

        results: list[dict[str, Any]] = []
        for row in rows:
            inventory = inventories_by_product.get(row["_id"]) if include_details else None
            prices = prices_by_product.get(row["_id"], []) if include_details else None
            images = images_by_product.get(row["_id"], []) if include_details else None
            info = suppliers.get(str(row["business_account_id"]), {})
            results.append(
                serialize_product(
                    row,
                    inventory=inventory,
                    prices=prices,
                    images=images,
                    supplier_name=info.get("name"),
                    supplier_logo_url=info.get("logo_url"),
                    supplier_city=info.get("city"),
                    supplier_governorate=info.get("governorate"),
                    supplier_verified=bool(info.get("verified")),
                )
            )
        return results, total

    async def get_product(
        self,
        product_id: str,
        *,
        viewer_business_id: str | None,
        can_manage: bool,
        include_details: bool = True,
        viewer_business_type: str | None = None,
    ) -> dict[str, Any]:
        doc = await self.products.get_by_id(product_id)
        if doc is None:
            raise ProductNotFoundError()
        owns = viewer_business_id is not None and str(doc["business_account_id"]) == viewer_business_id
        is_platform = viewer_business_type == BusinessAccountType.PLATFORM
        if doc.get("status") not in BUYER_VISIBLE_PRODUCT_STATUSES and not (
            (can_manage and owns) or is_platform
        ):
            raise ProductNotFoundError()
        inventory = await self.inventories.get_by_product(doc["_id"]) if include_details else None
        prices = await self.prices.list_for_product(doc["_id"]) if include_details else None
        images = await self.images.list_for_product(doc["_id"]) if include_details else None
        info = (
            await self._supplier_info_by_business_ids([doc.get("business_account_id")])
        ).get(str(doc["business_account_id"]), {})
        if not ((can_manage and owns) or is_platform) and not info.get("verified"):
            # Revoked / unverified suppliers must not be orderable even if a row was left active.
            raise ProductNotFoundError()
        return serialize_product(
            doc,
            inventory=inventory,
            prices=prices,
            images=images,
            supplier_name=info.get("name"),
            supplier_logo_url=info.get("logo_url"),
            supplier_city=info.get("city"),
            supplier_governorate=info.get("governorate"),
            supplier_verified=bool(info.get("verified")),
        )

    async def update_product(
        self,
        product_id: str,
        *,
        business_id: str,
        category_id: str | None = None,
        sku: str | None = None,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        unit: str | None = None,
        origin: str | None = None,
        moq: int | None = None,
        lead_time_days: int | None = None,
        status: str | None = None,
        is_featured: bool | None = None,
    ) -> dict[str, Any]:
        doc = await self._require_owned_product(product_id, business_id)
        updates: dict[str, Any] = {"updated_at": utc_now()}
        if category_id is not None:
            await self._require_active_category(category_id)
            updates["category_id"] = parse_object_id(category_id)
        if sku is not None:
            updates["sku"] = sku.strip().upper()
        if name is not None:
            updates["name"] = name.strip()
        if slug is not None:
            updates["slug"] = _slugify(slug)
        if description is not None:
            updates["description"] = description
        if unit is not None:
            updates["unit"] = unit
        if origin is not None:
            updates["origin"] = origin.strip() or None
        if moq is not None:
            if moq < 1:
                raise InvalidMoqError()
            updates["moq"] = moq
        if lead_time_days is not None:
            if lead_time_days < 0:
                raise InvalidLeadTimeError()
            updates["lead_time_days"] = lead_time_days
        if status is not None:
            if status == ProductStatus.ACTIVE:
                await self._assert_publishable(doc, updates)
            updates["status"] = status
        if is_featured is not None:
            updates["is_featured"] = bool(is_featured)
        try:
            updated = await self.products.update(product_id, updates)
        except DuplicateKeyError as exc:
            raise DuplicateSkuError(str(updates.get("sku") or doc["sku"])) from exc
        assert updated is not None
        inventory = await self.inventories.get_by_product(updated["_id"])
        prices = await self.prices.list_for_product(updated["_id"])
        images = await self.images.list_for_product(updated["_id"])
        return serialize_product(
            updated, inventory=inventory, prices=prices, images=images
        )

    async def delete_product(self, product_id: str, *, business_id: str) -> None:
        await self._require_owned_product(product_id, business_id)
        # Soft-deactivate rather than hard-delete commercial history anchors.
        await self.products.update(
            product_id,
            {"status": ProductStatus.INACTIVE, "updated_at": utc_now()},
        )
        try:
            from app.modules.cart.repository import CartItemRepository

            await CartItemRepository().delete_for_product(product_id)
        except Exception:
            pass

    async def add_product_image(
        self,
        product_id: str,
        *,
        business_id: str,
        url: str,
        alt_text: str | None = None,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        await self._require_owned_product(product_id, business_id)
        existing = await self.images.list_for_product(product_id)
        make_primary = is_primary or len(existing) == 0
        if make_primary and existing:
            await self.images.collection.update_many(
                {"product_id": parse_object_id(product_id)},
                {"$set": {"is_primary": False}},
            )
        now = utc_now()
        doc = await self.images.create(
            {
                "product_id": parse_object_id(product_id),
                "url": url,
                "alt_text": alt_text,
                "is_primary": make_primary,
                "display_order": len(existing),
                "created_at": now,
            }
        )
        return serialize_image(doc)

    async def set_primary_image(
        self,
        product_id: str,
        image_id: str,
        *,
        business_id: str,
    ) -> dict[str, Any]:
        await self._require_owned_product(product_id, business_id)
        image = await self.images.get_by_id(image_id)
        if image is None or str(image["product_id"]) != product_id:
            raise ProductNotFoundError()
        await self.images.collection.update_many(
            {"product_id": parse_object_id(product_id)},
            {"$set": {"is_primary": False}},
        )
        updated = await self.images.update(image_id, {"is_primary": True})
        assert updated is not None
        return serialize_image(updated)

    async def delete_product_image(
        self,
        product_id: str,
        image_id: str,
        *,
        business_id: str,
    ) -> None:
        """Soft-delete: mark deleted_at. File stays so the gallery can be restored."""
        await self._require_owned_product(product_id, business_id)
        image = await self.images.get_by_id(image_id)
        if image is None or str(image["product_id"]) != product_id:
            raise ProductNotFoundError()
        if image.get("deleted_at") is not None:
            return
        was_primary = bool(image.get("is_primary"))
        await self.images.update(
            image_id,
            {
                "deleted_at": utc_now(),
                "is_primary": False,
            },
        )
        if was_primary:
            remaining = await self.images.list_for_product(product_id)
            if remaining:
                await self.images.update(str(remaining[0]["_id"]), {"is_primary": True})

    async def _require_owned_product(self, product_id: str, business_id: str) -> dict[str, Any]:
        doc = await self.products.get_by_id(product_id)
        if doc is None:
            raise ProductNotFoundError()
        if str(doc["business_account_id"]) != business_id:
            raise ProductNotOwnedError()
        return doc

    async def _assert_publishable(self, doc: dict[str, Any], pending: dict[str, Any]) -> None:
        business_id = str(doc.get("business_account_id") or "")
        if business_id:
            profile = await self.supplier_profiles.get_by_business(business_id)
            if (
                profile is None
                or profile.get("verification_status") != SupplierVerificationStatus.VERIFIED
            ):
                raise ProductNotPublishableError(
                    "your company must be verified before listings can go live"
                )
        moq = int(pending.get("moq", doc.get("moq") or 0))
        if moq < 1:
            raise ProductNotPublishableError("MOQ must be greater than 0")
        inventory = await self.inventories.get_by_product(doc["_id"])
        if inventory is None:
            raise ProductNotPublishableError("add inventory before publishing")
        price_count = await self.prices.count_active_for_product(doc["_id"])
        if price_count < 1:
            raise ProductNotPublishableError("add at least one active price before publishing")

    # ── Pricing ────────────────────────────────────────────────────────────

    async def list_prices(self, product_id: str) -> list[dict[str, Any]]:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError()
        rows = await self.prices.list_for_product(product_id)
        return [serialize_price(row) for row in rows]

    async def create_price(
        self,
        product_id: str,
        *,
        business_id: str,
        min_quantity: int,
        max_quantity: int | None,
        unit_price: Decimal,
        currency: str,
        is_active: bool,
    ) -> dict[str, Any]:
        await self._require_owned_product(product_id, business_id)
        if unit_price <= 0:
            raise InvalidUnitPriceError()
        if min_quantity < 1:
            raise InvalidPriceRangeError("Minimum tier quantity must be greater than zero")
        if max_quantity is not None and max_quantity < min_quantity:
            raise InvalidPriceRangeError("Maximum tier quantity must be at least the minimum")
        existing = await self.prices.list_for_product(product_id)
        for row in existing:
            if not row.get("is_active", True):
                continue
            if _ranges_overlap(
                min_quantity,
                max_quantity,
                int(row["min_quantity"]),
                row.get("max_quantity"),
            ):
                raise OverlappingPriceTierError()
        now = utc_now()
        doc = await self.prices.create(
            {
                "product_id": parse_object_id(product_id),
                "min_quantity": min_quantity,
                "max_quantity": max_quantity,
                "unit_price": to_decimal128(unit_price),
                "currency": currency,
                "is_active": is_active,
                "created_at": now,
                "updated_at": now,
            }
        )
        return serialize_price(doc)

    async def update_price(
        self,
        product_id: str,
        price_id: str,
        *,
        business_id: str,
        min_quantity: int | None = None,
        max_quantity: int | None = None,
        clear_max_quantity: bool = False,
        unit_price: Decimal | None = None,
        currency: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        await self._require_owned_product(product_id, business_id)
        price = await self.prices.get_by_id(price_id)
        if price is None or str(price["product_id"]) != product_id:
            raise PriceNotFoundError()
        new_min = min_quantity if min_quantity is not None else int(price["min_quantity"])
        if clear_max_quantity:
            new_max: int | None = None
        elif max_quantity is not None:
            new_max = max_quantity
        else:
            new_max = price.get("max_quantity")
        if new_min < 1:
            raise InvalidPriceRangeError("Minimum tier quantity must be greater than zero")
        if new_max is not None and new_max < new_min:
            raise InvalidPriceRangeError("Maximum tier quantity must be at least the minimum")
        if unit_price is not None and unit_price <= 0:
            raise InvalidUnitPriceError()
        active = is_active if is_active is not None else bool(price.get("is_active", True))
        if active:
            for row in await self.prices.list_for_product(product_id):
                if str(row["_id"]) == price_id or not row.get("is_active", True):
                    continue
                if _ranges_overlap(new_min, new_max, int(row["min_quantity"]), row.get("max_quantity")):
                    raise OverlappingPriceTierError()
        updates: dict[str, Any] = {"updated_at": utc_now(), "min_quantity": new_min, "max_quantity": new_max}
        if unit_price is not None:
            updates["unit_price"] = to_decimal128(unit_price)
        if currency is not None:
            updates["currency"] = currency
        if is_active is not None:
            updates["is_active"] = is_active
        updated = await self.prices.update(price_id, updates)
        assert updated is not None
        return serialize_price(updated)

    async def delete_price(self, product_id: str, price_id: str, *, business_id: str) -> None:
        """Soft-delete: deactivate and hide the tier. Row stays for commercial history."""
        await self._require_owned_product(product_id, business_id)
        price = await self.prices.get_by_id(price_id)
        if price is None or str(price["product_id"]) != product_id:
            raise PriceNotFoundError()
        if price.get("deleted_at") is not None:
            return
        await self.prices.update(
            price_id,
            {
                "is_active": False,
                "deleted_at": utc_now(),
                "updated_at": utc_now(),
            },
        )

    def resolve_unit_price(
        self, tiers: list[dict[str, Any]], quantity: int
    ) -> dict[str, Any] | None:
        """Return the active serialized tier that covers `quantity`, if any."""
        matches: list[dict[str, Any]] = []
        for row in tiers:
            if not row.get("is_active", True):
                continue
            lo = int(row["min_quantity"])
            hi = row.get("max_quantity")
            if quantity < lo:
                continue
            if hi is not None and quantity > int(hi):
                continue
            matches.append(row)
        if not matches:
            return None
        matches.sort(key=lambda r: int(r["min_quantity"]), reverse=True)
        return matches[0]

    # ── Inventory ──────────────────────────────────────────────────────────

    async def get_inventory(
        self,
        product_id: str,
        *,
        business_id: str | None,
        require_own: bool,
    ) -> dict[str, Any]:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError()
        owns = business_id is not None and str(product["business_account_id"]) == business_id
        if require_own and not owns:
            raise ProductNotOwnedError()
        if not owns and product.get("status") not in BUYER_VISIBLE_PRODUCT_STATUSES:
            raise ProductNotFoundError()
        inventory = await self.inventories.get_by_product(product_id)
        if inventory is None:
            raise InventoryNotFoundError()
        return serialize_inventory(inventory)

    async def add_stock(
        self,
        product_id: str,
        *,
        business_id: str,
        user_id: str,
        quantity: Decimal,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._mutate_stock(
            product_id,
            business_id=business_id,
            user_id=user_id,
            quantity=quantity,
            kind=InventoryTransactionType.STOCK_RECEIVED,
            reason=reason,
            reference_type=reference_type or InventoryReferenceType.MANUAL,
            reference_id=reference_id,
        )

    async def reserve_stock(
        self,
        product_id: str,
        *,
        business_id: str,
        user_id: str,
        quantity: Decimal,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._mutate_stock(
            product_id,
            business_id=business_id,
            user_id=user_id,
            quantity=quantity,
            kind=InventoryTransactionType.RESERVATION,
            reason=reason,
            reference_type=reference_type or InventoryReferenceType.ORDER,
            reference_id=reference_id,
        )

    async def release_stock(
        self,
        product_id: str,
        *,
        business_id: str,
        user_id: str,
        quantity: Decimal,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._mutate_stock(
            product_id,
            business_id=business_id,
            user_id=user_id,
            quantity=quantity,
            kind=InventoryTransactionType.RESERVATION_RELEASE,
            reason=reason,
            reference_type=reference_type or InventoryReferenceType.ORDER,
            reference_id=reference_id,
        )

    async def sale_stock(
        self,
        product_id: str,
        *,
        business_id: str,
        user_id: str,
        quantity: Decimal,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._mutate_stock(
            product_id,
            business_id=business_id,
            user_id=user_id,
            quantity=quantity,
            kind=InventoryTransactionType.SALE,
            reason=reason,
            reference_type=reference_type or InventoryReferenceType.ORDER,
            reference_id=reference_id,
        )

    async def list_transactions(
        self,
        product_id: str,
        *,
        business_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        await self._require_owned_product(product_id, business_id)
        inventory = await self.inventories.get_by_product(product_id)
        if inventory is None:
            raise InventoryNotFoundError()
        query = {"inventory_id": inventory["_id"]}
        total = await self.transactions.count(query)
        rows = await self.transactions.list_for_inventory(
            inventory["_id"],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return [serialize_transaction(row) for row in rows], total

    async def _mutate_stock(
        self,
        product_id: str,
        *,
        business_id: str,
        user_id: str,
        quantity: Decimal,
        kind: InventoryTransactionType,
        reason: str | None,
        reference_type: str | None,
        reference_id: str | None,
    ) -> dict[str, Any]:
        if quantity <= 0:
            raise InvalidStockQuantityError()
        await self._require_owned_product(product_id, business_id)
        inventory = await self.inventories.get_by_product(product_id)
        if inventory is None:
            raise InventoryNotFoundError()

        prev_available = _as_decimal(inventory["available_quantity"])
        prev_reserved = _as_decimal(inventory["reserved_quantity"])
        now = utc_now()
        ref_oid = parse_object_id(reference_id) if reference_id else None

        async def work(session: MongoSession) -> dict[str, Any]:
            if kind == InventoryTransactionType.STOCK_RECEIVED:
                updated = await self.inventories.add_stock(
                    product_id=product_id,
                    quantity=quantity,
                    updated_at=now,
                    session=session,
                )
            elif kind == InventoryTransactionType.RESERVATION:
                updated = await self.inventories.conditional_reserve(
                    product_id=product_id,
                    quantity=quantity,
                    updated_at=now,
                    session=session,
                )
                if updated is None:
                    raise InsufficientStockError()
            elif kind == InventoryTransactionType.RESERVATION_RELEASE:
                updated = await self.inventories.conditional_release(
                    product_id=product_id,
                    quantity=quantity,
                    updated_at=now,
                    session=session,
                )
                if updated is None:
                    raise InsufficientReservedError()
            elif kind == InventoryTransactionType.SALE:
                updated = await self.inventories.conditional_sale(
                    product_id=product_id,
                    quantity=quantity,
                    updated_at=now,
                    session=session,
                )
                if updated is None:
                    raise InsufficientReservedError()
            else:
                raise BadRequestError(f"Unsupported inventory transaction type: {kind}")

            assert updated is not None
            new_available = _as_decimal(updated["available_quantity"])
            new_reserved = _as_decimal(updated["reserved_quantity"])
            # Re-read previous from before update for accurate history when concurrent.
            # For stock_received / success paths, compute from deltas.
            if kind == InventoryTransactionType.STOCK_RECEIVED:
                p_avail, p_res = new_available - quantity, new_reserved
            elif kind == InventoryTransactionType.RESERVATION:
                p_avail, p_res = new_available + quantity, new_reserved - quantity
            elif kind == InventoryTransactionType.RESERVATION_RELEASE:
                p_avail, p_res = new_available - quantity, new_reserved + quantity
            else:  # SALE
                p_avail, p_res = new_available, new_reserved + quantity

            tx = await self.transactions.create(
                {
                    "inventory_id": updated["_id"],
                    "product_id": parse_object_id(product_id),
                    "transaction_type": kind,
                    "quantity": to_decimal128(quantity),
                    "reference_type": reference_type,
                    "reference_id": ref_oid,
                    "previous_available": to_decimal128(p_avail),
                    "previous_reserved": to_decimal128(p_res),
                    "new_available": to_decimal128(new_available),
                    "new_reserved": to_decimal128(new_reserved),
                    "reason": reason,
                    "created_by": parse_object_id(user_id),
                    "created_at": now,
                },
                session=session,
            )
            return {"inventory": updated, "transaction": tx}

        # Capture unused locals for lint clarity of pre-read snapshot.
        _ = (prev_available, prev_reserved)
        result = await run_in_transaction(work)
        return {
            "inventory": serialize_inventory(result["inventory"]),
            "transaction": serialize_transaction(result["transaction"]),
        }
