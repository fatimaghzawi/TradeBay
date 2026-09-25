
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.exceptions import BadRequestError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.catalog.constants import ProductStatus
from app.modules.catalog.repository import ProductPriceRepository, ProductRepository
from app.modules.catalog.service import serialize_price
from app.modules.checkout.constants import MAX_CHECKOUT_LINES, MAX_LINE_QUANTITY
from app.modules.identity.constants import (
    BusinessAccountStatus,
    BusinessAccountType,
    SupplierVerificationStatus,
)
from app.modules.platform_money.commission import as_decimal, money
from app.modules.settings.constants import SINGLETON_KEY


class CheckoutValidationError(BadRequestError):
    pass

@dataclass
class QuoteLine:
    cart_item_id: Any
    product_id: Any
    product_name: str
    sku: str | None
    unit: str
    moq: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    currency: str
    image_url: str | None
    cart_unit_price: Decimal | None

    @property
    def price_changed(self) -> bool:
        return self.cart_unit_price is not None and money(self.cart_unit_price) != self.unit_price

@dataclass
class SupplierGroup:
    supplier_business_id: Any
    supplier_name: str
    currency: str
    lines: list[QuoteLine] = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    discount_total: Decimal = Decimal("0.00")
    charge_total: Decimal = Decimal("0.00")
    tax_total: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    tax_rate: Decimal | None = None
    tax_name: str | None = None

@dataclass
class CheckoutQuote:
    currency: str
    groups: list[SupplierGroup]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal

    @property
    def cart_item_ids(self) -> list[Any]:
        return [ln.cart_item_id for g in self.groups for ln in g.lines]

    @property
    def price_changes(self) -> list[QuoteLine]:
        return [ln for g in self.groups for ln in g.lines if ln.price_changed]

def resolve_tier_price(tiers: list[dict[str, Any]], quantity: int) -> dict[str, Any] | None:
    active = [t for t in tiers if t.get("is_active", True)]
    for tier in sorted(active, key=lambda r: int(r["min_quantity"]), reverse=True):
        lo = int(tier["min_quantity"])
        hi = tier.get("max_quantity")
        if quantity < lo or (hi is not None and quantity > int(hi)):
            continue
        return tier
    if active:
        return min(active, key=lambda r: int(r["min_quantity"]))
    return None

