
from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.modules.catalog.constants import ProductStatus
from app.modules.checkout.constants import CheckoutStatus
from app.modules.finance.constants import InvoiceStatus, PaymentMethod, PaymentStatus
from app.modules.identity.constants import (
    SYSTEM_ROLE_BUSINESS_ADMIN,
    BusinessAccountStatus,
    BusinessAccountType,
    InvitationStatus,
    MembershipStatus,
    SupplierVerificationStatus,
    UserStatus,
)
from app.modules.negotiation.constants import NegotiationOfferStatus, NegotiationStatus
from app.modules.platform_money.commission import as_decimal, commission_rate, money
from app.modules.platform_money.constants import (
    CommissionStatus,
    SupplierBalanceBucket,
    SupplierLedgerDirection,
    SupplierLedgerEntryType,
)
from app.modules.procurement.constants import OrderStatus, QuotationStatus, RFQStatus, ShipmentStatus
from app.modules.trust.constants import DisputeStatus

PUBLIC_DIR = Path(__file__).resolve().parents[4] / "frontend" / "public"
MONEY_FIELDS = ("subtotal", "tax_total", "total", "amount", "unit_price", "line_total", "commission_amount")
CARD_DATA_KEYS = re.compile(r"card_?number|\bpan\b|cvc|cvv|expiry|exp_month|exp_year", re.I)
PLACEHOLDER_WORDS = re.compile(r"\b(test|demo|lorem|dummy|sample|placeholder)\b", re.I)

