"""Buyer cart service — marketplace lines that checkout into an RFQ."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.modules.cart.exceptions import (
    CartBuyerRequiredError,
    CartEmptyError,
    CartInvalidSuggestedPriceError,
    CartItemNotFoundError,
    CartMixedCurrencyError,
    CartPriceRequiredError,
    CartProductUnavailableError,
)
from app.modules.cart.repository import CartItemRepository, CartRepository
from app.modules.catalog.constants import ProductStatus
from app.modules.catalog.repository import (
    ProductImageRepository,
    ProductPriceRepository,
    ProductRepository,
)
from app.modules.catalog.service import serialize_price
from app.modules.identity.constants import BusinessAccountType
from app.modules.procurement.service import ProcurementService
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


def _money_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "to_decimal"):
        return format(value.to_decimal(), "f")
    return str(value)


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if hasattr(value, "to_decimal"):
        return value.to_decimal()
    return Decimal(str(value))


class CartService:
    def __init__(self) -> None:
        self.carts = CartRepository()
        self.items = CartItemRepository()
        self.products = ProductRepository()
        self.prices = ProductPriceRepository()
        self.images = ProductImageRepository()
        self.procurement = ProcurementService()

    def _require_buyer(self, business: dict[str, Any] | None) -> str:
        if business is None or str(business.get("type")) != BusinessAccountType.BUYER:
            raise CartBuyerRequiredError()
        return str(business["_id"])

    async def _ensure_cart(self, buyer_id: str) -> dict[str, Any]:
        existing = await self.carts.get_for_buyer(buyer_id)
        if existing is not None:
            return existing
        now = utc_now()
        return await self.carts.create(
            {
                "buyer_business_id": parse_object_id(buyer_id),
                "created_at": now,
                "updated_at": now,
            }
        )

    async def _serialize_item(self, row: dict[str, Any]) -> dict[str, Any]:
        catalog_price = _money_str(row.get("unit_price"))
        suggested = _money_str(row.get("suggested_unit_price"))
        return {
            "id": str(row["_id"]),
            "product_id": str(row["product_id"]),
            "supplier_business_id": str(row["supplier_business_id"]),
            "supplier_name": row.get("supplier_name"),
            "product_name": row.get("product_name"),
            "sku": row.get("sku"),
            "unit": row.get("unit"),
            "moq": int(row.get("moq") or 1),
            "quantity": int(row["quantity"]),
            "unit_price": catalog_price,
            "suggested_unit_price": suggested if suggested is not None else catalog_price,
            "currency": row.get("currency") or "USD",
            "primary_image_url": row.get("primary_image_url"),
            "line_total": _money_str(row.get("line_total")),
            "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        }

    async def get_cart(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        await self._ensure_cart(buyer_id)
        rows = await self.items.list_for_buyer(buyer_id)
        items = [await self._serialize_item(row) for row in rows]
        currencies = {item["currency"] for item in items if item.get("currency")}
        subtotal: Decimal | None = None
        currency = next(iter(currencies), "USD") if len(currencies) == 1 else None
        if currency:
            subtotal = sum(
                (Decimal(item["line_total"]) for item in items if item.get("line_total")),
                Decimal("0"),
            )
        return {
            "buyer_business_id": buyer_id,
            "item_count": len(items),
            "quantity_total": sum(item["quantity"] for item in items),
            "currency": currency,
            "subtotal": format(subtotal, "f") if subtotal is not None else None,
            "items": items,
        }

    async def _price_snapshot(
        self, product_id: str, quantity: int
    ) -> tuple[Any | None, str]:
        tiers = await self.prices.list_for_product(product_id)
        active = [serialize_price(t) for t in tiers if t.get("is_active", True)]
        match = None
        for tier in sorted(active, key=lambda r: int(r["min_quantity"]), reverse=True):
            lo = int(tier["min_quantity"])
            hi = tier.get("max_quantity")
            if quantity < lo:
                continue
            if hi is not None and quantity > int(hi):
                continue
            match = tier
            break
        if match is None and active:
            match = min(active, key=lambda r: int(r["min_quantity"]))
        if match is None:
            return None, "USD"
        return to_decimal128(_as_decimal(match["unit_price"])), str(match.get("currency") or "USD")

    async def add_item(
        self,
        *,
        business: dict[str, Any] | None,
        product_id: str,
        quantity: int = 1,
        suggested_unit_price: str | None = None,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        product = await self.products.get_by_id(product_id)
        if product is None or str(product.get("status")) != ProductStatus.ACTIVE:
            raise CartProductUnavailableError("Product is not available")
        supplier_id = str(product["business_account_id"])
        if supplier_id == buyer_id:
            raise CartProductUnavailableError("You cannot add your own listings to the cart")

        from app.modules.identity.constants import (
            BusinessAccountStatus,
            SupplierVerificationStatus,
        )
        from app.modules.identity.repository import (
            BusinessRepository,
            SupplierProfileRepository,
        )

        supplier = await BusinessRepository().get_by_id(supplier_id)
        if supplier is None or str(supplier.get("status")) == BusinessAccountStatus.SUSPENDED:
            raise CartProductUnavailableError("Supplier is not available")
        profile = await SupplierProfileRepository().get_by_business(supplier_id)
        if (
            profile is None
            or profile.get("verification_status") != SupplierVerificationStatus.VERIFIED
        ):
            raise CartProductUnavailableError("Supplier is not verified to sell")

        cart = await self._ensure_cart(buyer_id)
        existing = await self.items.get_for_buyer_product(buyer_id, product_id)
        now = utc_now()
        if existing is not None:
            next_qty = int(existing["quantity"]) + quantity
            return await self.update_item(
                business=business,
                item_id=str(existing["_id"]),
                quantity=next_qty,
                suggested_unit_price=suggested_unit_price,
                update_suggested_price=suggested_unit_price is not None,
            )

        moq = max(1, int(product.get("moq") or 1))
        qty = max(quantity, moq)
        unit_price, currency = await self._price_snapshot(product_id, qty)
        suggested = self._parse_suggested(suggested_unit_price)
        if suggested is None and unit_price is not None:
            suggested = unit_price
        line_total = None
        if unit_price is not None:
            line_total = to_decimal128(_as_decimal(unit_price) * Decimal(qty))

        images = await self.images.list_for_product(product_id)
        primary = next((img for img in images if img.get("is_primary")), images[0] if images else None)

        await self.items.create(
            {
                "cart_id": cart["_id"],
                "buyer_business_id": parse_object_id(buyer_id),
                "product_id": parse_object_id(product_id),
                "supplier_business_id": parse_object_id(supplier_id),
                "supplier_name": supplier.get("name") if supplier else None,
                "product_name": product.get("name"),
                "sku": product.get("sku"),
                "unit": product.get("unit") or "unit",
                "moq": moq,
                "quantity": qty,
                "unit_price": unit_price,
                "suggested_unit_price": suggested,
                "currency": currency,
                "line_total": line_total,
                "primary_image_url": primary.get("url") if primary else None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await self.carts.update(cart["_id"], {"updated_at": now})
        return await self.get_cart(business=business)

    async def update_item(
        self,
        *,
        business: dict[str, Any] | None,
        item_id: str,
        quantity: int | None = None,
        suggested_unit_price: str | None = None,
        update_suggested_price: bool = False,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        item = await self.items.get_for_buyer_item(buyer_id, item_id)
        if item is None:
            raise CartItemNotFoundError()
        moq = max(1, int(item.get("moq") or 1))
        qty = max(int(quantity if quantity is not None else item["quantity"]), moq)
        unit_price = item.get("unit_price")
        currency = str(item.get("currency") or "USD")
        if unit_price is None:
            unit_price, currency = await self._price_snapshot(str(item["product_id"]), qty)
        line_total = None
        if unit_price is not None:
            line_total = to_decimal128(_as_decimal(unit_price) * Decimal(qty))
        now = utc_now()
        patch: dict[str, Any] = {
            "quantity": qty,
            "unit_price": unit_price,
            "currency": currency,
            "line_total": line_total,
            "updated_at": now,
        }
        if update_suggested_price:
            parsed = self._parse_suggested(suggested_unit_price)
            patch["suggested_unit_price"] = parsed if parsed is not None else unit_price
        await self.items.update(item["_id"], patch)
        cart = await self.carts.get_for_buyer(buyer_id)
        if cart is not None:
            await self.carts.update(cart["_id"], {"updated_at": now})
        return await self.get_cart(business=business)

    def _parse_suggested(self, value: str | None) -> Any:
        if value is None or str(value).strip() == "":
            return None
        try:
            amount = Decimal(str(value).strip())
        except Exception as exc:
            raise CartInvalidSuggestedPriceError() from exc
        if amount < 0:
            raise CartInvalidSuggestedPriceError()
        return to_decimal128(amount)

    async def remove_item(
        self,
        *,
        business: dict[str, Any] | None,
        item_id: str,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        item = await self.items.get_for_buyer_item(buyer_id, item_id)
        if item is None:
            raise CartItemNotFoundError()
        await self.items.delete(item["_id"])
        cart = await self.carts.get_for_buyer(buyer_id)
        if cart is not None:
            await self.carts.update(cart["_id"], {"updated_at": utc_now()})
        return await self.get_cart(business=business)

    async def clear_cart(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        await self.items.delete_for_buyer(buyer_id)
        cart = await self.carts.get_for_buyer(buyer_id)
        if cart is not None:
            await self.carts.update(cart["_id"], {"updated_at": utc_now()})
        return await self.get_cart(business=business)

    async def checkout(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        title: str | None = None,
        notes: str | None = None,
        publish: bool = False,
        ip: str | None = None,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        rows = await self.items.list_for_buyer(buyer_id)
        if not rows:
            raise CartEmptyError()

        currencies = {str(r.get("currency") or "USD") for r in rows}
        currency = next(iter(currencies)) if len(currencies) == 1 else "USD"
        rfq_items = []
        for row in rows:
            suggested = _money_str(row.get("suggested_unit_price"))
            catalog = _money_str(row.get("unit_price"))
            target = suggested if suggested is not None else catalog
            rfq_items.append(
                {
                    "product_id": str(row["product_id"]),
                    "product_name": row.get("product_name") or "Product",
                    "sku": row.get("sku"),
                    "quantity": str(int(row["quantity"])),
                    "unit": row.get("unit") or "unit",
                    "catalog_unit_price": catalog,
                    "target_unit_price": target,
                    "supplier_business_id": str(row["supplier_business_id"]),
                    "primary_image_url": row.get("primary_image_url"),
                }
            )

        supplier_ids = sorted({str(r["supplier_business_id"]) for r in rows})
        rfq_title = (title or "").strip() or f"Cart request ({len(rows)} item{'s' if len(rows) != 1 else ''})"

        # Single listed product from one supplier → Product RFQ; otherwise Sourcing.
        is_product = (
            len(rows) == 1
            and rows[0].get("product_id") is not None
            and len(supplier_ids) == 1
        )
        if is_product:
            row = rows[0]
            suggested = _money_str(row.get("suggested_unit_price"))
            catalog = _money_str(row.get("unit_price"))
            rfq = await self.procurement.create_product_rfq(
                user_id=user_id,
                business=business,
                payload={
                    "product_id": str(row["product_id"]),
                    "quantity": str(int(row["quantity"])),
                    "unit": row.get("unit") or "unit",
                    "target_unit_price": suggested if suggested is not None else catalog,
                    "notes": notes,
                    "currency": currency,
                    "publish": False,
                },
                ip=ip,
            )
            rfq_id = str(rfq["id"])
            await self.procurement.rfqs.update(
                parse_object_id(rfq_id),
                {
                    "source": "cart",
                    "source_supplier_ids": [parse_object_id(supplier_ids[0])],
                    "title": rfq_title,
                },
            )
        else:
            rfq = await self.procurement.create_rfq(
                user_id=user_id,
                business=business,
                payload={
                    "title": rfq_title,
                    "description": "Created from marketplace cart",
                    "notes": notes,
                    "currency": currency,
                    "visibility": "invited",
                    "rfq_type": "sourcing",
                    "items": rfq_items,
                },
                ip=ip,
            )
            rfq_id = str(rfq["id"])
            await self.procurement.rfqs.update(
                parse_object_id(rfq_id),
                {
                    "source": "cart",
                    "source_supplier_ids": [parse_object_id(sid) for sid in supplier_ids],
                },
            )
        rfq = await self.procurement.get_rfq(
            user_id=user_id,
            business=business,
            rfq_id=rfq_id,
        )
        invited = 0
        invite_error: str | None = None
        sent: list[dict[str, Any]] = []
        if publish:
            try:
                payload = await self.procurement.send_draft_to_product_owners(
                    user_id=user_id,
                    business=business,
                    rfq_id=rfq_id,
                    ip=ip,
                )
                rfq = payload.get("rfq") or rfq
                sent = list(payload.get("sent") or [])
                invited = len(sent)
                rfq_id = str(rfq.get("id") or rfq_id)
            except Exception as exc:
                invite_error = str(getattr(exc, "message", None) or exc)

        # Keep cart lines until payment — RFQ start must not empty the cart.
        return {
            "rfq_id": rfq_id,
            "rfq_number": rfq.get("rfq_number"),
            "status": rfq.get("status"),
            "suppliers_invited": invited,
            "invite_warning": invite_error,
            "cart": await self.get_cart(business=business),
        }

    async def place_orders(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        notes: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Place direct purchase orders from the cart (one PO per supplier)."""
        buyer_id = self._require_buyer(business)
        rows = await self.items.list_for_buyer(buyer_id)
        if not rows:
            raise CartEmptyError()

        by_supplier: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            suggested = _money_str(row.get("suggested_unit_price"))
            catalog = _money_str(row.get("unit_price"))
            price = suggested if suggested is not None else catalog
            if price is None:
                raise CartPriceRequiredError()
            sid = str(row["supplier_business_id"])
            by_supplier.setdefault(sid, []).append(
                {
                    "product_id": str(row["product_id"]),
                    "product_name": row.get("product_name") or "Product",
                    "sku": row.get("sku"),
                    "quantity": str(int(row["quantity"])),
                    "unit": row.get("unit") or "unit",
                    "unit_price": price,
                    "currency": str(row.get("currency") or "USD"),
                }
            )

        orders: list[dict[str, Any]] = []
        for supplier_id, lines in by_supplier.items():
            currencies = {ln["currency"] for ln in lines}
            if len(currencies) != 1:
                raise CartMixedCurrencyError()
            currency = next(iter(currencies))
            order = await self.procurement.create_direct_order_from_cart_lines(
                user_id=user_id,
                business=business,
                supplier_business_id=supplier_id,
                currency=currency,
                lines=lines,
                ip=ip,
            )
            if notes:
                await self.procurement.orders.update(
                    parse_object_id(str(order["id"])),
                    {"notes": notes, "updated_at": utc_now()},
                )
            orders.append(
                {
                    "id": order["id"],
                    "order_number": order.get("order_number"),
                    "supplier_business_id": supplier_id,
                    "total": order.get("total"),
                    "currency": order.get("currency"),
                    "status": order.get("status"),
                }
            )

        return {
            "orders": orders,
            "order_count": len(orders),
            "cart": await self.get_cart(business=business),
        }

    async def remove_products_for_buyer(
        self,
        *,
        buyer_business_id: str,
        product_ids: list[str],
    ) -> int:
        """Drop cart lines for paid products. Returns how many lines were removed."""
        oids = [parse_object_id(pid) for pid in product_ids if pid]
        if not oids:
            return 0
        result = await self.items.collection.delete_many(
            {
                "buyer_business_id": parse_object_id(buyer_business_id),
                "product_id": {"$in": oids},
            }
        )
        removed = int(result.deleted_count)
        if removed:
            cart = await self.carts.get_for_buyer(buyer_business_id)
            if cart is not None:
                await self.carts.update(cart["_id"], {"updated_at": utc_now()})
        return removed
