"""Procurement & fulfilment service — RFQ → quote → award → PO → shipment → receive."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import Decimal128, ObjectId
from pymongo import ReturnDocument

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.db.transactions import run_in_transaction
from app.modules.identity.constants import (
    BusinessAccountStatus,
    BusinessAccountType,
    SupplierVerificationStatus,
)
from app.modules.procurement.commercial import (
    compute_document_totals,
    compute_line,
    money,
    optional_money,
    quantize,
)
from app.modules.catalog.constants import ProductStatus
from app.modules.procurement.constants import (
    ORDER_TRANSITIONS,
    QUOTATION_TRANSITIONS,
    RFQ_TRANSITIONS,
    SHIPMENT_TRANSITIONS,
    OrderStatus,
    QuotationStatus,
    RFQStatus,
    RFQType,
    RFQVisibility,
    ShipmentStatus,
    SupplierInviteStatus,
    assert_transition,
)
from app.modules.procurement.exceptions import (
    OrderNotFoundError,
    ProcurementConflictError,
    ProcurementForbiddenError,
    ProcurementValidationError,
    ProductRFQValidationError,
    QuotationNotFoundError,
    RFQNotFoundError,
    ShipmentNotFoundError,
    SourcingRFQValidationError,
)
from app.modules.procurement.notify import notify
from app.modules.procurement.repository import (
    OrderItemRepository,
    OrderRepository,
    QuotationItemRepository,
    QuotationRepository,
    RFQItemRepository,
    RFQRepository,
    ShipmentItemRepository,
    ShipmentRepository,
)
from app.shared.events.bus import (
    ORDER_CREATED,
    QUOTATION_ACCEPTED,
    RFQ_PUBLISHED,
    SHIPMENT_DELIVERED,
    DomainEvent,
    event_bus,
)
from app.shared.services.audit import AuditService
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id
from app.modules.settings.tax import compute_tax, as_decimal as tax_as_decimal


def _dec(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money_out(value: Any) -> str | None:
    if value is None:
        return None
    return format(_dec(value), "f")


def _rate_out(value: Any) -> str | None:
    if value is None:
        return None
    return format(tax_as_decimal(value).quantize(Decimal("0.0001")), "f")


def _pct_label(rate: Any) -> str | None:
    if rate is None:
        return None
    pct = tax_as_decimal(rate) * Decimal("100")
    text = format(pct.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".")
    return f"{text}%"


async def _active_tax_settings() -> dict[str, Any] | None:
    from app.modules.settings.service import SettingsService

    return await SettingsService().get_active_tax()


def _compose_order_money(
    *,
    subtotal: Any,
    discount_total: Any = "0",
    charge_total: Any = "0",
    tax_rate: Any | None = None,
    existing_tax_total: Any | None = None,
) -> dict[str, Any]:
    """Apply platform VAT when a rate is provided; otherwise keep existing tax."""
    sub = _dec(subtotal)
    disc = _dec(discount_total or "0")
    charge = _dec(charge_total or "0")
    if tax_rate is not None:
        computed = compute_tax(subtotal=sub, discount=disc, rate=tax_rate)
        tax_total = computed["tax_amount"]
        taxable = computed["taxable_amount"]
        total = quantize(taxable + tax_total + charge)
        return {
            "subtotal": quantize(sub),
            "discount_total": quantize(disc),
            "charge_total": quantize(charge),
            "tax_total": tax_total,
            "total": total,
            "tax_rate_snapshot": computed["tax_rate"],
        }
    tax_total = _dec(existing_tax_total or "0")
    total = quantize(sub - disc + charge + tax_total)
    return {
        "subtotal": quantize(sub),
        "discount_total": quantize(disc),
        "charge_total": quantize(charge),
        "tax_total": quantize(tax_total),
        "total": total,
        "tax_rate_snapshot": None,
    }


def group_catalog_items_by_supplier(
    items: list[dict[str, Any]],
    *,
    product_owners: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Bucket RFQ lines by owning supplier. Unowned/open lines use key ''."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        sid = item.get("supplier_business_id")
        if sid:
            key = str(sid)
        else:
            pid = item.get("product_id")
            key = product_owners.get(str(pid), "") if pid else ""
        groups.setdefault(key, []).append(item)
    return groups


def freeze_catalog_price(
    *,
    previous: Any = None,
    looked_up: Any = None,
    client: Any = None,
) -> Any:
    """Listed price is frozen at snapshot. The buyer cannot overwrite it later."""
    if previous is not None:
        return previous
    if looked_up is not None:
        return looked_up
    return client


def rfq_is_unsent(rfq: dict[str, Any]) -> bool:
    """True until suppliers are invited. Publish-without-invite is still editable."""
    if str(rfq.get("status") or "") in {
        RFQStatus.CANCELLED,
        RFQStatus.EXPIRED,
        RFQStatus.AWARDED,
    }:
        return False
    return not (rfq.get("supplier_invites") or [])


def quotation_cannot_be_edited(status: str, *, allow_revision: bool = False) -> str | None:
    """Supplier quotation fields freeze after submit. Negotiation may revise internally.

    Passing on a counter must not lock the quote. ``rejected`` can still be revived
    when a later counter is taken (``allow_revision=True``). Awarded quotes stay frozen.
    """
    if status in {
        QuotationStatus.ACCEPTED,
        QuotationStatus.WITHDRAWN,
        QuotationStatus.EXPIRED,
    }:
        return "Cannot modify an accepted or rejected quotation"
    if status == QuotationStatus.REJECTED and not allow_revision:
        return "Cannot modify an accepted or rejected quotation"
    if status in {QuotationStatus.SUBMITTED, QuotationStatus.NEGOTIATING} and not allow_revision:
        return "This quotation was already submitted and cannot be changed"
    return None


def _item_doc_to_payload(item: dict[str, Any]) -> dict[str, Any]:
    sid = item.get("supplier_business_id")
    return {
        "product_id": str(item["product_id"]) if item.get("product_id") else None,
        "category_id": str(item["category_id"]) if item.get("category_id") else None,
        "product_name": item.get("product_name") or "Product",
        "sku": item.get("sku"),
        "quantity": _money_out(item.get("quantity")) or "1",
        "unit": item.get("unit") or "unit",
        "catalog_unit_price": _money_out(item.get("catalog_unit_price")),
        "target_unit_price": _money_out(item.get("target_unit_price")),
        "primary_image_url": item.get("primary_image_url"),
        "requirements": item.get("requirements"),
        "notes": item.get("notes"),
        "supplier_business_id": str(sid) if sid else None,
    }


def _oid(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _public_evidence_url(shipment_id: str, stored_url: str | None) -> str | None:
    from app.modules.procurement.storage import public_evidence_url

    return public_evidence_url(shipment_id=shipment_id, stored_url=stored_url)


class ProcurementService:
    """RFQ → quotation → award → PO → shipment → receive."""

    def __init__(self) -> None:
        self.rfqs = RFQRepository()
        self.rfq_items = RFQItemRepository()
        self.quotations = QuotationRepository()
        self.quotation_items = QuotationItemRepository()
        self.orders = OrderRepository()
        self.order_items = OrderItemRepository()
        self.shipments = ShipmentRepository()
        self.shipment_items = ShipmentItemRepository()
        self.audit = AuditService()

    def _require_buyer(self, business: dict[str, Any] | None) -> str:
        if not business or str(business.get("type")) != BusinessAccountType.BUYER:
            raise ProcurementForbiddenError("Select a buyer company to continue")
        return str(business["_id"])

    def _require_supplier(self, business: dict[str, Any] | None) -> str:
        if not business or str(business.get("type")) != BusinessAccountType.SUPPLIER:
            raise ProcurementForbiddenError("Select a supplier company to continue")
        return str(business["_id"])

    async def _next_number(self, prefix: str, collection: CollectionName, field: str) -> str:
        year = utc_now().year
        head = f"{prefix}-{year}-"
        count = await mongo_manager.collection(str(collection)).count_documents(
            {field: {"$regex": f"^{head}"}}
        )
        return f"{head}{count + 1:04d}"

    async def _verified_supplier_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        oids = [parse_object_id(i) for i in ids]
        profiles = (
            await mongo_manager.collection(CollectionName.SUPPLIER_PROFILES)
            .find(
                {
                    "business_account_id": {"$in": oids},
                    "verification_status": SupplierVerificationStatus.VERIFIED,
                },
                {"business_account_id": 1},
            )
            .to_list(length=len(oids))
        )
        return {str(p["business_account_id"]) for p in profiles}

    # ── RFQ ──────────────────────────────────────────────────────────────

    async def create_rfq(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
        ip: str | None = None,
        hydrate: bool = True,
    ) -> dict[str, Any]:
        """Legacy/generic create. Prefer create_product_rfq / create_sourcing_rfq."""
        buyer_id = self._require_buyer(business)
        items = payload.get("items") or []
        if not items:
            raise ProcurementValidationError("RFQ requires at least one item")
        rfq_type = str(payload.get("rfq_type") or RFQType.SOURCING).lower()
        if rfq_type not in {RFQType.PRODUCT, RFQType.SOURCING}:
            raise ProcurementValidationError("Choose a product quote or a sourcing request")
        now = utc_now()
        number = await self._next_number("RFQ", CollectionName.RFQS, "rfq_number")
        dest = payload.get("destination")
        doc = await self.rfqs.create(
            {
                "rfq_number": number,
                "buyer_business_id": parse_object_id(buyer_id),
                "created_by_user_id": parse_object_id(user_id),
                "rfq_type": rfq_type,
                "title": payload["title"].strip(),
                "description": payload.get("description"),
                "destination": dest.model_dump() if hasattr(dest, "model_dump") else dest,
                "required_by": payload.get("required_by"),
                "response_deadline": payload.get("response_deadline"),
                "currency": payload.get("currency") or "USD",
                "notes": payload.get("notes"),
                "status": RFQStatus.DRAFT,
                "visibility": payload.get("visibility") or RFQVisibility.INVITED,
                "product_id": parse_object_id(payload["product_id"])
                if payload.get("product_id")
                else None,
                "supplier_business_id": parse_object_id(payload["supplier_business_id"])
                if payload.get("supplier_business_id")
                else None,
                "supplier_invites": [],
                "sourcing_request_id": parse_object_id(payload["sourcing_request_id"])
                if payload.get("sourcing_request_id")
                else None,
                "business_plan_id": parse_object_id(payload["business_plan_id"])
                if payload.get("business_plan_id")
                else None,
                "awarded_quotation_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await self._replace_items(doc["_id"], items)
        await self.audit.log(
            action="RFQ_CREATED",
            resource_type="rfq",
            resource_id=doc["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={"rfq_number": number, "rfq_type": rfq_type},
        )
        if not hydrate:
            return {
                "id": str(doc["_id"]),
                "rfq_number": number,
                "status": RFQStatus.DRAFT,
                "supplier_name": None,
            }
        return await self.get_rfq(user_id=user_id, business=business, rfq_id=str(doc["_id"]))

    async def create_product_rfq(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Product RFQ: one listed product → owning supplier only."""
        buyer_id = self._require_buyer(business)
        product_id = str(payload.get("product_id") or "").strip()
        if not product_id:
            raise ProductRFQValidationError("Select a product to request a quote")
        qty_raw = payload.get("quantity")
        try:
            qty = money(qty_raw)
        except Exception as exc:
            raise ProductRFQValidationError("Enter a valid quantity") from exc
        if qty <= 0:
            raise ProductRFQValidationError("Quantity must be greater than zero")

        product = await mongo_manager.collection(CollectionName.PRODUCTS).find_one(
            {"_id": parse_object_id(product_id)}
        )
        if product is None:
            raise ProductRFQValidationError("Product does not exist")
        if str(product.get("status")) != ProductStatus.ACTIVE:
            raise ProductRFQValidationError("Product is not active")
        supplier_id = str(product.get("business_account_id") or product.get("supplier_id") or "")
        if not supplier_id:
            raise ProductRFQValidationError("Product has no owning supplier")
        if supplier_id == buyer_id:
            raise ProductRFQValidationError("You cannot request a quote for your own product")

        # Client must not override supplier — reject mismatch if they try.
        client_supplier = payload.get("supplier_business_id") or payload.get("supplier_id")
        if client_supplier and str(client_supplier) != supplier_id:
            raise ProductRFQValidationError(
                "The supplier must match the product owner and can't be changed"
            )

        supplier = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": parse_object_id(supplier_id)}
        )
        if supplier is None:
            raise ProductRFQValidationError("Supplier business not found")
        if str(supplier.get("status")) == BusinessAccountStatus.SUSPENDED:
            raise ProductRFQValidationError("Supplier is suspended")
        verified = await self._verified_supplier_ids([supplier_id])
        if supplier_id not in verified:
            raise ProductRFQValidationError("Supplier is not verified")

        title = f"{product.get('name') or 'Product'} — quote request"
        catalog = await self._lookup_catalog_unit_price(product_id, qty)
        item = {
            "product_id": product_id,
            "category_id": str(product["category_id"]) if product.get("category_id") else None,
            "product_name": product.get("name") or "Product",
            "sku": product.get("sku"),
            "quantity": str(qty),
            "unit": payload.get("unit") or product.get("unit") or "unit",
            "catalog_unit_price": _money_out(catalog),
            "target_unit_price": payload.get("target_unit_price"),
            "requirements": payload.get("requirements"),
            "notes": payload.get("notes"),
            "supplier_business_id": supplier_id,
        }
        rfq = await self.create_rfq(
            user_id=user_id,
            business=business,
            payload={
                "title": title,
                "description": payload.get("requirements") or payload.get("notes"),
                "destination": payload.get("destination"),
                "required_by": payload.get("required_by"),
                "response_deadline": payload.get("response_deadline"),
                "currency": payload.get("currency") or "USD",
                "notes": payload.get("notes"),
                "visibility": RFQVisibility.INVITED,
                "rfq_type": RFQType.PRODUCT,
                "product_id": product_id,
                "supplier_business_id": supplier_id,
                "items": [item],
            },
            ip=ip,
        )
        if payload.get("publish"):
            rfq = await self.publish_rfq(
                user_id=user_id, business=business, rfq_id=str(rfq["id"]), ip=ip
            )
            try:
                rfq = await self.invite_suppliers(
                    user_id=user_id,
                    business=business,
                    rfq_id=str(rfq["id"]),
                    supplier_business_ids=[supplier_id],
                    ip=ip,
                )
            except Exception:
                # Published even if invite soft-fails (e.g. already invited)
                rfq = await self.get_rfq(user_id=user_id, business=business, rfq_id=str(rfq["id"]))
        return rfq

    async def create_sourcing_rfq(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Sourcing RFQ: requirement-first; no product/supplier lock."""
        buyer_id = self._require_buyer(business)
        title = (payload.get("title") or "").strip()
        if not title:
            raise SourcingRFQValidationError("Add a title for this sourcing request")
        description = (payload.get("description") or "").strip() or None
        requirements = (payload.get("requirements") or "").strip() or None
        if not description and not requirements and not payload.get("items"):
            raise SourcingRFQValidationError(
                "Provide a description, requirements, or at least one item line"
            )
        if payload.get("product_id") or payload.get("supplier_business_id"):
            raise SourcingRFQValidationError(
                "Sourcing requests can't be tied to a specific product or supplier upfront"
            )

        items = payload.get("items")
        if items:
            for it in items:
                data = it.model_dump() if hasattr(it, "model_dump") else dict(it)
                if data.get("product_id") and payload.get("forbid_product_ids"):
                    raise SourcingRFQValidationError("Sourcing line items can't include catalog products")
        else:
            qty_raw = payload.get("quantity")
            try:
                qty = money(qty_raw)
            except Exception as exc:
                raise SourcingRFQValidationError("Enter a valid quantity") from exc
            if qty <= 0:
                raise SourcingRFQValidationError("Quantity must be greater than zero")
            items = [
                {
                    "product_id": None,
                    "category_id": payload.get("category_id"),
                    "product_name": (payload.get("product_name") or title).strip(),
                    "sku": None,
                    "quantity": str(qty),
                    "unit": payload.get("unit") or "unit",
                    "target_unit_price": payload.get("target_unit_price"),
                    "requirements": requirements,
                    "notes": payload.get("notes"),
                }
            ]

        visibility = payload.get("visibility") or RFQVisibility.OPEN
        if visibility not in {RFQVisibility.OPEN, RFQVisibility.INVITED}:
            raise SourcingRFQValidationError("Choose Open or Invite-only visibility")

        rfq = await self.create_rfq(
            user_id=user_id,
            business=business,
            payload={
                "title": title,
                "description": description or requirements,
                "destination": payload.get("destination"),
                "required_by": payload.get("required_by"),
                "response_deadline": payload.get("response_deadline"),
                "currency": payload.get("currency") or "USD",
                "notes": payload.get("notes"),
                "visibility": visibility,
                "rfq_type": RFQType.SOURCING,
                "product_id": None,
                "supplier_business_id": None,
                "items": items,
                "sourcing_request_id": payload.get("sourcing_request_id"),
                "business_plan_id": payload.get("business_plan_id"),
            },
            ip=ip,
        )
        if payload.get("publish"):
            rfq = await self.publish_rfq(
                user_id=user_id, business=business, rfq_id=str(rfq["id"]), ip=ip
            )
        return rfq

    async def _replace_items(self, rfq_id: ObjectId, items: list[Any]) -> None:
        existing = await self.rfq_items.list_for_rfq(rfq_id)
        previous_by_product: dict[str, Any] = {}
        previous_images: dict[str, str] = {}
        for row in existing:
            pid = row.get("product_id")
            if not pid:
                continue
            key = str(pid)
            if row.get("catalog_unit_price") is not None:
                previous_by_product[key] = row["catalog_unit_price"]
            if row.get("primary_image_url"):
                previous_images[key] = str(row["primary_image_url"])
        parsed_items: list[dict[str, Any]] = []
        pids: list[str] = []
        for raw in items:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            pid = str(data["product_id"]) if data.get("product_id") else None
            if pid:
                pids.append(pid)
            parsed_items.append(data)
        catalog_images = await self._primary_image_urls(pids)
        catalog_owners = await self._product_owners(
            [{"product_id": parse_object_id(pid)} for pid in pids]
        )
        await self.rfq_items.delete_for_rfq(rfq_id)
        for idx, data in enumerate(parsed_items):
            try:
                quantity = money(data["quantity"])
            except (ValueError, TypeError) as exc:
                raise ProcurementValidationError("Enter a valid quantity") from exc
            if quantity <= 0:
                raise ProcurementValidationError("Quantity must be greater than zero")
            try:
                target = optional_money(data.get("target_unit_price"))
            except (ValueError, TypeError) as exc:
                raise ProcurementValidationError(
                    "Enter a valid target unit price"
                ) from exc
            try:
                client_catalog = optional_money(data.get("catalog_unit_price"))
            except (ValueError, TypeError) as exc:
                raise ProcurementValidationError(
                    "Enter a valid catalog unit price"
                ) from exc
            pid = str(data["product_id"]) if data.get("product_id") else None
            looked = await self._lookup_catalog_unit_price(pid, quantity) if pid else None
            catalog = freeze_catalog_price(
                previous=previous_by_product.get(pid) if pid else None,
                looked_up=looked,
                client=to_decimal128(client_catalog) if client_catalog is not None else None,
            )
            image_url = None
            if pid:
                image_url = (
                    previous_images.get(pid)
                    or catalog_images.get(pid)
                    or (str(data["primary_image_url"]) if data.get("primary_image_url") else None)
                )
            supplier_id = None
            if data.get("supplier_business_id"):
                supplier_id = parse_object_id(data["supplier_business_id"])
            elif pid and pid in catalog_owners:
                supplier_id = parse_object_id(catalog_owners[pid])
            await self.rfq_items.create(
                {
                    "rfq_id": rfq_id,
                    "product_id": parse_object_id(data["product_id"]) if data.get("product_id") else None,
                    "category_id": parse_object_id(data["category_id"])
                    if data.get("category_id")
                    else None,
                    "supplier_business_id": supplier_id,
                    "product_name": data["product_name"],
                    "sku": data.get("sku"),
                    "quantity": to_decimal128(quantity),
                    "unit": data.get("unit") or "unit",
                    "catalog_unit_price": (
                        catalog if catalog is None or hasattr(catalog, "to_decimal") else to_decimal128(catalog)
                    ),
                    "target_unit_price": to_decimal128(target) if target is not None else None,
                    "primary_image_url": image_url,
                    "requirements": data.get("requirements"),
                    "notes": data.get("notes"),
                    "sort_order": idx,
                }
            )

    async def _lookup_catalog_unit_price(
        self, product_id: str | None, quantity: Any
    ) -> Any | None:
        if not product_id:
            return None
        from app.modules.catalog.repository import ProductPriceRepository
        from app.modules.catalog.service import serialize_price

        try:
            qty = int(_dec(quantity))
        except Exception:
            qty = 1
        tiers = [
            serialize_price(row)
            for row in await ProductPriceRepository().list_for_product(product_id)
            if row.get("is_active", True)
        ]
        match = None
        for tier in sorted(tiers, key=lambda r: int(r["min_quantity"]), reverse=True):
            lo = int(tier["min_quantity"])
            hi = tier.get("max_quantity")
            if qty < lo:
                continue
            if hi is not None and qty > int(hi):
                continue
            match = tier
            break
        if match is None and tiers:
            match = min(tiers, key=lambda r: int(r["min_quantity"]))
        if match is None:
            return None
        try:
            return to_decimal128(_dec(match["unit_price"]))
        except Exception:
            return None

    async def update_rfq(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        if not rfq_is_unsent(rfq):
            raise ProcurementValidationError(
                "This request was already sent to suppliers and can no longer be edited"
            )
        if str(rfq.get("rfq_type") or "") == RFQType.PRODUCT:
            # Product RFQs keep product/supplier lock; items may adjust qty/requirements only.
            if payload.get("items") is not None:
                for raw in payload["items"]:
                    data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
                    pid = data.get("product_id")
                    if pid and str(pid) != str(rfq.get("product_id") or ""):
                        raise ProductRFQValidationError(
                            "Cannot change the locked product on a Product RFQ"
                        )
        updates: dict[str, Any] = {"updated_at": utc_now()}
        for key in (
            "title",
            "description",
            "required_by",
            "response_deadline",
            "currency",
            "notes",
            "visibility",
        ):
            if payload.get(key) is not None:
                updates[key] = payload[key]
        if payload.get("destination") is not None:
            dest = payload["destination"]
            updates["destination"] = dest.model_dump() if hasattr(dest, "model_dump") else dest
        await self.rfqs.update(rfq["_id"], updates)
        if payload.get("items") is not None:
            if not payload["items"]:
                raise ProcurementValidationError("RFQ requires at least one item")
            await self._replace_items(rfq["_id"], payload["items"])
        return await self.get_rfq(user_id=user_id, business=business, rfq_id=rfq_id)

    async def _product_owners(self, items: list[dict[str, Any]]) -> dict[str, str]:
        ids = [item["product_id"] for item in items if item.get("product_id")]
        if not ids:
            return {}
        products = (
            await mongo_manager.collection(CollectionName.PRODUCTS)
            .find({"_id": {"$in": ids}}, {"business_account_id": 1})
            .to_list(length=max(len(ids), 1))
        )
        return {
            str(row["_id"]): str(row["business_account_id"])
            for row in products
            if row.get("business_account_id")
        }

    async def send_draft_to_product_owners(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Publish a draft and invite only the supplier that owns each catalog line.

        Mixed-supplier carts become one RFQ per supplier so nobody sees a
        competitor's products.
        """
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        if not rfq_is_unsent(rfq):
            current = await self.get_rfq(user_id=user_id, business=business, rfq_id=rfq_id)
            sent = (
                []
                if rfq["status"] == RFQStatus.CANCELLED
                else [
                    {
                        "id": current["id"],
                        "rfq_number": current.get("rfq_number"),
                    }
                ]
            )
            return {"rfq": current, "sent": sent}
        items = await self.rfq_items.list_for_rfq(rfq_id)
        if not items:
            raise ProcurementValidationError("Cannot send an RFQ without items")
        owners = await self._product_owners(items)
        groups = group_catalog_items_by_supplier(items, product_owners=owners)
        owned = {sid: rows for sid, rows in groups.items() if sid}
        if not owned:
            if rfq["status"] == RFQStatus.DRAFT:
                published = await self.publish_rfq(
                    user_id=user_id, business=business, rfq_id=rfq_id, ip=ip
                )
            else:
                published = await self.get_rfq(
                    user_id=user_id, business=business, rfq_id=rfq_id
                )
            source_ids = [str(sid) for sid in (rfq.get("source_supplier_ids") or []) if sid]
            if source_ids:
                try:
                    published = await self.invite_suppliers(
                        user_id=user_id,
                        business=business,
                        rfq_id=rfq_id,
                        supplier_business_ids=source_ids,
                        ip=ip,
                    )
                except Exception:
                    published = await self.get_rfq(
                        user_id=user_id, business=business, rfq_id=rfq_id
                    )
            return {
                "rfq": published,
                "sent": [{"id": published["id"], "rfq_number": published.get("rfq_number")}],
            }

        async def _publish_and_invite(target_id: str, supplier_id: str) -> dict[str, Any]:
            target = await self.rfqs.get_by_id(target_id)
            stub = {
                "id": target_id,
                "rfq_number": (target or {}).get("rfq_number"),
                "status": (target or {}).get("status"),
                "supplier_name": None,
            }
            if target and target.get("status") == RFQStatus.DRAFT:
                stub = await self.publish_rfq(
                    user_id=user_id,
                    business=business,
                    rfq_id=target_id,
                    ip=ip,
                    hydrate=False,
                    auto_invite=False,
                )
            try:
                stub = await self.invite_suppliers(
                    user_id=user_id,
                    business=business,
                    rfq_id=target_id,
                    supplier_business_ids=[supplier_id],
                    ip=ip,
                    hydrate=False,
                )
            except Exception:
                pass
            return stub

        if len(owned) == 1:
            supplier_id = next(iter(owned))
            await self.rfqs.update(
                rfq["_id"],
                {
                    "source_supplier_ids": [parse_object_id(supplier_id)],
                    "updated_at": utc_now(),
                },
            )
            published = await _publish_and_invite(rfq_id, supplier_id)
            current = await self.get_rfq(user_id=user_id, business=business, rfq_id=rfq_id)
            return {
                "rfq": current,
                "sent": [
                    {
                        "id": current["id"],
                        "rfq_number": current.get("rfq_number"),
                        "supplier_business_id": supplier_id,
                        "supplier_name": current.get("supplier_name")
                        or await self._business_name(supplier_id),
                        "item_count": len(owned[supplier_id]),
                    }
                ],
            }

        sent: list[dict[str, Any]] = []
        primary: dict[str, Any] | None = None
        for supplier_id, rows in owned.items():
            supplier_name = await self._business_name(supplier_id)
            single = len(rows) == 1 and rows[0].get("product_id")
            payload_items = [_item_doc_to_payload(row) for row in rows]
            created = await self.create_rfq(
                user_id=user_id,
                business=business,
                payload={
                    "title": (
                        f"{rows[0].get('product_name') or 'Product'} — quote request"
                        if single
                        else f"{rfq.get('title') or 'Quote request'} · {supplier_name or 'Supplier'}"
                    ),
                    "description": rfq.get("description"),
                    "notes": rfq.get("notes"),
                    "currency": rfq.get("currency") or "USD",
                    "destination": rfq.get("destination"),
                    "required_by": rfq.get("required_by"),
                    "response_deadline": rfq.get("response_deadline"),
                    "visibility": RFQVisibility.INVITED,
                    "rfq_type": RFQType.PRODUCT if single else RFQType.SOURCING,
                    "product_id": str(rows[0]["product_id"]) if single else None,
                    "supplier_business_id": supplier_id if single else None,
                    "items": payload_items,
                },
                ip=ip,
                hydrate=False,
            )
            created_id = str(created["id"])
            await self.rfqs.update(
                parse_object_id(created_id),
                {
                    "source": rfq.get("source") or "cart",
                    "source_supplier_ids": [parse_object_id(supplier_id)],
                    "updated_at": utc_now(),
                },
            )
            published = await _publish_and_invite(created_id, supplier_id)
            if primary is None:
                primary = published
            sent.append(
                {
                    "id": published["id"],
                    "rfq_number": published.get("rfq_number"),
                    "supplier_business_id": supplier_id,
                    "supplier_name": supplier_name,
                    "item_count": len(rows),
                }
            )

        await self.rfqs.update(
            rfq["_id"],
            {"status": RFQStatus.CANCELLED, "updated_at": utc_now()},
        )
        primary_id = str((primary or sent[0])["id"])
        return {
            "rfq": await self.get_rfq(user_id=user_id, business=business, rfq_id=primary_id),
            "sent": sent,
        }

    async def publish_rfq(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        ip: str | None = None,
        hydrate: bool = True,
        auto_invite: bool = True,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        assert_transition(RFQ_TRANSITIONS, rfq["status"], RFQStatus.PUBLISHED)
        items = await self.rfq_items.list_for_rfq(rfq_id)
        if not items:
            raise ProcurementValidationError("Cannot publish an RFQ without items")
        await self.rfqs.update(
            rfq["_id"],
            {"status": RFQStatus.PUBLISHED, "updated_at": utc_now()},
        )
        await self.audit.log(
            action="RFQ_PUBLISHED",
            resource_type="rfq",
            resource_id=rfq["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
        )
        await event_bus.publish(
            DomainEvent(name=RFQ_PUBLISHED, payload={"rfq_id": rfq_id, "buyer_business_id": buyer_id})
        )
        # Product RFQ: auto-invite the locked supplier after publish.
        if (
            auto_invite
            and str(rfq.get("rfq_type") or "") == RFQType.PRODUCT
            and rfq.get("supplier_business_id")
        ):
            try:
                return await self.invite_suppliers(
                    user_id=user_id,
                    business=business,
                    rfq_id=rfq_id,
                    supplier_business_ids=[str(rfq["supplier_business_id"])],
                    ip=ip,
                    hydrate=hydrate,
                )
            except Exception:
                pass
        if not hydrate:
            return {
                "id": rfq_id,
                "rfq_number": rfq.get("rfq_number"),
                "status": RFQStatus.PUBLISHED,
                "supplier_name": None,
            }
        return await self.get_rfq(user_id=user_id, business=business, rfq_id=rfq_id)

    async def invite_suppliers(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        supplier_business_ids: list[str],
        ip: str | None = None,
        hydrate: bool = True,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        if rfq["status"] not in {RFQStatus.PUBLISHED, RFQStatus.RESPONDING, RFQStatus.NEGOTIATING}:
            raise ProcurementValidationError("Publish this RFQ before inviting suppliers")
        if str(rfq.get("rfq_type") or "") == RFQType.PRODUCT:
            locked = str(rfq.get("supplier_business_id") or "")
            if not locked:
                raise ProductRFQValidationError("Product RFQ is missing target supplier")
            if any(str(sid) != locked for sid in supplier_business_ids):
                raise ProductRFQValidationError(
                    "Product RFQs can only invite the product owner supplier"
                )
            supplier_business_ids = [locked]
        verified = await self._verified_supplier_ids(supplier_business_ids)
        if not verified:
            raise ProcurementValidationError(
                "No verified suppliers in the selection. Unverified suppliers cannot be invited."
            )
        invites = list(rfq.get("supplier_invites") or [])
        existing = {str(i.get("supplier_business_id")) for i in invites}
        now = utc_now()
        added = 0
        for sid in verified:
            if sid in existing:
                continue
            invites.append(
                {
                    "supplier_business_id": parse_object_id(sid),
                    "invited_by_user_id": parse_object_id(user_id),
                    "invited_at": now,
                    "viewed_at": None,
                    "responded_at": None,
                    "declined_at": None,
                    "decline_reason": None,
                    "status": SupplierInviteStatus.INVITED,
                }
            )
            added += 1
            await notify(
                recipient_business_id=sid,
                type="RFQ_INVITATION",
                title=f"Quote request: {rfq.get('rfq_number')}",
                message=(
                    f"A buyer requested a quotation on {rfq.get('title')}. "
                    "Only your products are included. Message the buyer to negotiate, "
                    "then submit your quotation."
                ),
                reference_type="rfq",
                reference_id=rfq["_id"],
            )
        if added == 0:
            raise ProcurementConflictError("All selected verified suppliers were already invited")
        await self.rfqs.update(
            rfq["_id"],
            {
                "supplier_invites": invites,
                "visibility": RFQVisibility.INVITED,
                "updated_at": now,
            },
        )
        await self.audit.log(
            action="RFQ_SUPPLIERS_INVITED",
            resource_type="rfq",
            resource_id=rfq["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={"added": added},
        )
        if not hydrate:
            return {
                "id": rfq_id,
                "rfq_number": rfq.get("rfq_number"),
                "status": rfq.get("status"),
                "supplier_name": None,
            }
        return await self.get_rfq(user_id=user_id, business=business, rfq_id=rfq_id)

    async def list_eligible_suppliers(
        self, *, business: dict[str, Any] | None, rfq_id: str, limit: int = 40
    ) -> list[dict[str, Any]]:
        buyer_id = self._require_buyer(business)
        await self._get_buyer_rfq(rfq_id, buyer_id)
        items = await self.rfq_items.list_for_rfq(rfq_id)
        product_ids = [i["product_id"] for i in items if i.get("product_id")]
        owners = await self._product_owners(items)
        supplier_ids: set[ObjectId] = set()
        for item in items:
            sid = item.get("supplier_business_id")
            if sid:
                supplier_ids.add(sid if isinstance(sid, ObjectId) else parse_object_id(str(sid)))
            elif item.get("product_id"):
                owner = owners.get(str(item["product_id"]))
                if owner:
                    supplier_ids.add(parse_object_id(owner))
        if product_ids:
            products = (
                await mongo_manager.collection(CollectionName.PRODUCTS)
                .find({"_id": {"$in": product_ids}}, {"business_account_id": 1})
                .to_list(length=200)
            )
            for p in products:
                if p.get("business_account_id"):
                    supplier_ids.add(p["business_account_id"])

        profiles = (
            await mongo_manager.collection(CollectionName.SUPPLIER_PROFILES)
            .find({})
            .limit(400)
            .to_list(length=400)
        )
        profile_map = {p["business_account_id"]: p for p in profiles if p.get("business_account_id")}
        verified_ids = {
            bid
            for bid, p in profile_map.items()
            if str(p.get("verification_status")) == SupplierVerificationStatus.VERIFIED
        }

        # Catalog RFQs: always seat product owners (even if not currently verified).
        # Open sourcing with no lines: fall back to verified suppliers.
        if supplier_ids:
            candidate_ids = list(supplier_ids)[:limit]
        else:
            candidate_ids = list(verified_ids)[:limit]

        businesses = (
            await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS)
            .find({"_id": {"$in": candidate_ids}})
            .to_list(length=limit)
        )
        products_by_supplier: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            sid = str(item.get("supplier_business_id") or "") or owners.get(
                str(item["product_id"]) if item.get("product_id") else ""
            )
            if not sid:
                continue
            products_by_supplier.setdefault(sid, []).append(
                {
                    "product_id": _oid(item.get("product_id")),
                    "product_name": item.get("product_name"),
                    "sku": item.get("sku"),
                    "quantity": _money_out(item.get("quantity")),
                    "unit": item.get("unit") or "unit",
                }
            )
        return [
            {
                "supplier_business_id": str(b["_id"]),
                "name": b.get("name"),
                "verified": b["_id"] in verified_ids,
                "can_invite": b["_id"] in verified_ids,
                "verification_status": (
                    str(profile_map[b["_id"]].get("verification_status"))
                    if b["_id"] in profile_map
                    else None
                ),
                "product_match": b["_id"] in supplier_ids,
                "products": products_by_supplier.get(str(b["_id"]), []),
            }
            for b in businesses
        ]

    async def supplier_view_rfq(
        self, *, user_id: str, business: dict[str, Any] | None, rfq_id: str
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        rfq = await self.rfqs.get_by_id(rfq_id)
        if rfq is None:
            raise RFQNotFoundError()
        invites = list(rfq.get("supplier_invites") or [])
        invite = next(
            (i for i in invites if str(i.get("supplier_business_id")) == supplier_id),
            None,
        )
        if invite is None and rfq.get("visibility") != RFQVisibility.OPEN:
            raise ProcurementForbiddenError()
        if invite and invite.get("status") == SupplierInviteStatus.INVITED:
            for i in invites:
                if str(i.get("supplier_business_id")) == supplier_id:
                    i["status"] = SupplierInviteStatus.VIEWED
                    i["viewed_at"] = utc_now()
            await self.rfqs.update(rfq["_id"], {"supplier_invites": invites, "updated_at": utc_now()})
        return await self._serialize_rfq(rfq, include_quotes_for=supplier_id)

    async def respond_invite(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        accept: bool,
        reason: str | None = None,
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        rfq = await self.rfqs.get_by_id(rfq_id)
        if rfq is None:
            raise RFQNotFoundError()
        invites = list(rfq.get("supplier_invites") or [])
        found = False
        now = utc_now()
        for i in invites:
            if str(i.get("supplier_business_id")) != supplier_id:
                continue
            found = True
            i["responded_at"] = now
            if accept:
                i["status"] = SupplierInviteStatus.ACCEPTED
            else:
                i["status"] = SupplierInviteStatus.DECLINED
                i["declined_at"] = now
                i["decline_reason"] = reason
        if not found:
            raise ProcurementForbiddenError("You were not invited to this RFQ")
        await self.rfqs.update(rfq["_id"], {"supplier_invites": invites, "updated_at": now})
        await notify(
            recipient_business_id=rfq["buyer_business_id"],
            type="RFQ_INVITE_RESPONSE",
            title=f"Supplier {'accepted' if accept else 'declined'} RFQ {rfq.get('rfq_number')}",
            message=(
                f"A supplier accepted the invitation to quote on {rfq.get('title')}."
                if accept
                else (
                    f"A supplier declined to quote on {rfq.get('title')}."
                    + (f" Reason: {reason.strip()}" if reason and reason.strip() else "")
                )
            ),
            reference_type="rfq",
            reference_id=rfq["_id"],
        )
        return await self.supplier_view_rfq(user_id=user_id, business=business, rfq_id=rfq_id)

    async def list_rfqs(
        self,
        *,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        rfq_type: str | None = None,
        as_supplier: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        if as_supplier:
            sid = self._require_supplier(business)
            rows = await self.rfqs.list_invited_for_supplier(
                sid, skip=(page - 1) * page_size, limit=page_size
            )
            total = await self.rfqs.count(
                {"supplier_invites.supplier_business_id": parse_object_id(sid)}
            )
        else:
            bid = self._require_buyer(business)
            rows = await self.rfqs.list_for_buyer(
                bid,
                skip=(page - 1) * page_size,
                limit=page_size,
                status=status,
                rfq_type=rfq_type,
            )
            total = await self.rfqs.count_for_buyer(bid, status=status, rfq_type=rfq_type)
        return [await self._serialize_rfq_summary(r) for r in rows], total

    async def get_rfq(
        self, *, user_id: str, business: dict[str, Any] | None, rfq_id: str
    ) -> dict[str, Any]:
        if business and str(business.get("type")) == BusinessAccountType.PLATFORM:
            rfq = await self.rfqs.get_by_id(rfq_id)
            if rfq is None:
                raise RFQNotFoundError()
            return await self._serialize_rfq(rfq)
        if business and str(business.get("type")) == BusinessAccountType.SUPPLIER:
            return await self.supplier_view_rfq(user_id=user_id, business=business, rfq_id=rfq_id)
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        return await self._serialize_rfq(rfq)

    async def _get_buyer_rfq(self, rfq_id: str, buyer_id: str) -> dict[str, Any]:
        rfq = await self.rfqs.get_by_id(rfq_id)
        if rfq is None:
            raise RFQNotFoundError()
        if str(rfq.get("buyer_business_id")) != buyer_id:
            raise ProcurementForbiddenError()
        return rfq

    # ── Quotations ───────────────────────────────────────────────────────

    async def upsert_quotation(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        payload: dict[str, Any],
        submit: bool = False,
        allow_revision: bool = False,
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        verified = await self._verified_supplier_ids([supplier_id])
        if supplier_id not in verified:
            raise ProcurementForbiddenError("Only verified suppliers can submit quotations")
        rfq = await self.rfqs.get_by_id(rfq_id)
        if rfq is None:
            raise RFQNotFoundError()
        if rfq["status"] not in {
            RFQStatus.PUBLISHED,
            RFQStatus.RESPONDING,
            RFQStatus.NEGOTIATING,
        }:
            raise ProcurementValidationError("RFQ is not open for quotations")
        rfq_type = str(rfq.get("rfq_type") or RFQType.SOURCING).lower()
        if rfq_type == RFQType.PRODUCT:
            target = str(rfq.get("supplier_business_id") or "")
            if not target:
                raise ProcurementValidationError("Product RFQ is missing target supplier")
            if supplier_id != target:
                raise ProcurementForbiddenError(
                    "Only the product owner supplier can quote on this Product RFQ"
                )
        invites = rfq.get("supplier_invites") or []
        invited = any(str(i.get("supplier_business_id")) == supplier_id for i in invites)
        if rfq.get("visibility") == RFQVisibility.INVITED and not invited:
            raise ProcurementForbiddenError("You were not invited to this RFQ")

        rfq_items = {str(i["_id"]): i for i in await self.rfq_items.list_for_rfq(rfq_id)}
        owners = await self._product_owners(list(rfq_items.values()))
        line_inputs = []
        for raw in payload["lines"]:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            if data["rfq_item_id"] not in rfq_items:
                raise ProcurementValidationError("Quotation line must reference an RFQ item")
            rfq_item = rfq_items[data["rfq_item_id"]]
            owner = str(rfq_item.get("supplier_business_id") or "") or owners.get(
                str(rfq_item["product_id"]) if rfq_item.get("product_id") else ""
            )
            if rfq_item.get("product_id") and owner and owner != supplier_id:
                raise ProcurementForbiddenError("You can only quote your own products on this RFQ")
            line_inputs.append((data, rfq_item))

        computed_lines = []
        for data, rfq_item in line_inputs:
            computed_lines.append(
                (
                    data,
                    rfq_item,
                    compute_line(
                        quantity=data["quantity"],
                        unit_price=data["unit_price"],
                        discount=data.get("discount") or "0",
                        tax=data.get("tax") or "0",
                        shipping=data.get("shipping_allocation") or "0",
                    ),
                )
            )
        totals = compute_document_totals(
            [c[2] for c in computed_lines],
            document_discount=payload.get("document_discount") or "0",
            document_shipping=payload.get("document_shipping") or "0",
            document_tax=payload.get("document_tax") or "0",
        )

        existing = await self.quotations.get_for_rfq_supplier(rfq_id, supplier_id)
        now = utc_now()
        if existing is None:
            number = await self._next_number("QT", CollectionName.QUOTATIONS, "quotation_number")
            version = 1
            status = QuotationStatus.SUBMITTED if submit else QuotationStatus.DRAFT
            quote = await self.quotations.create(
                {
                    "quotation_number": number,
                    "rfq_id": parse_object_id(rfq_id),
                    "supplier_id": parse_object_id(supplier_id),
                    "buyer_business_id": rfq["buyer_business_id"],
                    "created_by_user_id": parse_object_id(user_id),
                    "status": status,
                    "valid_until": payload.get("valid_until"),
                    "payment_terms": payload.get("payment_terms"),
                    "delivery_terms": payload.get("delivery_terms"),
                    "currency": payload.get("currency") or rfq.get("currency") or "USD",
                    "subtotal": to_decimal128(totals.subtotal),
                    "discount_total": to_decimal128(totals.discount_total),
                    "charge_total": to_decimal128(totals.charge_total),
                    "tax_total": to_decimal128(totals.tax_total),
                    "total": to_decimal128(totals.total),
                    "notes": payload.get("notes"),
                    "current_version": version,
                    "submitted_at": now if submit else None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        else:
            locked = quotation_cannot_be_edited(
                str(existing.get("status") or ""),
                allow_revision=allow_revision,
            )
            if locked:
                raise ProcurementValidationError(locked)
            version = int(existing.get("current_version") or 1)
            if (
                existing["status"]
                in {QuotationStatus.SUBMITTED, QuotationStatus.NEGOTIATING, QuotationStatus.REJECTED}
                and submit
            ):
                version += 1
            status = existing["status"]
            if submit:
                if status in {QuotationStatus.DRAFT, QuotationStatus.REJECTED}:
                    assert_transition(QUOTATION_TRANSITIONS, status, QuotationStatus.SUBMITTED)
                status = QuotationStatus.SUBMITTED
            quote = await self.quotations.update(
                existing["_id"],
                {
                    "status": status,
                    "valid_until": payload.get("valid_until"),
                    "payment_terms": payload.get("payment_terms"),
                    "delivery_terms": payload.get("delivery_terms"),
                    "currency": payload.get("currency") or existing.get("currency") or "USD",
                    "subtotal": to_decimal128(totals.subtotal),
                    "discount_total": to_decimal128(totals.discount_total),
                    "charge_total": to_decimal128(totals.charge_total),
                    "tax_total": to_decimal128(totals.tax_total),
                    "total": to_decimal128(totals.total),
                    "notes": payload.get("notes"),
                    "current_version": version,
                    "submitted_at": now if submit else existing.get("submitted_at"),
                    "updated_at": now,
                },
            )
            assert quote is not None

        for data, rfq_item, line in computed_lines:
            await self.quotation_items.create(
                {
                    "quotation_id": quote["_id"],
                    "rfq_item_id": parse_object_id(data["rfq_item_id"]),
                    "version": version,
                    "product_id": rfq_item.get("product_id"),
                    "product_name_snapshot": rfq_item.get("product_name"),
                    "sku_snapshot": rfq_item.get("sku"),
                    "quantity": to_decimal128(line.quantity),
                    "unit": rfq_item.get("unit") or "unit",
                    "unit_price": to_decimal128(line.unit_price),
                    "moq": data.get("moq"),
                    "lead_time_days": data.get("lead_time_days"),
                    "discount": to_decimal128(line.discount),
                    "tax": to_decimal128(line.tax),
                    "shipping_allocation": to_decimal128(line.shipping),
                    "line_total": to_decimal128(line.line_total),
                    "notes": data.get("notes"),
                }
            )

        if submit:
            invites = list(rfq.get("supplier_invites") or [])
            invite_changed = False
            for invite in invites:
                if str(invite.get("supplier_business_id")) != supplier_id:
                    continue
                if invite.get("status") in {
                    SupplierInviteStatus.INVITED,
                    SupplierInviteStatus.VIEWED,
                }:
                    invite["status"] = SupplierInviteStatus.ACCEPTED
                    invite["responded_at"] = now
                    invite_changed = True
            if invite_changed:
                await self.rfqs.update(
                    rfq["_id"],
                    {"supplier_invites": invites, "updated_at": now},
                )

        if submit and rfq["status"] == RFQStatus.PUBLISHED:
            await self.rfqs.update(
                rfq["_id"],
                {"status": RFQStatus.RESPONDING, "updated_at": now},
            )
        if submit:
            await notify(
                recipient_business_id=rfq["buyer_business_id"],
                type="QUOTE_RECEIVED",
                title=f"Quotation received for {rfq.get('rfq_number')}",
                message=f"A supplier submitted quotation {quote.get('quotation_number')} for {rfq.get('title')}.",
                reference_type="rfq",
                reference_id=rfq["_id"],
            )
            from app.modules.communication.constants import SystemEvent
            from app.modules.communication.timeline import post_thread_system_event

            await post_thread_system_event(
                context_type="rfq",
                context_id=rfq["_id"],
                system_event=SystemEvent.QUOTE_RECEIVED,
                body=f"Quotation {quote.get('quotation_number')} received",
                initiator_business_id=rfq["buyer_business_id"],
                counterparty_business_id=supplier_id,
                subject=f"RFQ {rfq.get('rfq_number')}",
            )
            await self.audit.log(
                action="QUOTATION_SUBMITTED",
                resource_type="quotation",
                resource_id=quote["_id"],
                business_account_id=supplier_id,
                user_id=user_id,
                actor_id=user_id,
                metadata={"rfq_id": rfq_id, "version": version},
            )
        return await self.get_quotation(user_id=user_id, business=business, quotation_id=str(quote["_id"]))

    async def get_quotation(
        self, *, user_id: str, business: dict[str, Any] | None, quotation_id: str
    ) -> dict[str, Any]:
        quote = await self.quotations.get_by_id(quotation_id)
        if quote is None:
            raise QuotationNotFoundError()
        self._assert_quote_access(quote, business)
        return await self._serialize_quotation(quote)

    async def withdraw_quotation(
        self, *, user_id: str, business: dict[str, Any] | None, quotation_id: str
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        quote = await self.quotations.get_by_id(quotation_id)
        if quote is None:
            raise QuotationNotFoundError()
        if str(quote.get("supplier_id")) != supplier_id:
            raise ProcurementForbiddenError()
        assert_transition(QUOTATION_TRANSITIONS, quote["status"], QuotationStatus.WITHDRAWN)
        await self.quotations.update(
            quote["_id"],
            {"status": QuotationStatus.WITHDRAWN, "updated_at": utc_now()},
        )
        rfq = await self.rfqs.get_by_id(quote.get("rfq_id"))
        try:
            await notify(
                recipient_business_id=quote.get("buyer_business_id") or (rfq or {}).get("buyer_business_id"),
                type="QUOTATION_WITHDRAWN",
                title=f"Quotation withdrawn — {quote.get('quotation_number')}",
                message="The supplier withdrew this quotation. Review remaining quotes on the RFQ.",
                reference_type="rfq",
                reference_id=quote.get("rfq_id"),
            )
        except Exception:
            pass
        return await self.get_quotation(user_id=user_id, business=business, quotation_id=quotation_id)

    async def reject_quotation(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        quotation_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        quote = await self.quotations.get_by_id(quotation_id)
        if quote is None:
            raise QuotationNotFoundError()
        if str(quote.get("buyer_business_id")) != buyer_id:
            raise ProcurementForbiddenError()
        assert_transition(QUOTATION_TRANSITIONS, quote["status"], QuotationStatus.REJECTED)
        note = (reason or "").strip() or None
        await self.quotations.update(
            quote["_id"],
            {
                "status": QuotationStatus.REJECTED,
                "rejection_reason": note,
                "updated_at": utc_now(),
            },
        )
        rfq_id = quote.get("rfq_id")
        try:
            await notify(
                recipient_business_id=quote.get("supplier_id"),
                type="QUOTE_REJECTED",
                title=f"Quotation declined — {quote.get('quotation_number')}",
                message=note
                or f"The buyer declined quotation {quote.get('quotation_number')}.",
                reference_type="rfq",
                reference_id=rfq_id,
                cta_path=f"/procurement/rfqs/{rfq_id}" if rfq_id else None,
            )
        except Exception:
            pass
        return await self.get_quotation(
            user_id=user_id, business=business, quotation_id=quotation_id
        )

    async def comparison(
        self, *, business: dict[str, Any] | None, rfq_id: str
    ) -> dict[str, Any]:
        if business and str(business.get("type")) == BusinessAccountType.PLATFORM:
            rfq = await self.rfqs.get_by_id(rfq_id)
            if rfq is None:
                raise RFQNotFoundError()
        else:
            buyer_id = self._require_buyer(business)
            rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        quotes = [
            q
            for q in await self.quotations.list_for_rfq(rfq_id)
            if q.get("status") in {QuotationStatus.SUBMITTED, QuotationStatus.NEGOTIATING, QuotationStatus.ACCEPTED}
        ]
        items = await self.rfq_items.list_for_rfq(rfq_id)
        columns = []
        for q in quotes:
            lines = await self.quotation_items.list_for_quotation(
                q["_id"], version=int(q.get("current_version") or 1)
            )
            columns.append(
                {
                    "quotation": await self._serialize_quotation_summary(q),
                    "lines": [self._serialize_quote_line(ln) for ln in lines],
                }
            )
        return {
            "rfq": await self._serialize_rfq_summary(rfq),
            "rfq_items": [self._serialize_rfq_item(i) for i in items],
            "quotations": columns,
        }

    async def handshake(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        quotation_id: str,
        confirm: bool,
        ip: str | None = None,
    ) -> dict[str, Any]:
        """OK the deal: lock the quotation and prepare a draft purchase order."""
        if not confirm:
            raise ProcurementValidationError("Confirm you want to lock in this deal")
        return await self._close_deal(
            user_id=user_id,
            business=business,
            rfq_id=rfq_id,
            quotation_id=quotation_id,
            order_status=OrderStatus.DRAFT,
            ip=ip,
        )

    async def award(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        quotation_id: str,
        confirm: bool,
        ip: str | None = None,
    ) -> dict[str, Any]:
        if not confirm:
            raise ProcurementValidationError("Confirm you want to award this quotation")
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        existing = await self.orders.find_one(
            {"rfq_id": rfq["_id"], "quotation_id": parse_object_id(quotation_id)}
        )
        if existing and existing.get("status") == OrderStatus.DRAFT:
            return await self.issue_order(
                user_id=user_id,
                business=business,
                order_id=str(existing["_id"]),
                ip=ip,
            )
        if existing and existing.get("status") != OrderStatus.CANCELLED:
            return await self.get_order(
                user_id=user_id, business=business, order_id=str(existing["_id"])
            )
        return await self._close_deal(
            user_id=user_id,
            business=business,
            rfq_id=rfq_id,
            quotation_id=quotation_id,
            order_status=OrderStatus.PENDING,
            ip=ip,
        )

    async def issue_order(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        order_id: str,
        payment_method: str | None = None,
        payment_terms: str | None = None,
        delivery_terms: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Promote a draft handshake PO to a live purchase order."""
        buyer_id = self._require_buyer(business)
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError()
        if str(order.get("buyer_business_id")) != buyer_id:
            raise ProcurementForbiddenError()
        assert_transition(ORDER_TRANSITIONS, order["status"], OrderStatus.PENDING)

        now = utc_now()
        history = list(order.get("status_history") or [])
        history.append(
            {
                "status": OrderStatus.PENDING,
                "changed_by_user_id": parse_object_id(user_id),
                "note": "Draft purchase order issued to supplier",
                "changed_at": now,
            }
        )
        updates: dict[str, Any] = {
            "status": OrderStatus.PENDING,
            "status_history": history,
            "updated_at": now,
        }
        if payment_method is not None:
            method = payment_method.strip()
            if method:
                updates["payment_method"] = method
        if payment_terms is not None:
            terms = payment_terms.strip()
            if terms:
                updates["payment_terms"] = terms
        if delivery_terms is not None:
            delivery = delivery_terms.strip()
            if delivery:
                updates["delivery_terms"] = delivery
        if not updates.get("payment_method") and not order.get("payment_method"):
            raise ProcurementValidationError("Payment method is required to issue the purchase order.")

        await self.orders.update(order["_id"], updates)
        order_number = order.get("order_number")
        await self.audit.log(
            action="PURCHASE_ORDER_ISSUED",
            resource_type="order",
            resource_id=order["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={
                "quotation_id": str(order.get("quotation_id")),
                "rfq_id": str(order.get("rfq_id")),
                "payment_method": updates.get("payment_method") or order.get("payment_method"),
            },
        )
        await notify(
            recipient_business_id=order["supplier_business_id"],
            type="QUOTATION_ACCEPTED",
            title=f"Purchase order issued — {order_number}",
            message="The buyer issued the purchase order from the agreed quotation. Please acknowledge.",
            reference_type="order",
            reference_id=order["_id"],
        )
        await event_bus.publish(
            DomainEvent(name=ORDER_CREATED, payload={"order_id": str(order["_id"])})
        )
        return await self.get_order(user_id=user_id, business=business, order_id=order_id)

    async def _close_deal(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        rfq_id: str,
        quotation_id: str,
        order_status: str,
        ip: str | None = None,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        rfq = await self._get_buyer_rfq(rfq_id, buyer_id)
        if rfq["status"] not in {
            RFQStatus.PUBLISHED,
            RFQStatus.RESPONDING,
            RFQStatus.NEGOTIATING,
        }:
            raise ProcurementValidationError("RFQ is not eligible for award")
        quote = await self.quotations.get_by_id(quotation_id)
        if quote is None or str(quote.get("rfq_id")) != rfq_id:
            raise QuotationNotFoundError()
        if quote["status"] not in {QuotationStatus.SUBMITTED, QuotationStatus.NEGOTIATING}:
            if quote["status"] == QuotationStatus.ACCEPTED:
                existing = await self.orders.find_one(
                    {"rfq_id": rfq["_id"], "quotation_id": quote["_id"]}
                )
                if existing:
                    return await self.get_order(
                        user_id=user_id, business=business, order_id=str(existing["_id"])
                    )
            raise ProcurementValidationError("Quotation is not eligible for award")

        existing = await self.orders.find_one({"rfq_id": rfq["_id"]})
        if existing and existing.get("status") != OrderStatus.CANCELLED:
            return await self.get_order(
                user_id=user_id, business=business, order_id=str(existing["_id"])
            )

        async def _work(session):
            return await self._award_tx(
                session=session,
                user_id=user_id,
                buyer_id=buyer_id,
                rfq=rfq,
                quote=quote,
                order_status=order_status,
                ip=ip,
            )

        order_id = await run_in_transaction(_work)
        others = await self.quotations.list_for_rfq(rfq_id)
        for other in others:
            if str(other["_id"]) == quotation_id:
                continue
            if other.get("status") == QuotationStatus.REJECTED:
                try:
                    await notify(
                        recipient_business_id=other["supplier_id"],
                        type="QUOTATION_REJECTED",
                        title=f"Quotation not selected — {rfq.get('rfq_number')}",
                        message="The buyer awarded this RFQ to another supplier.",
                        reference_type="rfq",
                        reference_id=rfq["_id"],
                    )
                except Exception:
                    pass
        return await self.get_order(user_id=user_id, business=business, order_id=order_id)

    async def _award_tx(
        self,
        *,
        session,
        user_id: str,
        buyer_id: str,
        rfq: dict[str, Any],
        quote: dict[str, Any],
        order_status: str = OrderStatus.PENDING,
        ip: str | None,
    ) -> str:
        now = utc_now()
        claimed = await self.rfqs.collection.find_one_and_update(
            {
                "_id": rfq["_id"],
                "status": {
                    "$in": [
                        RFQStatus.PUBLISHED,
                        RFQStatus.RESPONDING,
                        RFQStatus.NEGOTIATING,
                    ]
                },
            },
            {
                "$set": {
                    "status": RFQStatus.AWARDED,
                    "awarded_quotation_id": quote["_id"],
                    "updated_at": now,
                }
            },
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if claimed is None:
            raise ProcurementConflictError("RFQ was already awarded or is no longer eligible")

        version = int(quote.get("current_version") or 1)
        lines = await self.quotation_items.list_for_quotation(quote["_id"], version=version)
        if not lines:
            raise ProcurementValidationError("Quotation has no line items")

        others = await self.quotations.list_for_rfq(str(rfq["_id"]))
        for other in others:
            if str(other["_id"]) == str(quote["_id"]):
                continue
            if other.get("status") in {
                QuotationStatus.SUBMITTED,
                QuotationStatus.NEGOTIATING,
                QuotationStatus.DRAFT,
            }:
                await self.quotations.update(
                    other["_id"],
                    {"status": QuotationStatus.REJECTED, "updated_at": now},
                    session=session,
                )

        await self.quotations.update(
            quote["_id"],
            {"status": QuotationStatus.ACCEPTED, "updated_at": now},
            session=session,
        )

        order_number = await self._next_number("PO", CollectionName.ORDERS, "order_number")
        draft_note = (
            f"Draft PO prepared from {quote.get('quotation_number')}"
            if order_status == OrderStatus.DRAFT
            else "Created from awarded quotation"
        )
        active_tax = await _active_tax_settings()
        tax_name = (active_tax or {}).get("name") or "VAT"
        tax_rate = (active_tax or {}).get("rate")
        # Prefer platform VAT when configured; otherwise keep quotation tax totals.
        money_row = _compose_order_money(
            subtotal=quote.get("subtotal"),
            discount_total=quote.get("discount_total"),
            charge_total=quote.get("charge_total"),
            tax_rate=tax_rate,
            existing_tax_total=quote.get("tax_total"),
        )
        order = await self.orders.create(
            {
                "order_number": order_number,
                "buyer_business_id": parse_object_id(buyer_id),
                "supplier_business_id": quote["supplier_id"],
                "rfq_id": rfq["_id"],
                "quotation_id": quote["_id"],
                "status": order_status,
                "currency": quote.get("currency") or "USD",
                "subtotal": to_decimal128(money_row["subtotal"]),
                "discount_total": to_decimal128(money_row["discount_total"]),
                "charge_total": to_decimal128(money_row["charge_total"]),
                "tax_total": to_decimal128(money_row["tax_total"]),
                "total": to_decimal128(money_row["total"]),
                "tax_rate_snapshot": to_decimal128(money_row["tax_rate_snapshot"])
                if money_row["tax_rate_snapshot"] is not None
                else None,
                "tax_name_snapshot": tax_name if money_row["tax_rate_snapshot"] is not None else None,
                "shipping_address": rfq.get("destination"),
                "billing_address": None,
                "payment_terms": quote.get("payment_terms"),
                "payment_method": None,
                "delivery_terms": quote.get("delivery_terms"),
                "payment_status": "unpaid",
                "stock_reservation_status": "pending",
                "status_history": [
                    {
                        "status": order_status,
                        "changed_by_user_id": parse_object_id(user_id),
                        "note": draft_note,
                        "changed_at": now,
                    }
                ],
                "rejection_reason": None,
                "confirmed_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "created_at": now,
                "updated_at": now,
            },
            session=session,
        )
        for ln in lines:
            await self.order_items.create(
                {
                    "order_id": order["_id"],
                    "quotation_item_id": ln["_id"],
                    "rfq_item_id": ln.get("rfq_item_id"),
                    "product_id": ln.get("product_id"),
                    "product_name_snapshot": ln.get("product_name_snapshot") or "Item",
                    "sku_snapshot": ln.get("sku_snapshot"),
                    "quantity": ln["quantity"],
                    "unit": ln.get("unit") or "unit",
                    "unit_price": ln["unit_price"],
                    "discount_snapshot": ln.get("discount") or to_decimal128(Decimal("0")),
                    "tax_snapshot": ln.get("tax") or to_decimal128(Decimal("0")),
                    "subtotal": to_decimal128(quantize(_dec(ln["quantity"]) * _dec(ln["unit_price"]))),
                    "line_total": ln["line_total"],
                    "shipped_quantity": to_decimal128(Decimal("0")),
                    "received_quantity": to_decimal128(Decimal("0")),
                    "damaged_quantity": to_decimal128(Decimal("0")),
                    "missing_quantity": to_decimal128(Decimal("0")),
                    "rejected_quantity": to_decimal128(Decimal("0")),
                },
                session=session,
            )

        await self.audit.log(
            action="QUOTATION_HANDSHAKE" if order_status == OrderStatus.DRAFT else "QUOTATION_AWARDED",
            resource_type="quotation",
            resource_id=quote["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={
                "order_id": str(order["_id"]),
                "rfq_id": str(rfq["_id"]),
                "order_status": order_status,
                "quotation_number": quote.get("quotation_number"),
            },
        )
        if order_status == OrderStatus.DRAFT:
            await notify(
                recipient_business_id=quote["supplier_id"],
                type="QUOTATION_ACCEPTED",
                title=f"Deal agreed — draft PO {order_number}",
                message=(
                    f"The buyer locked quotation {quote.get('quotation_number')}. "
                    "A draft purchase order is ready for issue."
                ),
                reference_type="order",
                reference_id=order["_id"],
            )
        else:
            await notify(
                recipient_business_id=quote["supplier_id"],
                type="QUOTATION_ACCEPTED",
                title=f"Quotation awarded — PO {order_number}",
                message="The buyer accepted your quotation and issued a purchase order.",
                reference_type="order",
                reference_id=order["_id"],
            )
            await event_bus.publish(
                DomainEvent(
                    name=QUOTATION_ACCEPTED,
                    payload={"quotation_id": str(quote["_id"]), "order_id": str(order["_id"])},
                )
            )
            await event_bus.publish(
                DomainEvent(name=ORDER_CREATED, payload={"order_id": str(order["_id"])})
            )
        return str(order["_id"])

    async def create_direct_order_from_cart_lines(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        supplier_business_id: str,
        currency: str,
        lines: list[dict[str, Any]],
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Create a purchase order directly from cart lines (no RFQ/quotation)."""
        buyer_id = self._require_buyer(business)
        if not lines:
            raise ProcurementValidationError("Order requires at least one line")
        now = utc_now()
        zero = to_decimal128(Decimal("0"))
        built: list[dict[str, Any]] = []
        subtotal = Decimal("0")
        for raw in lines:
            qty = _dec(raw["quantity"])
            unit_price = _dec(raw["unit_price"])
            if qty <= 0 or unit_price < 0:
                raise ProcurementValidationError("Invalid order line amounts")
            line_total = quantize(qty * unit_price)
            subtotal += line_total
            built.append(
                {
                    "product_id": parse_object_id(raw["product_id"]) if raw.get("product_id") else None,
                    "product_name_snapshot": raw.get("product_name") or "Product",
                    "sku_snapshot": raw.get("sku"),
                    "quantity": to_decimal128(qty),
                    "unit": raw.get("unit") or "unit",
                    "unit_price": to_decimal128(unit_price),
                    "line_total": to_decimal128(line_total),
                    "subtotal": to_decimal128(line_total),
                }
            )

        order_number = await self._next_number("PO", CollectionName.ORDERS, "order_number")
        active_tax = await _active_tax_settings()
        tax_name = (active_tax or {}).get("name") or "VAT"
        tax_rate = (active_tax or {}).get("rate")
        money_row = _compose_order_money(
            subtotal=subtotal,
            discount_total="0",
            charge_total="0",
            tax_rate=tax_rate,
            existing_tax_total="0",
        )
        order = await self.orders.create(
            {
                "order_number": order_number,
                "buyer_business_id": parse_object_id(buyer_id),
                "supplier_business_id": parse_object_id(supplier_business_id),
                "rfq_id": None,
                "quotation_id": None,
                "source": "cart_direct",
                "status": OrderStatus.PENDING,
                "currency": currency or "USD",
                "subtotal": to_decimal128(money_row["subtotal"]),
                "discount_total": to_decimal128(money_row["discount_total"]),
                "charge_total": to_decimal128(money_row["charge_total"]),
                "tax_total": to_decimal128(money_row["tax_total"]),
                "total": to_decimal128(money_row["total"]),
                "tax_rate_snapshot": to_decimal128(money_row["tax_rate_snapshot"])
                if money_row["tax_rate_snapshot"] is not None
                else None,
                "tax_name_snapshot": tax_name if money_row["tax_rate_snapshot"] is not None else None,
                "shipping_address": None,
                "billing_address": None,
                "payment_terms": "Net 30",
                "payment_method": "Bank transfer",
                "delivery_terms": None,
                "payment_status": "unpaid",
                "stock_reservation_status": "pending",
                "status_history": [
                    {
                        "status": OrderStatus.PENDING,
                        "changed_by_user_id": parse_object_id(user_id),
                        "note": "Created directly from marketplace cart",
                        "changed_at": now,
                    }
                ],
                "rejection_reason": None,
                "confirmed_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        for ln in built:
            await self.order_items.create(
                {
                    "order_id": order["_id"],
                    "quotation_item_id": None,
                    "rfq_item_id": None,
                    "product_id": ln["product_id"],
                    "product_name_snapshot": ln["product_name_snapshot"],
                    "sku_snapshot": ln["sku_snapshot"],
                    "quantity": ln["quantity"],
                    "unit": ln["unit"],
                    "unit_price": ln["unit_price"],
                    "discount_snapshot": zero,
                    "tax_snapshot": zero,
                    "subtotal": ln["subtotal"],
                    "line_total": ln["line_total"],
                    "shipped_quantity": zero,
                    "received_quantity": zero,
                    "damaged_quantity": zero,
                    "missing_quantity": zero,
                    "rejected_quantity": zero,
                }
            )

        await self.audit.log(
            action="ORDER_CREATED_FROM_CART",
            resource_type="order",
            resource_id=order["_id"],
            business_account_id=buyer_id,
            user_id=user_id,
            actor_id=user_id,
            ip_address=ip,
            metadata={
                "order_number": order_number,
                "supplier_business_id": supplier_business_id,
                "line_count": len(built),
            },
        )
        await notify(
            recipient_business_id=supplier_business_id,
            type="ORDER_CREATED",
            title=f"New direct order {order_number}",
            message="A buyer placed a direct purchase order. Confirm it in TradeBay to continue fulfilment.",
            reference_type="order",
            reference_id=order["_id"],
        )
        await event_bus.publish(
            DomainEvent(name=ORDER_CREATED, payload={"order_id": str(order["_id"])})
        )
        return await self.get_order(user_id=user_id, business=business, order_id=str(order["_id"]))

    def _assert_quote_access(self, quote: dict[str, Any], business: dict[str, Any] | None) -> None:
        if not business:
            raise ProcurementForbiddenError()
        if str(business.get("type")) == BusinessAccountType.PLATFORM:
            return
        bid = str(business["_id"])
        if bid not in {str(quote.get("supplier_id")), str(quote.get("buyer_business_id"))}:
            raise ProcurementForbiddenError()

    # ── Orders / PO ──────────────────────────────────────────────────────

    async def list_orders(
        self,
        *,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        if not business:
            raise ProcurementForbiddenError()
        as_buyer = str(business.get("type")) == BusinessAccountType.BUYER
        bid = str(business["_id"])
        return await self.list_orders_for_business(
            business_id=bid,
            as_buyer=as_buyer,
            page=page,
            page_size=page_size,
            status=status,
        )

    async def list_orders_for_business(
        self,
        *,
        business_id: str,
        as_buyer: bool = True,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Platform/admin oversight — list POs for a trading company by id."""
        rows = await self.orders.list_for_business(
            business_id,
            as_buyer=as_buyer,
            skip=(page - 1) * page_size,
            limit=page_size,
            status=status,
        )
        total = await self.orders.count_for_business(
            business_id, as_buyer=as_buyer, status=status
        )
        return [await self._serialize_order_summary(o) for o in rows], total

    async def list_rfqs_for_buyer_business(
        self,
        *,
        business_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Platform/admin oversight — list RFQs created by a buyer company."""
        rows = await self.rfqs.list_for_buyer(
            business_id,
            skip=(page - 1) * page_size,
            limit=page_size,
            status=status,
        )
        total = await self.rfqs.count_for_buyer(business_id, status=status)
        return [await self._serialize_rfq_summary(r) for r in rows], total

    async def get_order(
        self, *, user_id: str, business: dict[str, Any] | None, order_id: str
    ) -> dict[str, Any]:
        order = await self._get_accessible_order(order_id, business)
        return await self._serialize_order(order)

    async def acknowledge_order(
        self, *, user_id: str, business: dict[str, Any] | None, order_id: str
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError()
        if str(order.get("supplier_business_id")) != supplier_id:
            raise ProcurementForbiddenError()
        assert_transition(ORDER_TRANSITIONS, order["status"], OrderStatus.CONFIRMED)

        # Reserve catalog lines before confirm — never leave a confirmed PO with silent stock miss.
        reservation = await self._reserve_stock_for_order(
            order_id=str(order["_id"]),
            user_id=user_id,
            supplier_id=supplier_id,
            require_success=True,
        )

        now = utc_now()
        history = list(order.get("status_history") or [])
        history.append(
            {
                "status": OrderStatus.CONFIRMED,
                "changed_by_user_id": parse_object_id(user_id),
                "note": "Supplier acknowledged PO",
                "changed_at": now,
            }
        )
        await self.orders.update(
            order["_id"],
            {
                "status": OrderStatus.CONFIRMED,
                "confirmed_at": now,
                "stock_reservation_status": reservation,
                "status_history": history,
                "updated_at": now,
            },
        )
        # Finance + platform money: invoice + commission/payable from confirmed PO
        await self._try_issue_finance_on_confirm(order_id=str(order["_id"]), user_id=user_id)
        await notify(
            recipient_business_id=order["buyer_business_id"],
            type="ORDER_CONFIRMED",
            title=f"PO {order.get('order_number')} acknowledged",
            message="The supplier confirmed this purchase order and is preparing fulfilment.",
            reference_type="order",
            reference_id=order["_id"],
        )
        from app.modules.communication.constants import SystemEvent
        from app.modules.communication.timeline import post_thread_system_event

        await post_thread_system_event(
            context_type="order",
            context_id=order["_id"],
            system_event=SystemEvent.ORDER_CONFIRMED,
            body=f"Purchase order {order.get('order_number')} confirmed",
            initiator_business_id=order["buyer_business_id"],
            counterparty_business_id=order["supplier_business_id"],
            subject=f"PO {order.get('order_number')}",
        )
        return await self.get_order(user_id=user_id, business=business, order_id=order_id)

    async def _try_issue_finance_on_confirm(self, *, order_id: str, user_id: str) -> None:
        try:
            from app.modules.finance.service import issue_invoice_for_confirmed_order
            from app.modules.platform_money.service import create_commission_and_payable_for_order

            order = await self.orders.get_by_id(order_id)
            if not order:
                return
            items = await self.order_items.list_for_order(order_id)
            await issue_invoice_for_confirmed_order(order=order, order_items=items, user_id=user_id)
            await create_commission_and_payable_for_order(order=order)
        except Exception:
            # Finance must not block fulfilment acknowledgement
            pass

    async def _reserve_stock_for_order(
        self,
        *,
        order_id: str,
        user_id: str,
        supplier_id: str,
        require_success: bool,
    ) -> str:
        """Reserve catalog lines. Returns stock_reservation_status."""
        from app.modules.catalog.exceptions import InsufficientStockError
        from app.modules.catalog.service import CatalogService

        catalog = CatalogService()
        items = await self.order_items.list_for_order(order_id)
        catalog_lines = [item for item in items if item.get("product_id")]
        if not catalog_lines:
            return "not_applicable"

        reserved: list[tuple[str, Any]] = []
        try:
            for item in catalog_lines:
                pid = str(item["product_id"])
                await catalog.reserve_stock(
                    pid,
                    business_id=supplier_id,
                    user_id=user_id,
                    quantity=_dec(item["quantity"]),
                    reference_type="order",
                    reference_id=order_id,
                )
                reserved.append((pid, _dec(item["quantity"])))
        except InsufficientStockError:
            # Roll back any lines already reserved in this attempt.
            for pid, qty in reserved:
                try:
                    await catalog.release_stock(
                        pid,
                        business_id=supplier_id,
                        user_id=user_id,
                        quantity=qty,
                        reference_type="order",
                        reference_id=order_id,
                        reason="Rollback after insufficient stock on PO acknowledge",
                    )
                except Exception:
                    pass
            if require_success:
                raise ProcurementValidationError(
                    "Insufficient available stock to acknowledge this purchase order"
                )
            raise
        except Exception:
            for pid, qty in reserved:
                try:
                    await catalog.release_stock(
                        pid,
                        business_id=supplier_id,
                        user_id=user_id,
                        quantity=qty,
                        reference_type="order",
                        reference_id=order_id,
                        reason="Rollback after reservation error on PO acknowledge",
                    )
                except Exception:
                    pass
            if require_success:
                raise ProcurementValidationError(
                    "Unable to reserve stock for one or more order lines"
                )
            raise
        return "reserved"

    async def _release_stock_for_order(
        self, *, order_id: str, user_id: str, supplier_id: str
    ) -> None:
        from app.modules.catalog.exceptions import InsufficientReservedError
        from app.modules.catalog.service import CatalogService

        catalog = CatalogService()
        items = await self.order_items.list_for_order(order_id)
        released_any = False
        for item in items:
            pid = item.get("product_id")
            if not pid:
                continue
            try:
                await catalog.release_stock(
                    str(pid),
                    business_id=supplier_id,
                    user_id=user_id,
                    quantity=_dec(item["quantity"]),
                    reference_type="order",
                    reference_id=order_id,
                    reason="Order cancelled / rejected",
                )
                released_any = True
            except InsufficientReservedError:
                # Already released or never reserved — idempotent cancel path.
                continue
        if released_any:
            await self.orders.update(
                order_id,
                {"stock_reservation_status": "released", "updated_at": utc_now()},
            )
    async def _get_accessible_order(
        self, order_id: str, business: dict[str, Any] | None
    ) -> dict[str, Any]:
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError()
        if not business:
            raise ProcurementForbiddenError()
        if str(business.get("type")) == BusinessAccountType.PLATFORM:
            return order
        bid = str(business["_id"])
        if bid not in {
            str(order.get("buyer_business_id")),
            str(order.get("supplier_business_id")),
        }:
            raise ProcurementForbiddenError()
        return order

    # ── Shipments ────────────────────────────────────────────────────────

    async def create_shipment(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        order_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError()
        if str(order.get("supplier_business_id")) != supplier_id:
            raise ProcurementForbiddenError()
        if order["status"] not in {
            OrderStatus.CONFIRMED,
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
        }:
            raise ProcurementValidationError("Order is not ready for shipment")

        order_items = {str(i["_id"]): i for i in await self.order_items.list_for_order(order_id)}
        existing_shipped = await self.shipment_items.list_for_order(order_id)
        shipped_by_item: dict[str, Decimal] = {}
        for s in existing_shipped:
            key = str(s["order_item_id"])
            shipped_by_item[key] = shipped_by_item.get(key, Decimal("0")) + _dec(s["quantity"])

        now = utc_now()
        number = await self._next_number("SHP", CollectionName.SHIPMENTS, "shipment_number")
        shipment = await self.shipments.create(
            {
                "shipment_number": number,
                "order_id": parse_object_id(order_id),
                "supplier_business_id": parse_object_id(supplier_id),
                "buyer_business_id": order["buyer_business_id"],
                # One-shot dispatch: journey milestones after this are ETA-driven, not manual taps.
                "status": ShipmentStatus.SHIPPED,
                "carrier_name": payload.get("carrier_name"),
                "tracking_number": payload.get("tracking_number"),
                "origin": payload.get("origin"),
                "shipping_address": order.get("shipping_address"),
                "estimated_delivery_at": payload.get("estimated_delivery_at"),
                "shipped_at": now,
                "delivered_at": None,
                "shipping_notes": payload.get("shipping_notes"),
                "tracking_events": [
                    {
                        "status": ShipmentStatus.PREPARING,
                        "description": "Package prepared for dispatch",
                        "location": payload.get("origin"),
                        "source": "system",
                        "occurred_at": now,
                        "metadata": None,
                    },
                    {
                        "status": ShipmentStatus.SHIPPED,
                        "description": "Package handed to carrier — ETA set",
                        "location": payload.get("origin"),
                        "source": "system",
                        "occurred_at": now,
                        "metadata": None,
                    },
                ],
                "delivery_evidence": [],
                "receiving": [],
                "received_at": None,
                "receiving_notes": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        for raw in payload["lines"]:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            oi = order_items.get(data["order_item_id"])
            if not oi:
                raise ProcurementValidationError("Shipment line must reference an order item")
            qty = money(data["quantity"])
            already = shipped_by_item.get(data["order_item_id"], Decimal("0"))
            ordered = _dec(oi["quantity"])
            if already + qty > ordered:
                raise ProcurementValidationError(
                    f"Cannot ship more than ordered for {oi.get('product_name_snapshot')}"
                )
            await self.shipment_items.create(
                {
                    "shipment_id": shipment["_id"],
                    "order_id": parse_object_id(order_id),
                    "order_item_id": parse_object_id(data["order_item_id"]),
                    "product_id": oi.get("product_id"),
                    "product_name_snapshot": oi.get("product_name_snapshot"),
                    "sku_snapshot": oi.get("sku_snapshot"),
                    "quantity": to_decimal128(qty),
                    "unit": oi.get("unit") or "unit",
                    "created_at": now,
                }
            )
            new_shipped = already + qty
            await self.order_items.update(
                oi["_id"],
                {"shipped_quantity": to_decimal128(new_shipped)},
            )

        history = list(order.get("status_history") or [])
        next_status = order["status"]
        if next_status == OrderStatus.CONFIRMED:
            assert_transition(ORDER_TRANSITIONS, next_status, OrderStatus.PROCESSING)
            history.append(
                {
                    "status": OrderStatus.PROCESSING,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": "Shipment prepared",
                    "changed_at": now,
                }
            )
            next_status = OrderStatus.PROCESSING
        if next_status == OrderStatus.PROCESSING:
            assert_transition(ORDER_TRANSITIONS, next_status, OrderStatus.SHIPPED)
            history.append(
                {
                    "status": OrderStatus.SHIPPED,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": "Package dispatched — tracking follows ETA automatically",
                    "changed_at": now,
                }
            )
            next_status = OrderStatus.SHIPPED
        if next_status != order["status"]:
            await self.orders.update(
                order["_id"],
                {"status": next_status, "status_history": history, "updated_at": now},
            )

        await notify(
            recipient_business_id=order["buyer_business_id"],
            type="SHIPMENT_CREATED",
            title=f"Shipment {number} is on the way — {order.get('order_number')}",
            message="The supplier dispatched your package. Track progress against the ETA in TradeBay.",
            reference_type="shipment",
            reference_id=shipment["_id"],
        )
        return await self.get_shipment(user_id=user_id, business=business, shipment_id=str(shipment["_id"]))

    async def add_tracking_event(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        shipment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Only the fulfilling supplier (or carrier webhook) may advance status.
        # Buyers confirm receipt via receive_shipment after DELIVERED.
        supplier_id = self._require_supplier(business)
        shipment = await self._get_accessible_shipment(shipment_id, business)
        if str(shipment.get("supplier_business_id") or "") != supplier_id:
            raise ProcurementForbiddenError("Only the fulfilling supplier can update tracking")
        target = payload["status"]
        assert_transition(SHIPMENT_TRANSITIONS, shipment["status"], target)
        now = utc_now()
        events = list(shipment.get("tracking_events") or [])
        events.append(
            {
                "status": target,
                "description": payload.get("description"),
                "location": payload.get("location"),
                "source": "manual",
                "occurred_at": payload.get("occurred_at") or now,
                "metadata": None,
            }
        )
        updates: dict[str, Any] = {
            "status": target,
            "tracking_events": events,
            "updated_at": now,
        }
        if target == ShipmentStatus.SHIPPED:
            updates["shipped_at"] = now
            order = await self.orders.get_by_id(shipment["order_id"])
            if order and order["status"] in {OrderStatus.PROCESSING, OrderStatus.CONFIRMED}:
                assert_transition(ORDER_TRANSITIONS, order["status"], OrderStatus.SHIPPED)
                history = list(order.get("status_history") or [])
                history.append(
                    {
                        "status": OrderStatus.SHIPPED,
                        "changed_by_user_id": parse_object_id(user_id),
                        "note": "Shipment shipped",
                        "changed_at": now,
                    }
                )
                await self.orders.update(
                    order["_id"],
                    {"status": OrderStatus.SHIPPED, "status_history": history, "updated_at": now},
                )
        if target == ShipmentStatus.DELIVERED:
            updates["delivered_at"] = now
            await event_bus.publish(
                DomainEvent(name=SHIPMENT_DELIVERED, payload={"shipment_id": shipment_id})
            )
        await self.shipments.update(shipment["_id"], updates)
        email_now = target in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}
        await notify(
            recipient_business_id=shipment.get("buyer_business_id"),
            type="TRACKING_UPDATED",
            title=f"Shipment {shipment.get('shipment_number')} → {target}",
            message=(
                f"Status is now {target}."
                + (f" {payload.get('description')}" if payload.get("description") else "")
            ).strip(),
            reference_type="shipment",
            reference_id=shipment["_id"],
            email=email_now,
        )
        return await self.get_shipment(user_id=user_id, business=business, shipment_id=shipment_id)

    async def add_delivery_evidence(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        shipment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        supplier_id = self._require_supplier(business)
        shipment = await self._get_accessible_shipment(shipment_id, business)
        if str(shipment.get("supplier_business_id") or "") != supplier_id:
            raise ProcurementForbiddenError("Only the fulfilling supplier can upload delivery evidence")
        evidence = list(shipment.get("delivery_evidence") or [])
        evidence.append(
            {
                "evidence_type": payload["evidence_type"],
                "url": payload["url"],
                "note": payload.get("note"),
                "uploaded_by_user_id": parse_object_id(user_id),
                "captured_at": utc_now(),
            }
        )
        await self.shipments.update(
            shipment["_id"],
            {"delivery_evidence": evidence, "updated_at": utc_now()},
        )
        return await self.get_shipment(user_id=user_id, business=business, shipment_id=shipment_id)

    async def receive_shipment(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        shipment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        shipment = await self.shipments.get_by_id(shipment_id)
        if shipment is None:
            raise ShipmentNotFoundError()
        if str(shipment.get("buyer_business_id")) != buyer_id:
            raise ProcurementForbiddenError()
        if shipment["status"] != ShipmentStatus.DELIVERED:
            raise ProcurementValidationError("Can only receive a delivered shipment")

        ship_items = {
            str(i["order_item_id"]): i
            for i in await self.shipment_items.list_for_shipment(shipment_id)
        }
        receiving = []
        now = utc_now()
        for raw in payload["lines"]:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            si = ship_items.get(data["order_item_id"])
            if not si:
                raise ProcurementValidationError("Receiving line must match a shipment item")
            received = money(data.get("received_quantity") or "0")
            damaged = money(data.get("damaged_quantity") or "0")
            missing = money(data.get("missing_quantity") or "0")
            rejected = money(data.get("rejected_quantity") or "0")
            shipped_qty = _dec(si["quantity"])
            if received + damaged + missing + rejected > shipped_qty:
                raise ProcurementValidationError("Receiving quantities exceed shipped quantity")
            receiving.append(
                {
                    "order_item_id": parse_object_id(data["order_item_id"]),
                    "received_quantity": to_decimal128(received),
                    "damaged_quantity": to_decimal128(damaged),
                    "missing_quantity": to_decimal128(missing),
                    "rejected_quantity": to_decimal128(rejected),
                    "notes": data.get("notes"),
                }
            )
            oi = await self.order_items.get_by_id(data["order_item_id"])
            if oi:
                await self.order_items.update(
                    oi["_id"],
                    {
                        "received_quantity": to_decimal128(
                            _dec(oi.get("received_quantity") or 0) + received
                        ),
                        "damaged_quantity": to_decimal128(
                            _dec(oi.get("damaged_quantity") or 0) + damaged
                        ),
                        "missing_quantity": to_decimal128(
                            _dec(oi.get("missing_quantity") or 0) + missing
                        ),
                        "rejected_quantity": to_decimal128(
                            _dec(oi.get("rejected_quantity") or 0) + rejected
                        ),
                    },
                )
                # Buyer inventory increase for accepted goods
                if received > 0 and oi.get("product_id"):
                    await self._try_stock_received(
                        product_id=str(oi["product_id"]),
                        buyer_id=buyer_id,
                        user_id=user_id,
                        quantity=received,
                        shipment_id=shipment_id,
                    )

        await self.shipments.update(
            shipment["_id"],
            {
                "receiving": receiving,
                "received_at": now,
                "receiving_notes": payload.get("notes"),
                "updated_at": now,
            },
        )

        order = await self.orders.get_by_id(shipment["order_id"])
        if order and payload.get("complete_order", True):
            await self._maybe_complete_order(order=order, user_id=user_id)

        return await self.get_shipment(user_id=user_id, business=business, shipment_id=shipment_id)

    async def _try_stock_received(
        self,
        *,
        product_id: str,
        buyer_id: str,
        user_id: str,
        quantity: Decimal,
        shipment_id: str,
    ) -> None:
        """Receiving increases buyer inventory only if the product belongs to the buyer.

        For marketplace wholesale buys, inventory typically lives with the supplier.
        We attempt stock_received; failures are ignored (buyer may not own the SKU).
        """
        try:
            from app.modules.catalog.service import CatalogService

            await CatalogService().add_stock(
                product_id,
                business_id=buyer_id,
                user_id=user_id,
                quantity=quantity,
                reason="Goods received from shipment",
                reference_type="shipment",
                reference_id=shipment_id,
            )
        except Exception:
            pass

    async def _maybe_complete_order(self, *, order: dict[str, Any], user_id: str) -> None:
        try:
            from app.modules.trust.service import TrustService

            if await TrustService().has_open_dispute(order["_id"]):
                return
        except Exception:
            pass
        items = await self.order_items.list_for_order(order["_id"])
        all_received = True
        for item in items:
            ordered = _dec(item["quantity"])
            received = _dec(item.get("received_quantity") or 0)
            damaged = _dec(item.get("damaged_quantity") or 0)
            missing = _dec(item.get("missing_quantity") or 0)
            rejected = _dec(item.get("rejected_quantity") or 0)
            if received + damaged + missing + rejected < ordered:
                all_received = False
                break
        if not all_received:
            if order["status"] == OrderStatus.SHIPPED:
                assert_transition(ORDER_TRANSITIONS, order["status"], OrderStatus.DELIVERED)
                now = utc_now()
                history = list(order.get("status_history") or [])
                history.append(
                    {
                        "status": OrderStatus.DELIVERED,
                        "changed_by_user_id": parse_object_id(user_id),
                        "note": "Partial receiving recorded",
                        "changed_at": now,
                    }
                )
                await self.orders.update(
                    order["_id"],
                    {"status": OrderStatus.DELIVERED, "status_history": history, "updated_at": now},
                )
            return
        # Full accounting of quantities → delivered then completed
        now = utc_now()
        history = list(order.get("status_history") or [])
        status = order["status"]
        if status == OrderStatus.SHIPPED:
            assert_transition(ORDER_TRANSITIONS, status, OrderStatus.DELIVERED)
            history.append(
                {
                    "status": OrderStatus.DELIVERED,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": "Goods received",
                    "changed_at": now,
                }
            )
            status = OrderStatus.DELIVERED
        if status == OrderStatus.DELIVERED:
            assert_transition(ORDER_TRANSITIONS, status, OrderStatus.COMPLETED)
            history.append(
                {
                    "status": OrderStatus.COMPLETED,
                    "changed_by_user_id": parse_object_id(user_id),
                    "note": "Fulfilment completed",
                    "changed_at": now,
                }
            )
            await self.orders.update(
                order["_id"],
                {
                    "status": OrderStatus.COMPLETED,
                    "completed_at": now,
                    "status_history": history,
                    "updated_at": now,
                },
            )
            await self._try_release_platform_funds(order_id=str(order["_id"]), user_id=user_id)
            try:
                from app.modules.trust.notify import notify

                await notify(
                    recipient_business_id=order.get("supplier_business_id"),
                    type="ORDER_COMPLETED",
                    title=f"PO {order.get('order_number')} completed",
                    message="The buyer recorded a full receipt. Fulfilment is complete.",
                    reference_type="order",
                    reference_id=order["_id"],
                )
            except Exception:
                pass

    async def _try_release_platform_funds(self, *, order_id: str, user_id: str) -> None:
        try:
            from app.modules.platform_money.service import PlatformMoneyService

            await PlatformMoneyService().release_funds_for_order(
                order_id=order_id, user_id=user_id
            )
        except Exception:
            pass

    async def get_shipment(
        self, *, user_id: str, business: dict[str, Any] | None, shipment_id: str
    ) -> dict[str, Any]:
        shipment = await self._get_accessible_shipment(shipment_id, business)
        return await self._serialize_shipment(shipment)

    async def _get_accessible_shipment(
        self, shipment_id: str, business: dict[str, Any] | None
    ) -> dict[str, Any]:
        shipment = await self.shipments.get_by_id(shipment_id)
        if shipment is None:
            raise ShipmentNotFoundError()
        if not business:
            raise ProcurementForbiddenError()
        if str(business.get("type")) == BusinessAccountType.PLATFORM:
            return shipment
        bid = str(business["_id"])
        if bid not in {
            str(shipment.get("buyer_business_id")),
            str(shipment.get("supplier_business_id")),
        }:
            # Fall back via order
            order = await self.orders.get_by_id(shipment["order_id"])
            if not order or bid not in {
                str(order.get("buyer_business_id")),
                str(order.get("supplier_business_id")),
            }:
                raise ProcurementForbiddenError()
        return shipment

    async def dashboard(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ProcurementForbiddenError()
        bid = str(business["_id"])
        is_buyer = str(business.get("type")) == BusinessAccountType.BUYER
        if is_buyer:
            rfqs, rfq_total = await self.list_rfqs(business=business, page=1, page_size=5)
            orders, order_total = await self.list_orders(business=business, page=1, page_size=5)
            quotes_waiting = 0
            for r in await self.rfqs.list_for_buyer(bid, limit=50):
                if r.get("status") in {RFQStatus.RESPONDING, RFQStatus.PUBLISHED}:
                    qs = await self.quotations.list_for_rfq(str(r["_id"]))
                    quotes_waiting += sum(
                        1 for q in qs if q.get("status") == QuotationStatus.SUBMITTED
                    )
            return {
                "role": "buyer",
                "next_actions": [
                    {"key": "quotes", "label": f"{quotes_waiting} quotations waiting for comparison"}
                    if quotes_waiting
                    else None,
                    {"key": "rfqs", "label": f"{rfq_total} active RFQs"},
                    {"key": "orders", "label": f"{order_total} purchase orders"},
                ],
                "rfqs": rfqs,
                "orders": orders,
                "quotes_waiting": quotes_waiting,
            }
        # supplier
        invited, inv_total = await self.list_rfqs(
            business=business, page=1, page_size=5, as_supplier=True
        )
        orders, order_total = await self.list_orders(business=business, page=1, page_size=5)
        pending_ack = await self.orders.count_for_business(
            bid, as_buyer=False, status=OrderStatus.PENDING
        )
        return {
            "role": "supplier",
            "next_actions": [
                {"key": "ack", "label": f"{pending_ack} purchase orders awaiting acknowledgement"}
                if pending_ack
                else None,
                {"key": "invites", "label": f"{inv_total} RFQ invitations"},
            ],
            "rfqs": invited,
            "orders": orders,
            "pending_acknowledgements": pending_ack,
        }

    # ── Serialization ────────────────────────────────────────────────────

    async def _serialize_rfq_summary(self, rfq: dict[str, Any]) -> dict[str, Any]:
        invites = rfq.get("supplier_invites") or []
        quotes = await self.quotations.list_for_rfq(str(rfq["_id"]))
        buyer = await self._business_card(rfq.get("buyer_business_id"))
        return {
            "id": str(rfq["_id"]),
            "rfq_number": rfq.get("rfq_number"),
            "title": rfq.get("title"),
            "rfq_type": rfq.get("rfq_type") or RFQType.SOURCING,
            "status": rfq.get("status"),
            "visibility": rfq.get("visibility"),
            "currency": rfq.get("currency") or "USD",
            "product_id": _oid(rfq.get("product_id")),
            "supplier_business_id": _oid(rfq.get("supplier_business_id")),
            "response_deadline": rfq.get("response_deadline").isoformat()
            if rfq.get("response_deadline")
            else None,
            "invite_count": len(invites),
            "quotation_count": len(quotes),
            "buyer_business_id": _oid(rfq.get("buyer_business_id")),
            "buyer_name": buyer["name"],
            "buyer_logo_url": buyer["logo_url"],
            "created_at": rfq.get("created_at").isoformat() if rfq.get("created_at") else None,
            "updated_at": rfq.get("updated_at").isoformat() if rfq.get("updated_at") else None,
        }

    async def _primary_image_urls(self, product_ids: list[str]) -> dict[str, str]:
        from app.modules.catalog.repository import ProductImageRepository

        oids: list[ObjectId] = []
        seen: set[str] = set()
        for pid in product_ids:
            if not pid or pid in seen or pid == "None" or not ObjectId.is_valid(pid):
                continue
            seen.add(pid)
            oids.append(parse_object_id(pid))
        if not oids:
            return {}
        rows = await ProductImageRepository().find_many(
            {"product_id": {"$in": oids}, "deleted_at": None},
            limit=max(50, len(oids) * 8),
            sort=[("is_primary", -1), ("display_order", 1), ("created_at", 1)],
        )
        out: dict[str, str] = {}
        for row in rows:
            pid = _oid(row.get("product_id"))
            url = row.get("url")
            if not pid or pid in out or not url:
                continue
            out[pid] = str(url)
        return out

    def _serialize_rfq_item(
        self,
        item: dict[str, Any],
        *,
        supplier_business_id: str | None = None,
        supplier_name: str | None = None,
        primary_image_url: str | None = None,
    ) -> dict[str, Any]:
        sid = supplier_business_id or _oid(item.get("supplier_business_id"))
        return {
            "id": str(item["_id"]),
            "product_id": _oid(item.get("product_id")),
            "category_id": _oid(item.get("category_id")),
            "supplier_business_id": sid,
            "supplier_name": supplier_name,
            "product_name": item.get("product_name"),
            "sku": item.get("sku"),
            "quantity": _money_out(item.get("quantity")),
            "unit": item.get("unit"),
            "catalog_unit_price": _money_out(item.get("catalog_unit_price")),
            "target_unit_price": _money_out(item.get("target_unit_price")),
            "primary_image_url": primary_image_url
            or item.get("primary_image_url")
            or None,
            "requirements": item.get("requirements"),
            "notes": item.get("notes"),
            "sort_order": item.get("sort_order", 0),
        }

    def _supplier_requests(
        self,
        *,
        items: list[dict[str, Any]],
        invites: list[dict[str, Any]],
        quotations: list[dict[str, Any]],
        rfq_status: str,
    ) -> list[dict[str, Any]]:
        """One progress row per engaged supplier, with the products they can quote."""
        quotes_by_sid = {q.get("supplier_id"): q for q in quotations if q.get("supplier_id")}
        items_by_sid: dict[str, list[dict[str, Any]]] = {}
        names: dict[str, str | None] = {}
        for item in items:
            sid = item.get("supplier_business_id")
            if not sid:
                continue
            names[sid] = item.get("supplier_name")
            items_by_sid.setdefault(sid, []).append(
                {
                    "id": item.get("id"),
                    "product_name": item.get("product_name"),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                    "primary_image_url": item.get("primary_image_url"),
                }
            )
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for invite in invites:
            sid = invite.get("supplier_business_id")
            if not sid:
                continue
            seen.add(sid)
            quote = quotes_by_sid.get(sid)
            invite_status = str(invite.get("status") or "")
            quote_status = str(quote.get("status") or "") if quote else ""
            stage = "awaiting_quotation"
            if invite_status == SupplierInviteStatus.DECLINED:
                stage = "declined"
            elif quote_status == QuotationStatus.ACCEPTED or (
                rfq_status == RFQStatus.AWARDED and quote_status
            ):
                stage = "accepted" if quote_status == QuotationStatus.ACCEPTED else "rejected"
            elif quote_status == QuotationStatus.REJECTED:
                stage = "rejected"
            elif quote_status == QuotationStatus.NEGOTIATING:
                stage = "negotiating"
            elif quote_status == QuotationStatus.SUBMITTED:
                stage = "quoted"
            elif quote_status == QuotationStatus.WITHDRAWN:
                stage = "withdrawn"
            elif invite_status == SupplierInviteStatus.VIEWED:
                stage = "received"
            rows.append(
                {
                    "supplier_business_id": sid,
                    "supplier_name": invite.get("supplier_name") or names.get(sid),
                    "invite_status": invite_status,
                    "quotation_id": quote.get("id") if quote else None,
                    "quotation_status": quote_status or None,
                    "stage": stage,
                    "products": items_by_sid.get(sid, []),
                }
            )
        for sid, products in items_by_sid.items():
            if sid in seen:
                continue
            quote = quotes_by_sid.get(sid)
            rows.append(
                {
                    "supplier_business_id": sid,
                    "supplier_name": names.get(sid),
                    "invite_status": None,
                    "quotation_id": quote.get("id") if quote else None,
                    "quotation_status": quote.get("status") if quote else None,
                    "stage": "matched",
                    "products": products,
                }
            )
        return rows

    async def _serialize_rfq(
        self, rfq: dict[str, Any], *, include_quotes_for: str | None = None
    ) -> dict[str, Any]:
        summary = await self._serialize_rfq_summary(rfq)
        items = await self.rfq_items.list_for_rfq(rfq["_id"])
        owners = await self._product_owners(items)
        visible_items = items
        if include_quotes_for:
            visible_items = [
                item
                for item in items
                if not item.get("product_id")
                or owners.get(str(item["product_id"])) == include_quotes_for
                or str(item.get("supplier_business_id") or "") == include_quotes_for
            ]
        name_ids: set[str] = set()
        for item in visible_items:
            sid = item.get("supplier_business_id") or owners.get(
                str(item["product_id"]) if item.get("product_id") else ""
            )
            if sid:
                name_ids.add(str(sid))
        names: dict[str, str | None] = {}
        for sid in name_ids:
            names[sid] = await self._business_name(sid)
        image_pids = [
            str(item["product_id"])
            for item in visible_items
            if item.get("product_id") and not item.get("primary_image_url")
        ]
        catalog_images = await self._primary_image_urls(image_pids)
        serialized_items = []
        for item in visible_items:
            sid = str(item.get("supplier_business_id") or "") or owners.get(
                str(item["product_id"]) if item.get("product_id") else ""
            )
            pid = str(item["product_id"]) if item.get("product_id") else None
            serialized_items.append(
                self._serialize_rfq_item(
                    item,
                    supplier_business_id=sid,
                    supplier_name=names.get(sid) if sid else None,
                    primary_image_url=(
                        item.get("primary_image_url")
                        or (catalog_images.get(pid) if pid else None)
                    ),
                )
            )
        quotes = await self.quotations.list_for_rfq(str(rfq["_id"]))
        if include_quotes_for:
            quotes = [q for q in quotes if str(q.get("supplier_id")) == include_quotes_for]
        invites_out = []
        for i in rfq.get("supplier_invites") or []:
            card = await self._business_card(i.get("supplier_business_id"))
            invites_out.append(
                {
                    "supplier_business_id": _oid(i.get("supplier_business_id")),
                    "supplier_name": card["name"],
                    "supplier_logo_url": card["logo_url"],
                    "status": i.get("status"),
                    "invited_at": i.get("invited_at").isoformat() if i.get("invited_at") else None,
                    "viewed_at": i.get("viewed_at").isoformat() if i.get("viewed_at") else None,
                    "responded_at": i.get("responded_at").isoformat()
                    if i.get("responded_at")
                    else None,
                    "decline_reason": i.get("decline_reason"),
                }
            )
        source_ids = [
            sid
            for sid in (_oid(x) for x in (rfq.get("source_supplier_ids") or []))
            if sid
        ]
        order = await self.orders.find_one({"rfq_id": rfq["_id"]})
        quote_payloads = [await self._serialize_quotation(q) for q in quotes]
        supplier_card = await self._business_card(rfq.get("supplier_business_id"))
        return {
            **summary,
            "description": rfq.get("description"),
            "destination": rfq.get("destination"),
            "required_by": rfq.get("required_by").isoformat() if rfq.get("required_by") else None,
            "notes": rfq.get("notes"),
            "buyer_business_id": _oid(rfq.get("buyer_business_id")),
            "awarded_quotation_id": _oid(rfq.get("awarded_quotation_id")),
            "rfq_type": rfq.get("rfq_type") or RFQType.SOURCING,
            "product_id": _oid(rfq.get("product_id")),
            "supplier_business_id": _oid(rfq.get("supplier_business_id")),
            "supplier_name": supplier_card["name"],
            "supplier_logo_url": supplier_card["logo_url"],
            "source": rfq.get("source"),
            "source_supplier_ids": source_ids,
            "items": serialized_items,
            "invites": invites_out,
            "quotations": quote_payloads,
            "supplier_requests": self._supplier_requests(
                items=serialized_items,
                invites=invites_out,
                quotations=quote_payloads,
                rfq_status=str(rfq.get("status") or ""),
            ),
            "order_id": _oid(order.get("_id")) if order else None,
            "order_number": order.get("order_number") if order else None,
            "order_status": order.get("status") if order else None,
        }

    async def _business_card(self, business_id: Any) -> dict[str, Any]:
        empty: dict[str, Any] = {
            "name": None,
            "logo_url": None,
            "legal_name": None,
            "tax_number": None,
            "contact_email": None,
            "contact_phone": None,
            "address": None,
        }
        if not business_id:
            return empty
        raw = str(business_id)
        if raw in {"None", "null"} or not ObjectId.is_valid(raw):
            return empty
        doc = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": parse_object_id(raw)},
            {
                "name": 1,
                "logo_url": 1,
                "legal_name": 1,
                "tax_number": 1,
                "contact_email": 1,
                "contact_phone": 1,
                "address": 1,
            },
        )
        if not doc:
            return empty
        return {
            "name": doc.get("name"),
            "logo_url": doc.get("logo_url"),
            "legal_name": doc.get("legal_name"),
            "tax_number": doc.get("tax_number"),
            "contact_email": doc.get("contact_email"),
            "contact_phone": doc.get("contact_phone"),
            "address": doc.get("address"),
        }

    async def _business_name(self, business_id: Any) -> str | None:
        return (await self._business_card(business_id))["name"]

    async def _serialize_quotation_summary(self, quote: dict[str, Any]) -> dict[str, Any]:
        supplier = await self._business_card(quote.get("supplier_id"))
        return {
            "id": str(quote["_id"]),
            "quotation_number": quote.get("quotation_number"),
            "rfq_id": _oid(quote.get("rfq_id")),
            "supplier_id": _oid(quote.get("supplier_id")),
            "supplier_name": supplier["name"],
            "supplier_logo_url": supplier["logo_url"],
            "status": quote.get("status"),
            "currency": quote.get("currency"),
            "subtotal": _money_out(quote.get("subtotal")),
            "discount_total": _money_out(quote.get("discount_total")),
            "charge_total": _money_out(quote.get("charge_total")),
            "tax_total": _money_out(quote.get("tax_total")),
            "total": _money_out(quote.get("total")),
            "current_version": quote.get("current_version", 1),
            "valid_until": quote.get("valid_until").isoformat() if quote.get("valid_until") else None,
            "submitted_at": quote.get("submitted_at").isoformat()
            if quote.get("submitted_at")
            else None,
        }

    def _serialize_quote_line(self, ln: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(ln["_id"]),
            "rfq_item_id": _oid(ln.get("rfq_item_id")),
            "version": ln.get("version"),
            "product_id": _oid(ln.get("product_id")),
            "product_name_snapshot": ln.get("product_name_snapshot"),
            "sku_snapshot": ln.get("sku_snapshot"),
            "quantity": _money_out(ln.get("quantity")),
            "unit": ln.get("unit"),
            "unit_price": _money_out(ln.get("unit_price")),
            "moq": ln.get("moq"),
            "lead_time_days": ln.get("lead_time_days"),
            "discount": _money_out(ln.get("discount")),
            "tax": _money_out(ln.get("tax")),
            "shipping_allocation": _money_out(ln.get("shipping_allocation")),
            "line_total": _money_out(ln.get("line_total")),
            "notes": ln.get("notes"),
        }

    async def _serialize_quotation(self, quote: dict[str, Any]) -> dict[str, Any]:
        summary = await self._serialize_quotation_summary(quote)
        lines = await self.quotation_items.list_for_quotation(
            quote["_id"], version=int(quote.get("current_version") or 1)
        )
        return {
            **summary,
            "payment_terms": quote.get("payment_terms"),
            "delivery_terms": quote.get("delivery_terms"),
            "notes": quote.get("notes"),
            "lines": [self._serialize_quote_line(ln) for ln in lines],
        }

    async def _serialize_order_summary(self, order: dict[str, Any]) -> dict[str, Any]:
        quotation_number = None
        if order.get("quotation_id"):
            quote = await self.quotations.get_by_id(str(order["quotation_id"]))
            if quote:
                quotation_number = quote.get("quotation_number")
        buyer = await self._business_card(order.get("buyer_business_id"))
        supplier = await self._business_card(order.get("supplier_business_id"))
        return {
            "id": str(order["_id"]),
            "order_number": order.get("order_number"),
            "status": order.get("status"),
            "currency": order.get("currency"),
            "total": _money_out(order.get("total")),
            "buyer_business_id": _oid(order.get("buyer_business_id")),
            "buyer_name": buyer["name"],
            "buyer_logo_url": buyer["logo_url"],
            "buyer_legal_name": buyer.get("legal_name"),
            "buyer_tax_number": buyer.get("tax_number"),
            "buyer_contact_email": buyer.get("contact_email"),
            "buyer_contact_phone": buyer.get("contact_phone"),
            "buyer_address": buyer.get("address"),
            "supplier_business_id": _oid(order.get("supplier_business_id")),
            "supplier_name": supplier["name"],
            "supplier_logo_url": supplier["logo_url"],
            "supplier_legal_name": supplier.get("legal_name"),
            "supplier_tax_number": supplier.get("tax_number"),
            "supplier_contact_email": supplier.get("contact_email"),
            "supplier_contact_phone": supplier.get("contact_phone"),
            "supplier_address": supplier.get("address"),
            "rfq_id": _oid(order.get("rfq_id")),
            "quotation_id": _oid(order.get("quotation_id")),
            "quotation_number": quotation_number,
            "created_at": order.get("created_at").isoformat() if order.get("created_at") else None,
            "confirmed_at": order.get("confirmed_at").isoformat()
            if order.get("confirmed_at")
            else None,
        }

    async def _serialize_order(self, order: dict[str, Any]) -> dict[str, Any]:
        summary = await self._serialize_order_summary(order)
        items = await self.order_items.list_for_order(order["_id"])
        shipments = await self.shipments.list_for_order(str(order["_id"]))

        tax_rate = order.get("tax_rate_snapshot")
        tax_name = order.get("tax_name_snapshot")
        tax_total = order.get("tax_total")
        total = order.get("total")
        # Backfill VAT for older orders that skipped platform tax.
        if tax_rate is None:
            active_tax = await _active_tax_settings()
            if active_tax and active_tax.get("rate") is not None:
                money_row = _compose_order_money(
                    subtotal=order.get("subtotal"),
                    discount_total=order.get("discount_total"),
                    charge_total=order.get("charge_total"),
                    tax_rate=active_tax.get("rate"),
                )
                tax_rate = money_row["tax_rate_snapshot"]
                tax_name = active_tax.get("name") or "VAT"
                tax_total = money_row["tax_total"]
                total = money_row["total"]

        return {
            **summary,
            "subtotal": _money_out(order.get("subtotal")),
            "discount_total": _money_out(order.get("discount_total")),
            "charge_total": _money_out(order.get("charge_total")),
            "tax_total": _money_out(tax_total),
            "total": _money_out(total) or summary.get("total"),
            "tax_rate_snapshot": _rate_out(tax_rate),
            "tax_name_snapshot": tax_name or ("VAT" if tax_rate is not None else None),
            "tax_rate_percent": _pct_label(tax_rate),
            "payment_terms": order.get("payment_terms"),
            "payment_method": order.get("payment_method"),
            "delivery_terms": order.get("delivery_terms"),
            "payment_status": order.get("payment_status"),
            "shipping_address": order.get("shipping_address"),
            "rejection_reason": order.get("rejection_reason"),
            "status_history": [
                {
                    "status": h.get("status"),
                    "note": h.get("note"),
                    "changed_at": h.get("changed_at").isoformat() if h.get("changed_at") else None,
                }
                for h in (order.get("status_history") or [])
            ],
            "items": [
                {
                    "id": str(i["_id"]),
                    "product_id": _oid(i.get("product_id")),
                    "product_name_snapshot": i.get("product_name_snapshot"),
                    "sku_snapshot": i.get("sku_snapshot"),
                    "quantity": _money_out(i.get("quantity")),
                    "unit": i.get("unit"),
                    "unit_price": _money_out(i.get("unit_price")),
                    "line_total": _money_out(i.get("line_total")),
                    "shipped_quantity": _money_out(i.get("shipped_quantity")),
                    "received_quantity": _money_out(i.get("received_quantity")),
                    "damaged_quantity": _money_out(i.get("damaged_quantity")),
                    "missing_quantity": _money_out(i.get("missing_quantity")),
                    "rejected_quantity": _money_out(i.get("rejected_quantity")),
                }
                for i in items
            ],
            "shipments": [await self._serialize_shipment_summary(s) for s in shipments],
        }

    async def _serialize_shipment_summary(self, shipment: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(shipment["_id"]),
            "shipment_number": shipment.get("shipment_number"),
            "order_id": _oid(shipment.get("order_id")),
            "status": shipment.get("status"),
            "carrier_name": shipment.get("carrier_name"),
            "tracking_number": shipment.get("tracking_number"),
            "estimated_delivery_at": shipment.get("estimated_delivery_at").isoformat()
            if shipment.get("estimated_delivery_at")
            else None,
            "shipped_at": shipment.get("shipped_at").isoformat() if shipment.get("shipped_at") else None,
            "delivered_at": shipment.get("delivered_at").isoformat()
            if shipment.get("delivered_at")
            else None,
        }

    async def _serialize_shipment(self, shipment: dict[str, Any]) -> dict[str, Any]:
        summary = await self._serialize_shipment_summary(shipment)
        items = await self.shipment_items.list_for_shipment(shipment["_id"])
        return {
            **summary,
            "origin": shipment.get("origin"),
            "shipping_notes": shipment.get("shipping_notes"),
            "shipping_address": shipment.get("shipping_address"),
            "tracking_events": [
                {
                    "status": e.get("status"),
                    "description": e.get("description"),
                    "location": e.get("location"),
                    "source": e.get("source") or "manual",
                    "occurred_at": e.get("occurred_at").isoformat() if e.get("occurred_at") else None,
                }
                for e in (shipment.get("tracking_events") or [])
            ],
            "delivery_evidence": [
                {
                    "evidence_type": e.get("evidence_type"),
                    "url": _public_evidence_url(str(shipment["_id"]), e.get("url")),
                    "note": e.get("note"),
                    "captured_at": e.get("captured_at").isoformat() if e.get("captured_at") else None,
                }
                for e in (shipment.get("delivery_evidence") or [])
            ],
            "receiving": [
                {
                    "order_item_id": _oid(r.get("order_item_id")),
                    "received_quantity": _money_out(r.get("received_quantity")),
                    "damaged_quantity": _money_out(r.get("damaged_quantity")),
                    "missing_quantity": _money_out(r.get("missing_quantity")),
                    "rejected_quantity": _money_out(r.get("rejected_quantity")),
                    "notes": r.get("notes"),
                }
                for r in (shipment.get("receiving") or [])
            ],
            "received_at": shipment.get("received_at").isoformat()
            if shipment.get("received_at")
            else None,
            "items": [
                {
                    "id": str(i["_id"]),
                    "order_item_id": _oid(i.get("order_item_id")),
                    "product_name_snapshot": i.get("product_name_snapshot"),
                    "sku_snapshot": i.get("sku_snapshot"),
                    "quantity": _money_out(i.get("quantity")),
                    "unit": i.get("unit"),
                }
                for i in items
            ],
        }

    async def apply_tracking_webhook(
        self, *, provider_name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        from app.modules.procurement.tracking import get_tracking_provider

        provider = get_tracking_provider(provider_name)
        update = provider.parse_webhook(payload)
        if update is None or not update.tracking_number:
            raise ProcurementValidationError("Unrecognized tracking webhook payload")
        shipment = await self.shipments.find_by_tracking(update.tracking_number)
        if shipment is None:
            raise ShipmentNotFoundError()
        assert_transition(SHIPMENT_TRANSITIONS, shipment["status"], update.status)
        now = utc_now()
        events = list(shipment.get("tracking_events") or [])
        events.append(
            {
                "status": update.status,
                "description": update.description,
                "location": update.location,
                "source": update.source,
                "occurred_at": update.occurred_at or now,
                "metadata": update.metadata,
            }
        )
        updates: dict[str, Any] = {
            "status": update.status,
            "tracking_events": events,
            "updated_at": now,
        }
        if update.status == ShipmentStatus.SHIPPED:
            updates["shipped_at"] = now
        if update.status == ShipmentStatus.DELIVERED:
            updates["delivered_at"] = now
        await self.shipments.update(shipment["_id"], updates)
        refreshed = await self.shipments.get_by_id(str(shipment["_id"]))
        assert refreshed is not None
        return await self._serialize_shipment(refreshed)

    async def report_shipment_issue(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        shipment_id: str,
        reason: str,
        description: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        shipment = await self._get_accessible_shipment(shipment_id, business)
        from app.modules.trust.service import TrustService

        dispute = await TrustService().open_dispute(
            user_id=user_id,
            business=business,
            order_id=str(shipment["order_id"]),
            reason=reason,
            description=description,
            evidence_url=None,
            ip=ip,
        )
        return {"dispute": dispute, "shipment_id": shipment_id}

    async def purchase_order_pdf_bytes(
        self, *, business: dict[str, Any] | None, order_id: str
    ) -> tuple[bytes, str]:
        from app.modules.procurement.documents import render_purchase_order_pdf

        order = await self._get_accessible_order(order_id, business)
        serialized = await self._serialize_order(order)
        return render_purchase_order_pdf(serialized), f"{serialized.get('order_number') or 'PO'}.pdf"

    async def quotation_pdf_bytes(
        self, *, user_id: str, business: dict[str, Any] | None, quotation_id: str
    ) -> tuple[bytes, str]:
        from app.modules.procurement.documents import render_quotation_pdf

        quote = await self.get_quotation(
            user_id=user_id, business=business, quotation_id=quotation_id
        )
        return render_quotation_pdf(quote), f"{quote.get('quotation_number') or 'QT'}.pdf"