async def build_checkout_quote(*, buyer_business_id: str, cart_rows: list[dict[str, Any]]) -> CheckoutQuote:
    from app.modules.identity.repository import BusinessRepository, SupplierProfileRepository
    from app.modules.procurement.service import _active_tax_settings, _compose_order_money

    if not cart_rows:
        raise CheckoutValidationError("Your cart is empty", details={"reason": "cart_empty"})
    if len(cart_rows) > MAX_CHECKOUT_LINES:
        raise CheckoutValidationError(f"A checkout can include at most {MAX_CHECKOUT_LINES} lines")

    products = ProductRepository()
    prices = ProductPriceRepository()
    businesses = BusinessRepository()
    profiles = SupplierProfileRepository()
    inventories = mongo_manager.collection(CollectionName.INVENTORIES)

    groups: dict[str, SupplierGroup] = {}
    supplier_cache: dict[str, dict[str, Any]] = {}
    currencies: set[str] = set()

    for row in cart_rows:
        product_id = str(row["product_id"])
        product = await products.get_by_id(product_id)
        name = (product or {}).get("name") or row.get("product_name") or "This product"
        if product is None or str(product.get("status")) != ProductStatus.ACTIVE or product.get("deleted_at"):
            raise CheckoutValidationError(f"{name} is no longer available. Remove it from your cart to continue.")

        supplier_id = str(product["business_account_id"])
        if supplier_id == buyer_business_id:
            raise CheckoutValidationError("You can't buy your own listings")
        if supplier_id not in supplier_cache:
            supplier = await businesses.get_by_id(supplier_id)
            if (
                supplier is None
                or str(supplier.get("type")) != BusinessAccountType.SUPPLIER
                or str(supplier.get("status")) == BusinessAccountStatus.SUSPENDED
            ):
                raise CheckoutValidationError(f"The supplier of {name} isn't available right now")
            profile = await profiles.get_by_business(supplier_id)
            if profile is None or profile.get("verification_status") != SupplierVerificationStatus.VERIFIED:
                raise CheckoutValidationError(f"The supplier of {name} isn't verified to sell yet")
            supplier_cache[supplier_id] = supplier

        quantity = int(row.get("quantity") or 0)
        moq = max(1, int(product.get("moq") or 1))
        if quantity < moq:
            raise CheckoutValidationError(f"{name} has a minimum order of {moq} {product.get('unit') or 'units'}")
        if quantity > MAX_LINE_QUANTITY:
            raise CheckoutValidationError(f"Quantity for {name} is too large")

        tiers = [serialize_price(t) for t in await prices.list_for_product(product_id)]
        tier = resolve_tier_price(tiers, quantity)
        if tier is None:
            raise CheckoutValidationError(f"{name} has no price yet. Request a quote instead.")
        unit_price = money(tier["unit_price"])
        if unit_price <= 0:
            raise CheckoutValidationError(f"{name} has no valid price. Request a quote instead.")
        currency = str(tier.get("currency") or "USD").upper()
        currencies.add(currency)

        inventory = await inventories.find_one({"product_id": product["_id"]})
        available = as_decimal((inventory or {}).get("available_quantity"))
        if inventory is None or available < quantity:
            left = format(available.normalize(), "f") if inventory else "0"
            raise CheckoutValidationError(f"Only {left} of {name} left in stock. Lower the quantity to continue.")

        group = groups.get(supplier_id)
        if group is None:
            group = SupplierGroup(
                supplier_business_id=product["business_account_id"],
                supplier_name=supplier_cache[supplier_id].get("name") or "Supplier",
                currency=currency,
            )
            groups[supplier_id] = group
        group.lines.append(
            QuoteLine(
                cart_item_id=row["_id"],
                product_id=product["_id"],
                product_name=product.get("name") or "Product",
                sku=product.get("sku"),
                unit=product.get("unit") or "unit",
                moq=moq,
                quantity=quantity,
                unit_price=unit_price,
                line_total=money(unit_price * quantity),
                currency=currency,
                image_url=row.get("primary_image_url"),
                cart_unit_price=as_decimal(row["unit_price"]) if row.get("unit_price") is not None else None,
            )
        )

    if len(currencies) != 1:
        raise CheckoutValidationError("Items in one checkout must share a currency. Split your cart by currency.")
    currency = next(iter(currencies))

    active_tax = await _active_tax_settings()
    tax_rate = (active_tax or {}).get("rate")
    for group in groups.values():
        group.subtotal = money(sum((ln.line_total for ln in group.lines), Decimal("0")))
        row = _compose_order_money(subtotal=group.subtotal, tax_rate=tax_rate, existing_tax_total="0")
        group.subtotal = money(row["subtotal"])
        group.discount_total = money(row["discount_total"])
        group.charge_total = money(row["charge_total"])
        group.tax_total = money(row["tax_total"])
        group.total = money(row["total"])
        group.tax_rate = row["tax_rate_snapshot"]
        group.tax_name = ((active_tax or {}).get("name") or "VAT") if row["tax_rate_snapshot"] is not None else None

    ordered = sorted(groups.values(), key=lambda g: g.supplier_name.lower())
    quote = CheckoutQuote(
        currency=currency,
        groups=ordered,
        subtotal=money(sum((g.subtotal for g in ordered), Decimal("0"))),
        tax_total=money(sum((g.tax_total for g in ordered), Decimal("0"))),
        total=money(sum((g.total for g in ordered), Decimal("0"))),
    )

    settings = await mongo_manager.collection(CollectionName.PLATFORM_SETTINGS).find_one({"key": SINGLETON_KEY})
    minimum = money((settings or {}).get("minimum_order_value") or 0)
    if minimum > 0 and quote.total < minimum:
        raise CheckoutValidationError(f"The minimum order is {currency} {minimum}")
    return quote

def serialize_quote(quote: CheckoutQuote) -> dict[str, Any]:
    return {
        "currency": quote.currency,
        "supplier_count": len(quote.groups),
        "subtotal": format(quote.subtotal, "f"),
        "tax_total": format(quote.tax_total, "f"),
        "total": format(quote.total, "f"),
        "price_changes": [
            {
                "product_id": str(ln.product_id),
                "product_name": ln.product_name,
                "previous_unit_price": format(money(ln.cart_unit_price), "f") if ln.cart_unit_price is not None else None,
                "unit_price": format(ln.unit_price, "f"),
            }
            for ln in quote.price_changes
        ],
        "groups": [
            {
                "supplier_business_id": str(g.supplier_business_id),
                "supplier_name": g.supplier_name,
                "currency": g.currency,
                "subtotal": format(g.subtotal, "f"),
                "tax_total": format(g.tax_total, "f"),
                "tax_name": g.tax_name,
                "tax_rate": format(g.tax_rate, "f") if g.tax_rate is not None else None,
                "total": format(g.total, "f"),
                "lines": [
                    {
                        "product_id": str(ln.product_id),
                        "product_name": ln.product_name,
                        "sku": ln.sku,
                        "unit": ln.unit,
                        "moq": ln.moq,
                        "quantity": ln.quantity,
                        "unit_price": format(ln.unit_price, "f"),
                        "line_total": format(ln.line_total, "f"),
                        "image_url": ln.image_url,
                    }
                    for ln in g.lines
                ],
            }
            for g in quote.groups
        ],
    }