class Checker:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.problems: list[str] = []
        self._ids: dict[str, set[Any]] = {}

    def fail(self, message: str) -> None:
        self.problems.append(message)

    async def ids(self, collection: str) -> set[Any]:
        if collection not in self._ids:
            self._ids[collection] = {d["_id"] async for d in self.db[collection].find({}, {"_id": 1})}
        return self._ids[collection]

    async def all(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await self.db[collection].find(query or {}).to_list(length=None)

                                                                            

    async def refs(self, collection: str, field: str, target: str, *, optional: bool = False) -> None:
        known = await self.ids(target)
        async for doc in self.db[collection].find({}, {field: 1}):
            value = doc
            for part in field.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value is None:
                if not optional:
                    self.fail(f"{collection} {doc['_id']}: missing {field}")
                continue
            if value not in known:
                self.fail(f"{collection} {doc['_id']}: {field} → missing {target} {value}")

    async def array_refs(self, collection: str, array: str, field: str, target: str) -> None:
        known = await self.ids(target)
        async for doc in self.db[collection].find({}, {array: 1}):
            for row in doc.get(array) or []:
                if row.get(field) not in known:
                    self.fail(f"{collection} {doc['_id']}: {array}.{field} → missing {target} {row.get(field)}")

    async def references(self) -> None:
        pairs = [
            ("business_memberships", "user_id", "users", False),
            ("business_memberships", "business_account_id", "business_accounts", False),
            ("business_memberships", "role_id", "roles", False),
            ("roles", "business_account_id", "business_accounts", True),
            ("invitations", "business_account_id", "business_accounts", False),
            ("invitations", "role_id", "roles", False),
            ("supplier_profiles", "business_account_id", "business_accounts", False),
            ("supplier_profiles", "verified_by", "users", True),
            ("categories", "parent_category_id", "categories", True),
            ("products", "business_account_id", "business_accounts", False),
            ("products", "category_id", "categories", False),
            ("products", "supplier_id", "supplier_profiles", False),
            ("product_prices", "product_id", "products", False),
            ("product_images", "product_id", "products", False),
            ("inventories", "product_id", "products", False),
            ("inventory_transactions", "inventory_id", "inventories", False),
            ("inventory_transactions", "product_id", "products", False),
            ("rfqs", "buyer_business_id", "business_accounts", False),
            ("rfq_items", "rfq_id", "rfqs", False),
            ("quotations", "rfq_id", "rfqs", False),
            ("quotations", "supplier_id", "business_accounts", False),
            ("quotation_items", "quotation_id", "quotations", False),
            ("negotiations", "rfq_id", "rfqs", False),
            ("negotiations", "quotation_id", "quotations", False),
            ("negotiation_offers", "negotiation_id", "negotiations", False),
            ("negotiation_offers", "parent_offer_id", "negotiation_offers", True),
            ("orders", "buyer_business_id", "business_accounts", False),
            ("orders", "supplier_business_id", "business_accounts", False),
            ("orders", "rfq_id", "rfqs", True),
            ("orders", "quotation_id", "quotations", True),
            ("order_items", "order_id", "orders", False),
            ("order_items", "product_id", "products", True),
            ("customer_invoices", "order_id", "orders", False),
            ("customer_invoices", "checkout_id", "checkouts", True),
            ("payments", "payer_business_id", "business_accounts", False),
            ("checkouts", "buyer_business_id", "business_accounts", False),
            ("checkouts", "payment_id", "payments", False),
            ("shipments", "order_id", "orders", False),
            ("reviews", "order_id", "orders", False),
            ("disputes", "order_id", "orders", False),
            ("conversations", "initiator_business_id", "business_accounts", False),
            ("conversations", "counterparty_business_id", "business_accounts", False),
            ("messages", "conversation_id", "conversations", False),
            ("notifications", "recipient_business_id", "business_accounts", True),
            ("notifications", "recipient_user_id", "users", True),
            ("audit_logs", "user_id", "users", True),
            ("audit_logs", "business_account_id", "business_accounts", True),
            ("commission_records", "order_id", "orders", False),
            ("commission_records", "supplier_business_id", "business_accounts", False),
            ("supplier_ledger_entries", "supplier_business_id", "business_accounts", False),
            ("supplier_ledger_entries", "order_id", "orders", True),
            ("supplier_ledger_entries", "payment_id", "payments", True),
            ("supplier_ledger_entries", "commission_record_id", "commission_records", True),
            ("cart_items", "product_id", "products", False),
            ("sourcing_requests", "buyer_business_id", "business_accounts", False),
            ("sourcing_recommendations", "product_id", "products", True),
            ("sourcing_recommendations", "sourcing_request_id", "sourcing_requests", False),
            ("business_plans", "user_id", "users", False),
        ]
        for collection, field, target, optional in pairs:
            await self.refs(collection, field, target, optional=optional)
        await self.array_refs("payments", "allocations", "invoice_id", "customer_invoices")
        await self.array_refs("checkouts", "groups", "order_id", "orders")
        await self.array_refs("checkouts", "groups", "invoice_id", "customer_invoices")

                                                                            

    async def enums(self) -> None:
        specs: list[tuple[str, str, type[StrEnum]]] = [
            ("users", "status", UserStatus),
            ("business_accounts", "status", BusinessAccountStatus),
            ("business_accounts", "type", BusinessAccountType),
            ("business_memberships", "status", MembershipStatus),
            ("invitations", "status", InvitationStatus),
            ("supplier_profiles", "verification_status", SupplierVerificationStatus),
            ("products", "status", ProductStatus),
            ("rfqs", "status", RFQStatus),
            ("quotations", "status", QuotationStatus),
            ("negotiations", "status", NegotiationStatus),
            ("negotiation_offers", "status", NegotiationOfferStatus),
            ("orders", "status", OrderStatus),
            ("shipments", "status", ShipmentStatus),
            ("customer_invoices", "status", InvoiceStatus),
            ("payments", "status", PaymentStatus),
            ("payments", "payment_method", PaymentMethod),
            ("checkouts", "status", CheckoutStatus),
            ("commission_records", "status", CommissionStatus),
            ("supplier_ledger_entries", "entry_type", SupplierLedgerEntryType),
            ("supplier_ledger_entries", "direction", SupplierLedgerDirection),
            ("supplier_ledger_entries", "bucket", SupplierBalanceBucket),
            ("disputes", "status", DisputeStatus),
        ]
        for collection, field, enum in specs:
            allowed = {e.value for e in enum}
            async for doc in self.db[collection].find({}, {field: 1}):
                if str(doc.get(field)) not in allowed:
                    self.fail(f"{collection} {doc['_id']}: {field}={doc.get(field)!r} not a valid {enum.__name__}")

    async def uniques(self) -> None:
        for collection, field in (
            ("users", "email"),
            ("business_accounts", "name"),
            ("products", "sku"),
            ("products", "slug"),
            ("categories", "slug"),
            ("rfqs", "rfq_number"),
            ("orders", "order_number"),
            ("customer_invoices", "invoice_number"),
            ("checkouts", "checkout_number"),
            ("payments", "payment_reference"),
            ("shipments", "shipment_number"),
            ("supplier_ledger_entries", "idempotency_key"),
        ):
            counts = Counter([d.get(field) async for d in self.db[collection].find({}, {field: 1})])
            for value, count in counts.items():
                if value is not None and count > 1:
                    self.fail(f"{collection}.{field} duplicated: {value!r} x{count}")
        reviews = Counter([d.get("order_id") async for d in self.db["reviews"].find({}, {"order_id": 1})])
        for order_id, count in reviews.items():
            if count > 1:
                self.fail(f"order {order_id} has {count} reviews")

                                                                            

    def no_float(self, collection: str, doc: dict[str, Any]) -> None:
        for field in MONEY_FIELDS:
            if isinstance(doc.get(field), float):
                self.fail(f"{collection} {doc['_id']}: {field} stored as float")

    async def money_checks(self) -> None:
        items_by_order: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for item in await self.all("order_items"):
            self.no_float("order_items", item)
            qty, price = as_decimal(item["quantity"]), as_decimal(item["unit_price"])
            if money(qty * price) != money(item["subtotal"]):
                self.fail(f"order_item {item['_id']}: subtotal {item['subtotal']} != {qty} x {price}")
            expected_line = money(
                as_decimal(item["subtotal"]) - as_decimal(item.get("discount_snapshot")) + as_decimal(item.get("tax_snapshot"))
            )
            if money(item["line_total"]) not in {expected_line, money(item["subtotal"]) - money(item.get("discount_snapshot"))}:
                self.fail(f"order_item {item['_id']}: line_total {item['line_total']} does not reconcile")
            items_by_order[item["order_id"]].append(item)

        orders = {o["_id"]: o for o in await self.all("orders")}
        for order in orders.values():
            self.no_float("orders", order)
            items = items_by_order.get(order["_id"], [])
            if not items:
                self.fail(f"order {order['order_number']}: has no line items")
                continue
            if money(sum(as_decimal(i["subtotal"]) for i in items)) != money(order["subtotal"]):
                self.fail(f"order {order['order_number']}: subtotal != sum of line subtotals")
            expected_total = money(
                as_decimal(order["subtotal"])
                - as_decimal(order.get("discount_total"))
                + as_decimal(order.get("charge_total"))
                + as_decimal(order["tax_total"])
            )
            if expected_total != money(order["total"]):
                self.fail(f"order {order['order_number']}: total {order['total']} != {expected_total}")
            history = [h.get("changed_at") for h in order.get("status_history") or [] if h.get("changed_at")]
            if history != sorted(history):
                self.fail(f"order {order['order_number']}: status history is not chronological")

        invoices = {i["_id"]: i for i in await self.all("customer_invoices")}
        platform = await self.db["business_accounts"].find_one({"type": BusinessAccountType.PLATFORM})
        staff = {
            m["user_id"]
            for m in await self.all("business_memberships", {"business_account_id": (platform or {}).get("_id")})
        }
        paid_by_invoice: dict[Any, Decimal] = defaultdict(lambda: Decimal("0"))
        for pay in await self.all("payments"):
            self.no_float("payments", pay)
            for key in pay:
                if CARD_DATA_KEYS.search(key):
                    self.fail(f"payment {pay['payment_reference']}: stores card field {key!r}")
            allocated = money(sum(as_decimal(a.get("allocated_amount")) for a in pay.get("allocations") or []))
            if allocated != money(pay["amount"]):
                self.fail(f"payment {pay['payment_reference']}: allocations {allocated} != amount {pay['amount']}")
            if pay["status"] == PaymentStatus.COMPLETED:
                if not pay.get("paid_at"):
                    self.fail(f"payment {pay['payment_reference']}: completed without paid_at")
                for alloc in pay.get("allocations") or []:
                    paid_by_invoice[alloc["invoice_id"]] += as_decimal(alloc.get("allocated_amount"))
                if pay.get("payment_method") == PaymentMethod.CARD and not str(pay.get("provider_payment_id") or "").startswith("pi_demo_"):
                    self.fail(f"payment {pay['payment_reference']}: seeded card payment lacks a pi_demo_ id")
                if pay.get("payment_method") == PaymentMethod.CASH and pay.get("confirmed_by_user_id") not in staff:
                    self.fail(f"payment {pay['payment_reference']}: cash completed without TradeBay staff confirmation")

        for inv in invoices.values():
            self.no_float("customer_invoices", inv)
            order = orders.get(inv["order_id"])
            if order and money(order["total"]) != money(inv["total"]):
                self.fail(f"invoice {inv['invoice_number']}: total {inv['total']} != order total {order['total']}")
            lines = inv.get("lines") or []
            if lines:
                line_sum = money(sum(as_decimal(ln.get("line_total") or ln.get("subtotal")) for ln in lines))
                if line_sum not in {money(inv["subtotal"]), money(inv["total"])}:
                    self.fail(f"invoice {inv['invoice_number']}: lines sum {line_sum} does not reconcile")
            paid = money(paid_by_invoice.get(inv["_id"], Decimal("0")))
            total = money(inv["total"])
            if paid > total:
                self.fail(f"invoice {inv['invoice_number']}: overpaid {paid} > {total}")
            if inv["status"] == InvoiceStatus.PAID and paid != total:
                self.fail(f"invoice {inv['invoice_number']}: marked paid but only {paid} of {total} received")
            if paid == total and total > 0 and inv["status"] != InvoiceStatus.PAID:
                self.fail(f"invoice {inv['invoice_number']}: fully paid but status {inv['status']}")

        for checkout in await self.all("checkouts"):
            groups = checkout.get("groups") or []
            if money(sum(as_decimal(g.get("total")) for g in groups)) != money(checkout["total"]):
                self.fail(f"checkout {checkout['checkout_number']}: total != sum of supplier groups")
            suppliers = [g.get("supplier_business_id") for g in groups]
            if len(suppliers) != len(set(suppliers)):
                self.fail(f"checkout {checkout['checkout_number']}: supplier split into duplicate orders")
            for g in groups:
                order = orders.get(g["order_id"])
                inv = invoices.get(g.get("invoice_id"))
                if order is None or inv is None:
                    continue
                if order["supplier_business_id"] != g["supplier_business_id"] or inv["order_id"] != order["_id"]:
                    self.fail(f"checkout {checkout['checkout_number']}: group links mismatch for {g.get('order_number')}")
                if money(g.get("total")) != money(order["total"]):
                    self.fail(f"checkout {checkout['checkout_number']}: group total != order {order['order_number']}")

                                                                            

    async def inventory(self) -> None:
        txs: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for tx in await self.db["inventory_transactions"].find({}).sort("_id", 1).to_list(length=None):
            txs[tx["inventory_id"]].append(tx)
        for inv in await self.all("inventories"):
            rows = txs.get(inv["_id"], [])
            if not rows:
                self.fail(f"inventory {inv['_id']}: no transactions")
                continue
            avail, reserved = Decimal("0"), Decimal("0")
            for tx in rows:
                if as_decimal(tx["previous_available"]) != avail or as_decimal(tx["previous_reserved"]) != reserved:
                    self.fail(f"inventory {inv['_id']}: transaction {tx['_id']} breaks the running balance")
                avail, reserved = as_decimal(tx["new_available"]), as_decimal(tx["new_reserved"])
                if avail < 0 or reserved < 0:
                    self.fail(f"inventory {inv['_id']}: negative stock after {tx['_id']}")
            if avail != as_decimal(inv["available_quantity"]) or reserved != as_decimal(inv["reserved_quantity"]):
                self.fail(
                    f"inventory {inv['_id']}: stored {inv['available_quantity']}/{inv['reserved_quantity']} "
                    f"!= replayed {avail}/{reserved}"
                )

                                                                            

    async def commissions(self) -> None:
        settings = await self.db["platform_settings"].find_one({}) or {}
        configured = commission_rate(settings.get("commission_rate")) if settings.get("commission_rate") is not None else None
        fee_rows = {
            r["commission_record_id"]: r
            for r in await self.all("supplier_ledger_entries", {"entry_type": SupplierLedgerEntryType.PLATFORM_FEE})
        }
        for rec in await self.all("commission_records"):
            rate = commission_rate(rec["rate"])
            if configured is not None and rate != configured:
                self.fail(f"commission {rec['_id']}: rate {rate} != platform setting {configured}")
            expected = money(as_decimal(rec["base_amount"]) * rate)
            if money(rec["commission_amount"]) != min(expected, money(rec["gross_amount"])):
                self.fail(f"commission {rec['_id']}: amount {rec['commission_amount']} != {expected}")
            if money(rec["net_amount"]) != money(as_decimal(rec["gross_amount"]) - as_decimal(rec["commission_amount"])):
                self.fail(f"commission {rec['_id']}: net != gross - commission")
            if rec["status"] == CommissionStatus.RECOGNIZED:
                row = fee_rows.get(rec["_id"])
                if money(rec["commission_amount"]) > 0 and (row is None or money(row["amount"]) != money(rec["commission_amount"])):
                    self.fail(f"commission {rec['_id']}: recognized without a matching platform-fee ledger entry")

    async def ledger(self) -> dict[str, Any]:
        balances: dict[str, Any] = {}
        suppliers = await self.all("business_accounts", {"type": BusinessAccountType.SUPPLIER})
        payments = {p["_id"]: p for p in await self.all("payments")}
        for sup in suppliers:
            rows = await self.all("supplier_ledger_entries", {"supplier_business_id": sup["_id"]})
            bucket: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for row in rows:
                if as_decimal(row["amount"]) < 0:
                    self.fail(f"ledger {row['_id']}: negative amount")
                sign = 1 if row["direction"] == SupplierLedgerDirection.CREDIT else -1
                bucket[row["bucket"]] += sign * as_decimal(row["amount"])
                if row["entry_type"] == SupplierLedgerEntryType.SALE:
                    pay = payments.get(row.get("payment_id"))
                    if pay is None or pay["status"] != PaymentStatus.COMPLETED:
                        self.fail(f"ledger {row['_id']}: sale credited without a completed buyer payment")
            for name, value in bucket.items():
                if value < 0:
                    self.fail(f"supplier {sup['name']}: {name} balance negative ({value})")
            if rows:
                balances[sup["name"]] = {
                    "pending": format(money(bucket[SupplierBalanceBucket.PENDING]), "f"),
                    "available": format(money(bucket[SupplierBalanceBucket.AVAILABLE]), "f"),
                }
        return balances

                                                                            

    async def access(self) -> None:
        roles = {r["_id"]: r for r in await self.all("roles")}
        admins: Counter[Any] = Counter()
        for m in await self.all("business_memberships"):
            role = roles.get(m["role_id"])
            if role and role.get("business_account_id") not in {None, m["business_account_id"]}:
                self.fail(f"membership {m['_id']}: role belongs to another business")
            if role and m["status"] == MembershipStatus.ACTIVE and role.get("name") in {SYSTEM_ROLE_BUSINESS_ADMIN, "Platform Admin"}:
                admins[m["business_account_id"]] += 1
        for biz in await self.all("business_accounts"):
            if admins[biz["_id"]] == 0:
                self.fail(f"business {biz['name']}: no active administrator")

        profiles = {p["business_account_id"]: p for p in await self.all("supplier_profiles")}
        for product in await self.all("products", {"status": ProductStatus.ACTIVE}):
            profile = profiles.get(product["business_account_id"])
            if profile is None or profile["verification_status"] != SupplierVerificationStatus.VERIFIED:
                self.fail(f"product {product['sku']}: active but supplier is not verified")
        for profile in profiles.values():
            if profile["verification_status"] == SupplierVerificationStatus.VERIFIED:
                approved = await self.db["audit_logs"].find_one(
                    {"resource_id": profile["_id"], "action": "SUPPLIER_VERIFICATION_APPROVED"}
                )
                if not profile.get("verified_by") or approved is None:
                    self.fail(f"supplier profile {profile['_id']}: verified without a review record")
        for order in await self.all("orders", {"supplier_business_id": {"$nin": [p for p in profiles]}}):
            self.fail(f"order {order['order_number']}: supplier has no supplier profile")

        orders = {o["_id"]: o for o in await self.all("orders")}
        for review in await self.all("reviews"):
            order = orders.get(review["order_id"])
            if order is None:
                continue
            if order["status"] not in {OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.DISPUTED}:
                self.fail(f"review {review['_id']}: order {order['order_number']} not delivered")
            reviewer = review.get("buyer_business_id") or review.get("reviewer_business_id")
            if reviewer is not None and reviewer != order["buyer_business_id"]:
                self.fail(f"review {review['_id']}: left by a company that isn't the buyer")

                                                                            

    def image(self, where: str, url: Any, *, required: bool) -> None:
        if not url:
            if required:
                self.fail(f"{where}: missing image")
            return
        text = str(url)
        if not text.startswith("/images/") or any(bad in text.lower() for bad in ("localhost", "blob:", "/tmp", "http")):
            self.fail(f"{where}: image {text!r} is not a committed static asset")
            return
        if not (PUBLIC_DIR / text.lstrip("/")).is_file():
            self.fail(f"{where}: image file {text} does not exist in frontend/public")

    async def images_and_names(self) -> None:
        with_image = {d["product_id"] for d in await self.all("product_images")}
        for img in await self.all("product_images"):
            self.image(f"product_image {img['_id']}", img.get("url"), required=True)
        for product in await self.all("products"):
            if product["_id"] not in with_image:
                self.fail(f"product {product['sku']}: no image")
            if PLACEHOLDER_WORDS.search(product["name"]):
                self.fail(f"product {product['sku']}: placeholder wording in name")
        for cat in await self.all("categories"):
            self.image(f"category {cat['slug']}", cat.get("image_url"), required=True)
        for biz in await self.all("business_accounts"):
            self.image(f"business {biz['name']} logo", biz.get("logo_url"), required=True)
            self.image(f"business {biz['name']} cover", biz.get("cover_url"), required=False)
            if PLACEHOLDER_WORDS.search(biz["name"]):
                self.fail(f"business {biz['name']}: placeholder wording in name")
        for user in await self.all("users"):
            self.image(f"user {user['email']} avatar", user.get("avatar_url"), required=False)
            if PLACEHOLDER_WORDS.search(f"{user.get('first_name')} {user.get('last_name')}"):
                self.fail(f"user {user['email']}: placeholder name")

async def verify_seed(db: Any) -> tuple[list[str], dict[str, Any]]:
    check = Checker(db)
    await check.references()
    await check.enums()
    await check.uniques()
    await check.money_checks()
    await check.inventory()
    await check.commissions()
    balances = await check.ledger()
    await check.access()
    await check.images_and_names()

    per_supplier = Counter()
    names = {b["_id"]: b["name"] for b in await check.all("business_accounts")}
    for p in await check.all("products"):
        per_supplier[names.get(p["business_account_id"], "?")] += 1
    summary: dict[str, Any] = {
        name: await db[name].count_documents({})
        for name in (
            "users", "business_accounts", "business_memberships", "categories", "products",
            "rfqs", "quotations", "negotiations", "negotiation_offers", "checkouts", "orders",
            "shipments", "customer_invoices", "payments", "commission_records",
            "supplier_ledger_entries", "reviews", "disputes", "conversations", "messages",
            "notifications", "audit_logs", "sourcing_requests", "business_plans",
        )
    }
    summary["subcategories"] = await db["categories"].count_documents({"parent_category_id": {"$ne": None}})
    summary["products per supplier"] = f"{min(per_supplier.values())}-{max(per_supplier.values())}"
    for status in OrderStatus:
        count = await db["orders"].count_documents({"status": status.value})
        if count:
            summary[f"orders {status.value}"] = count
    for name, bal in balances.items():
        summary[f"balance {name}"] = f"pending {bal['pending']} / available {bal['available']}"
    return check.problems, summary

async def _main() -> int:
    from _reset_demo_seed import _load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient

    _load_dotenv()
    from app.core.config import get_settings

    cfg = get_settings()
    client: AsyncIOMotorClient = AsyncIOMotorClient(cfg.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=30000)
    problems, summary = await verify_seed(client[cfg.mongodb_database])
    client.close()
    for key, value in summary.items():
        print(f"  {key:<28} {value}")
    for problem in problems:
        print(f"  - {problem}")
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0

if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_main()))
