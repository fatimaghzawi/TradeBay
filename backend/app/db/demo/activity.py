
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.ai.provider import StubAIProvider
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai_sourcing.service import AISourcingService
from app.modules.business_planner.service import BusinessPlannerService
from app.modules.cart.service import CartService
from app.modules.checkout.gateway import IntentResult, set_payment_gateway
from app.modules.checkout.payments import confirm_offline_payment
from app.modules.checkout.service import CheckoutService
from app.modules.communication.constants import ConversationType, MessageType
from app.modules.communication.service import CommunicationService
from app.modules.finance.service import FinanceService
from app.modules.negotiation.service import NegotiationService
from app.modules.procurement.commercial import money, quantize
from app.modules.procurement.constants import ShipmentStatus
from app.modules.procurement.service import ProcurementService
from app.modules.settings.tax import compute_tax
from app.modules.trust.service import TrustService
from app.shared.utils.datetime import set_seed_clock, utc_now
from app.shared.utils.objectid import parse_object_id

TAX_RATE = Decimal("0.11")

STAGES = ("pending", "confirmed", "shipped", "in_transit", "out_for_delivery", "delivered", "received")

class DemoCardGateway:

    provider = "stripe"

    def __init__(self) -> None:
        self.intents: dict[str, IntentResult] = {}

    def is_configured(self) -> bool:
        return True

    def publishable_key(self) -> str | None:
        return None

    async def create_intent(
        self, *, amount_minor: int, currency: str, idempotency_key: str, metadata: dict[str, str]
    ) -> IntentResult:
        intent_id = "pi_demo_" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]
        intent = IntentResult(
            id=intent_id,
            status="succeeded",
            amount_minor=amount_minor,
            currency=currency.upper(),
            client_secret=f"{intent_id}_secret_demo",
            metadata=dict(metadata),
        )
        self.intents[intent_id] = intent
        return IntentResult(
            id=intent_id,
            status="requires_payment_method",
            amount_minor=amount_minor,
            currency=currency.upper(),
            client_secret=f"{intent_id}_secret_demo",
            metadata=dict(metadata),
        )

    async def retrieve_intent(self, intent_id: str) -> IntentResult:
        return self.intents[intent_id]

    async def cancel_intent(self, intent_id: str) -> IntentResult:
        old = self.intents[intent_id]
        self.intents[intent_id] = IntentResult(
            id=old.id, status="canceled", amount_minor=old.amount_minor, currency=old.currency, metadata=old.metadata
        )
        return self.intents[intent_id]

def _biz(doc: dict[str, Any]) -> dict[str, Any]:
    return {"_id": doc["_id"], "type": doc["type"], "name": doc.get("name")}

def _dest(city: str, governorate: str) -> dict[str, str]:
    streets = {
        "Beirut": ("Hamra Street 42, Picard Building", "Ras Beirut", "1103"),
        "Zahle": ("Boulevard Street 19, Midan", "Zahle", "1801"),
        "Nabatieh": ("Main Square, Co-op Building", "Nabatieh", "1700"),
        "Jounieh": ("Maameltein Bay, Hotel House 3", "Keserwan", "1401"),
        "Tripoli": ("Syriac Street, Mina, Shop 12", "Mina", "1301"),
        "Tyre": ("Al-Jalil Street, Kitchen Compound", "Tyre", "1601"),
    }
    street, district, postal = streets.get(city, (f"{city} commercial street", city, "00000"))
    return {
        "street": street,
        "city": city,
        "district": district,
        "governorate": governorate,
        "postal_code": postal,
        "country": "Lebanon",
    }

async def _product_by_sku(sku: str) -> dict[str, Any]:
    row = await mongo_manager.collection(CollectionName.PRODUCTS).find_one({"sku": sku})
    if row is None:
        raise RuntimeError(f"Seed product missing: {sku}")
    return row

async def _tier_price(product_id: Any, quantity: str) -> str:
    qty = money(quantity)
    tiers = (
        await mongo_manager.collection(CollectionName.PRODUCT_PRICES)
        .find({"product_id": product_id, "is_active": True, "deleted_at": None})
        .sort("min_quantity", 1)
        .to_list(length=20)
    )
    chosen = None
    for tier in tiers:
        lo = int(tier.get("min_quantity") or 1)
        hi = tier.get("max_quantity")
        if qty >= lo and (hi is None or qty <= int(hi)):
            chosen = tier
    if chosen is None and tiers:
        chosen = tiers[0]
    if chosen is None:
        raise RuntimeError("Product has no price tiers")
    return format(money(chosen["unit_price"]), "f")

class Timeline:

    def __init__(self) -> None:
        self.origin = utc_now()

    def at(self, days_ago: float) -> datetime:
        moment = self.origin - timedelta(days=days_ago)
        set_seed_clock(moment)
        return moment

class Party:
    def __init__(self, business: dict[str, Any], user: dict[str, Any]) -> None:
        self.business = business
        self.user = user

    @property
    def biz(self) -> dict[str, Any]:
        return _biz(self.business)

    @property
    def uid(self) -> str:
        return str(self.user["_id"])

    @property
    def bid(self) -> str:
        return str(self.business["_id"])

class ActivitySeeder:
    def __init__(self, *, platform: Party) -> None:
        self.t = Timeline()
        self.platform = platform
        self.proc = ProcurementService()
        self.neg = NegotiationService()
        self.comm = CommunicationService()
        self.cart = CartService()
        self.checkout = CheckoutService()
        self.finance = FinanceService()
        self.trust = TrustService()

                                                                            

    async def fulfil(
        self,
        *,
        order_id: str,
        supplier: Party,
        buyer: Party,
        start: float,
        stage: str,
        carrier: str = "Liban Post Business",
    ) -> None:
        reached = STAGES.index(stage)
        if reached < 1:
            return
        self.t.at(start - 0.15)
        order = await self.proc.acknowledge_order(user_id=supplier.uid, business=supplier.biz, order_id=order_id)
        if reached < 2:
            return
        self.t.at(start - 0.9)
        shipment = await self.proc.create_shipment(
            user_id=supplier.uid,
            business=supplier.biz,
            order_id=order_id,
            payload={
                "carrier_name": carrier,
                "tracking_number": f"LB{str(order['order_number'])[-6:].replace('-', '')}{int(start * 10):04d}",
                "origin": "Lebanon",
                "lines": [{"order_item_id": i["id"], "quantity": i["quantity"]} for i in order["items"]],
            },
        )
        journey = (
            ("in_transit", ShipmentStatus.IN_TRANSIT, 1.3, "Sorting hub", "Left the regional sorting hub"),
            ("out_for_delivery", ShipmentStatus.OUT_FOR_DELIVERY, 1.8, "Local depot", "Out with the delivery driver"),
            ("delivered", ShipmentStatus.DELIVERED, 2.1, "Buyer site", "Delivered and signed for at reception"),
        )
        for name, status, offset, location, note in journey:
            if reached < STAGES.index(name):
                return
            self.t.at(start - offset)
            shipment = await self.proc.add_tracking_event(
                user_id=supplier.uid,
                business=supplier.biz,
                shipment_id=shipment["id"],
                payload={"status": status, "location": location, "description": note},
            )
        if reached < STAGES.index("received"):
            return
        self.t.at(start - 2.3)
        await self.proc.receive_shipment(
            user_id=buyer.uid,
            business=buyer.biz,
            shipment_id=shipment["id"],
            payload={
                "notes": "Counted and checked on arrival.",
                "lines": [
                    {
                        "order_item_id": i["id"],
                        "received_quantity": i["quantity"],
                        "damaged_quantity": "0",
                        "missing_quantity": "0",
                        "rejected_quantity": "0",
                    }
                    for i in order["items"]
                ],
            },
        )

    async def pay_invoice(self, *, order_id: str, buyer: Party, days_ago: float, confirm: bool) -> None:
        invoice = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"order_id": parse_object_id(order_id)}
        )
        if invoice is None:
            raise RuntimeError(f"No invoice for order {order_id}")
        self.t.at(days_ago)
        payment = await self.finance.record_payment(
            user_id=buyer.uid,
            business=buyer.biz,
            invoice_id=str(invoice["_id"]),
            amount=format(money(invoice["total"]), "f"),
            payment_method="manual",
            reference=f"BLOM-TRF-{str(invoice['invoice_number'])[-5:]}",
            complete=False,
        )
        if confirm:
            self.t.at(days_ago - 0.4)
            await self.finance.complete_payment(
                user_id=self.platform.uid, business=self.platform.biz, payment_id=payment["payment_id"]
            )

    async def review(self, *, order_id: str, buyer: Party, days_ago: float, rating: int, comment: str) -> None:
        self.t.at(days_ago)
        await self.trust.create_review(
            user_id=buyer.uid, business=buyer.biz, order_id=order_id, rating=rating, comment=comment
        )

                                                                            

    async def quote(
        self,
        *,
        rfq: dict[str, Any],
        supplier: Party,
        unit_price: str,
        notes: str,
        lead_days: int = 5,
        payment_terms: str = "Net 30",
    ) -> dict[str, Any]:
        item = rfq["items"][0]
        line_sub = quantize(money(item["quantity"]) * money(unit_price))
        tax = compute_tax(subtotal=line_sub, rate=TAX_RATE)["tax_amount"]
        return await self.proc.upsert_quotation(
            user_id=supplier.uid,
            business=supplier.biz,
            rfq_id=rfq["id"],
            payload={
                "payment_terms": payment_terms,
                "delivery_terms": "Delivered to buyer site",
                "currency": "USD",
                "notes": notes,
                "document_tax": "0",
                "lines": [
                    {
                        "rfq_item_id": item["id"],
                        "quantity": item["quantity"],
                        "unit_price": unit_price,
                        "moq": 1,
                        "lead_time_days": lead_days,
                        "tax": format(tax, "f"),
                    }
                ],
            },
            submit=True,
        )

    async def product_deal(
        self,
        *,
        buyer: Party,
        supplier: Party,
        sku: str,
        qty: str,
        requirements: str,
        quote_note: str,
        dest: dict[str, str],
        start: float,
        stage: str | None = None,
        negotiate: tuple[str, str] | None = None,
        negotiation_open: str | None = None,
        reject_reason: str | None = None,
        pay: str | None = None,
        review: tuple[int, str] | None = None,
    ) -> dict[str, Any]:
        product = await _product_by_sku(sku)
        self.t.at(start)
        rfq = await self.proc.create_product_rfq(
            user_id=buyer.uid,
            business=buyer.biz,
            payload={
                "product_id": str(product["_id"]),
                "quantity": qty,
                "unit": product.get("unit") or "unit",
                "requirements": requirements,
                "publish": True,
                "destination": dest,
            },
        )
        self.t.at(start - 0.3)
        list_price = await _tier_price(product["_id"], qty)
        quote = await self.quote(rfq=rfq, supplier=supplier, unit_price=list_price, notes=quote_note)
        if reject_reason:
            self.t.at(start - 0.8)
            await self.proc.reject_quotation(
                user_id=buyer.uid, business=buyer.biz, quotation_id=quote["id"], reason=reject_reason
            )
            return {"rfq": rfq, "quote": quote, "order": None}
        if negotiate or negotiation_open:
            await self.negotiate(
                rfq=rfq,
                quote=quote,
                buyer=buyer,
                supplier=supplier,
                start=start - 0.5,
                buyer_price=(negotiate or (negotiation_open, ""))[0],
                supplier_price=negotiate[1] if negotiate else None,
            )
            if negotiation_open:
                return {"rfq": rfq, "quote": quote, "order": None}
        if stage is None:
            return {"rfq": rfq, "quote": quote, "order": None}
        self.t.at(start - 1.2)
        order = await self.proc.award(
            user_id=buyer.uid, business=buyer.biz, rfq_id=rfq["id"], quotation_id=quote["id"], confirm=True
        )
        await self.fulfil(order_id=order["id"], supplier=supplier, buyer=buyer, start=start - 1.4, stage=stage)
        if pay:
            await self.pay_invoice(order_id=order["id"], buyer=buyer, days_ago=start - 4.2, confirm=pay == "confirmed")
        if review:
            await self.review(order_id=order["id"], buyer=buyer, days_ago=start - 4.8, rating=review[0], comment=review[1])
        return {"rfq": rfq, "quote": quote, "order": order}

    async def negotiate(
        self,
        *,
        rfq: dict[str, Any],
        quote: dict[str, Any],
        buyer: Party,
        supplier: Party,
        start: float,
        buyer_price: str,
        supplier_price: str | None,
    ) -> None:
        item = rfq["items"][0]
        self.t.at(start)
        neg = await self.neg.open(user_id=buyer.uid, business=buyer.biz, rfq_id=rfq["id"], quotation_id=quote["id"])
        self.t.at(start - 0.05)
        await self.neg.propose_offer(
            user_id=buyer.uid,
            business=buyer.biz,
            negotiation_id=neg["id"],
            lines=[{"rfq_item_id": item["id"], "quantity": item["quantity"], "unit_price": buyer_price}],
            payment_terms="Net 30",
        )
        if supplier_price is None:
            return
        buyer_offer = await self._latest_offer(neg["id"])
        self.t.at(start - 0.2)
        await self.neg.propose_offer(
            user_id=supplier.uid,
            business=supplier.biz,
            negotiation_id=neg["id"],
            lines=[{"rfq_item_id": item["id"], "quantity": item["quantity"], "unit_price": supplier_price}],
            payment_terms="Net 30",
            parent_offer_id=str(buyer_offer["_id"]),
        )
        supplier_offer = await self._latest_offer(neg["id"])
        self.t.at(start - 0.4)
        await self.neg.accept_offer(
            user_id=buyer.uid, business=buyer.biz, negotiation_id=neg["id"], offer_id=str(supplier_offer["_id"])
        )

    async def _latest_offer(self, negotiation_id: str) -> dict[str, Any]:
        offer = await mongo_manager.collection(CollectionName.NEGOTIATION_OFFERS).find_one(
            {"negotiation_id": parse_object_id(negotiation_id)}, sort=[("created_at", -1)]
        )
        if offer is None:
            raise RuntimeError("Negotiation offer missing")
        return offer

    async def sourcing_rfq(
        self,
        *,
        buyer: Party,
        title: str,
        description: str,
        qty: str,
        unit: str,
        product_name: str,
        dest: dict[str, str],
        start: float,
    ) -> dict[str, Any]:
        self.t.at(start)
        return await self.proc.create_sourcing_rfq(
            user_id=buyer.uid,
            business=buyer.biz,
            payload={
                "title": title,
                "description": description,
                "quantity": qty,
                "unit": unit,
                "product_name": product_name,
                "visibility": "open",
                "publish": True,
                "destination": dest,
            },
        )

                                                                            

    async def cart_checkout(
        self,
        *,
        buyer: Party,
        lines: list[tuple[str, int]],
        method: str,
        start: float,
        notes: str,
        paid: bool = True,
    ) -> dict[str, Any]:
        self.t.at(start + 0.05)
        await self.cart.clear_cart(business=buyer.biz)
        for sku, qty in lines:
            product = await _product_by_sku(sku)
            await self.cart.add_item(business=buyer.biz, product_id=str(product["_id"]), quantity=qty)
        preview = await self.checkout.preview(business=buyer.biz)
        self.t.at(start)
        placed = await self.checkout.place(
            user_id=buyer.uid,
            business=buyer.biz,
            payment_method=method,
            idempotency_key=f"seed-{buyer.bid}-{int(start * 100)}",
            expected_total=preview["total"],
            notes=notes,
        )
        if method == "card" and paid:
            self.t.at(start - 0.01)
            await self.checkout.start_card_payment(business=buyer.biz, checkout_id=placed["id"])
            self.t.at(start - 0.02)
            placed = await self.checkout.refresh_payment(business=buyer.biz, checkout_id=placed["id"])
        elif method == "card":
                                                                                       
                                                                   
            await mongo_manager.database[CollectionName.PAYMENTS].update_one(
                {"_id": parse_object_id(placed["payment"]["id"]), "status": "pending"},
                {"$set": {"provider_payment_id": None}},
            )
        return placed

    async def confirm_cash(self, checkout: dict[str, Any], *, days_ago: float) -> None:
        self.t.at(days_ago)
        await confirm_offline_payment(
            payment_id=checkout["payment"]["id"],
            user_id=self.platform.uid,
            note="Cash collected by the courier and deposited at TradeBay.",
        )

    @staticmethod
    def order_for(checkout: dict[str, Any], supplier: Party) -> str:
        for group in checkout["orders"]:
            if group["supplier_business_id"] == supplier.bid:
                return group["order_id"]
        raise RuntimeError("Supplier order missing from checkout")

                                                                            

    async def chat(
        self,
        *,
        buyer: Party,
        supplier: Party,
        subject: str,
        start: float,
        messages: list[tuple[str, str]],
        order_id: str | None = None,
    ) -> None:
        context = {"type_": ConversationType.DIRECT}
        if order_id:
            context = {"type_": ConversationType.ORDER, "context_type": "order", "context_id": order_id}
        self.t.at(start)
        thread = await self.comm.open_or_get(
            user_id=buyer.uid, business=buyer.biz, counterparty_business_id=supplier.bid, subject=subject, **context
        )
        await self.comm.open_or_get(
            user_id=supplier.uid, business=supplier.biz, counterparty_business_id=buyer.bid, subject=subject, **context
        )
        for index, (who, body) in enumerate(messages):
            party = buyer if who == "b" else supplier
            self.t.at(start - 0.02 * (index + 1))
            await self.comm.send_message(
                user_id=party.uid,
                business=party.biz,
                conversation_id=thread["id"],
                body=body,
                message_type=MessageType.TEXT,
            )

async def seed_marketplace_activity(
    *,
    buyers: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    suppliers: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    platform: tuple[dict[str, Any], dict[str, Any]],
) -> dict[str, int]:
    b = {k: Party(*v) for k, v in buyers.items()}
    s = {k: Party(*v) for k, v in suppliers.items()}
    seeder = ActivitySeeder(platform=Party(*platform))
    set_payment_gateway(DemoCardGateway())
    try:
        await _seed(seeder, b, s)
    finally:
        set_payment_gateway(None)
        set_seed_clock(None)
    return await _counts()

async def _seed(sd: ActivitySeeder, b: dict[str, Party], s: dict[str, Party]) -> None:
    beirut, harbor, cafe, grocery = b["beirut"], b["harbor"], b["cafe"], b["grocery"]
    hotel, pharmacy, catering = b["hotel"], b["pharmacy"], b["catering"]
    levant, bekaa, cedar = s["levant"], s["bekaa"], s["cedar"]
    pack, zahle, keserwan = s["pack"], s["zahle"], s["keserwan"]
    beirut_dest = _dest("Beirut", "Beirut")

                                                                            
    tape = await sd.product_deal(
        buyer=harbor, supplier=pack, sku="SPK-TAPE", qty="48",
        requirements="Packing tape dispensers for the restaurant dispatch counter, delivered to Hamra.",
        quote_note="Stock ready in our Dora warehouse. Delivery within Beirut included.",
        dest=beirut_dest, start=84, stage="received", pay="confirmed",
        review=(5, "Dispensers arrived boxed and labelled, a day earlier than promised."),
    )
    await sd.product_deal(
        buyer=grocery, supplier=levant, sku="LEV-OIL-1L", qty="48",
        requirements="Extra virgin olive oil 1L for our shelves, 48 cartons, lot dates within 6 months.",
        quote_note="Current lot pressed in November. Cartons of 12 bottles.",
        dest=_dest("Nabatieh", "Nabatieh"), start=78, stage="received", pay="confirmed",
        review=(5, "Oil quality was consistent across every carton."),
    )
    bricks = await sd.product_deal(
        buyer=beirut, supplier=cedar, sku="CDR-BLOCK-20", qty="1000",
        requirements="Clay bricks and concrete blocks for the storefront renovation on Hamra Street.",
        quote_note="Palletised, 250 blocks per pallet. Crane truck available for unloading.",
        dest=beirut_dest, start=70, stage="received", pay="confirmed",
        review=(4, "On-time delivery. Two blocks chipped, otherwise intact."),
    )
    await sd.product_deal(
        buyer=cafe, supplier=pack, sku="SPK-STORE", qty="40",
        requirements="Airtight food storage sets for the cafe prep kitchen.",
        quote_note="Food-grade containers, BPA free. Lids lock for cold storage.",
        dest=_dest("Zahle", "Bekaa"), start=62, stage="received", pay="pending",
        review=(4, "Containers hold up well in the walk-in fridge."),
    )
    await sd.product_deal(
        buyer=hotel, supplier=levant, sku="LEV-BREAD-MIX", qty="24",
        requirements="Bakery bread assortment for hotel breakfast service, twice a week.",
        quote_note="Baked the night before dispatch. Delivered chilled.",
        dest=_dest("Jounieh", "Mount Lebanon"), start=55, negotiate=("15.40", "15.90"),
        stage="received", pay="confirmed",
        review=(5, "Fresh every delivery and the negotiated price held."),
    )
    await sd.product_deal(
        buyer=beirut, supplier=cedar, sku="CDR-PAINT-20", qty="8",
        requirements="Paint buckets and roller kits for a facade touch-up.",
        quote_note="Exterior-grade acrylic, white and off-white available.",
        dest=beirut_dest, start=47, stage="received",
        review=(4, "Coverage as expected. Invoice to be settled with the next transfer."),
    )
    await sd.product_deal(
        buyer=beirut, supplier=bekaa, sku="BKT-ROUTER", qty="8",
        requirements="Dual-band Wi-Fi routers for our four branch offices, two each.",
        quote_note="Sealed units with one-year local warranty.",
        dest=beirut_dest, start=40, stage="received", pay="confirmed",
        review=(5, "Routers arrived sealed and configured in minutes."),
    )
    await sd.product_deal(
        buyer=pharmacy, supplier=keserwan, sku="PHR-COTTON", qty="16",
        requirements="Cotton pads and swabs for pharmacy retail shelves.",
        quote_note="Pharmacy-grade cotton. Expiry 36 months from production.",
        dest=_dest("Tripoli", "North"), start=35, stage="received", pay="confirmed",
        review=(4, "Packaging intact, good shelf presentation."),
    )
    ppe = await sd.product_deal(
        buyer=catering, supplier=cedar, sku="CDR-PPE", qty="24",
        requirements="Safety helmet and PPE kits for the kitchen renovation crew.",
        quote_note="EN-certified helmets, gloves, and goggles in every kit.",
        dest=_dest("Tyre", "South"), start=30, stage="received",
        review=(3, "Sizes were mixed across the pack; two helmets too small."),
    )
    await sd.product_deal(
        buyer=catering, supplier=pack, sku="SPK-STORE", qty="20",
        requirements="Food storage sets for weekend catering prep.",
        quote_note="Same model as our cafe clients use. Stackable.",
        dest=_dest("Tyre", "South"), start=26, stage="received", pay="confirmed",
        review=(5, "Stackable and easy to clean. Will reorder."),
    )
    await sd.product_deal(
        buyer=grocery, supplier=zahle, sku="ZFI-HONEY", qty="10",
        requirements="Wildflower honey cartons for the farm-shop corner.",
        quote_note="Harvested in the Bekaa this season. Glass jars, 12 per carton.",
        dest=_dest("Nabatieh", "Nabatieh"), start=21, stage="received", pay="confirmed",
        review=(4, "Lovely honey; one jar lid was dented."),
    )

                                                                      
    pasta_rfq = await sd.sourcing_rfq(
        buyer=grocery, title="Durum pasta assortment for grocery restock",
        description="About 20 cartons of durum pasta for retail shelves, mixed shapes.",
        qty="20", unit="carton", product_name="Durum Pasta Assortment",
        dest=_dest("Nabatieh", "Nabatieh"), start=50,
    )
    sd.t.at(49.6)
    levant_pasta = await sd.quote(
        rfq=pasta_rfq, supplier=levant, unit_price=await _tier_price((await _product_by_sku("LEV-PASTA-5"))["_id"], "20"),
        notes="Imported Italian durum wheat pasta, five shapes per carton.",
    )
    sd.t.at(49.4)
    await sd.quote(
        rfq=pasta_rfq, supplier=zahle, unit_price="11.95",
        notes="Village pasta shells, locally made. Lead time one week.", lead_days=7,
    )
    sd.t.at(48.8)
    pasta_order = await sd.proc.award(
        user_id=grocery.uid, business=grocery.biz, rfq_id=pasta_rfq["id"], quotation_id=levant_pasta["id"], confirm=True
    )
    await sd.fulfil(order_id=pasta_order["id"], supplier=levant, buyer=grocery, start=48.5, stage="received")
    await sd.pay_invoice(order_id=pasta_order["id"], buyer=grocery, days_ago=45, confirm=True)
    await sd.review(order_id=pasta_order["id"], buyer=grocery, days_ago=44.5, rating=4,
                    comment="Pasta cartons arrived clean and dry.")

                                                                            
    c1 = await sd.cart_checkout(
        buyer=beirut, method="cash", start=33,
        lines=[("LEV-OIL-1L", 12), ("SPK-STAPLER", 12), ("BKT-CALC-12", 12)],
        notes="Deliver to the Hamra branch loading bay, weekdays 8am-2pm.",
    )
    for supplier in (levant, pack, bekaa):
        await sd.fulfil(order_id=sd.order_for(c1, supplier), supplier=supplier, buyer=beirut, start=32.6, stage="received")
    await sd.confirm_cash(c1, days_ago=30)
    for supplier, rating, comment in (
        (levant, 5, "Olive oil delivered with the cash collection, smooth handover."),
        (pack, 4, "Staplers are sturdy. Delivery slot was respected."),
    ):
        await sd.review(order_id=sd.order_for(c1, supplier), buyer=beirut, days_ago=29, rating=rating, comment=comment)

    await _seed_recent(sd, b, s, deal_orders={
        "tape": tape["order"]["id"], "bricks": bricks["order"]["id"], "ppe": ppe["order"]["id"],
    })

async def _seed_recent(
    sd: ActivitySeeder, b: dict[str, Party], s: dict[str, Party], *, deal_orders: dict[str, str]
) -> None:
    beirut, harbor, cafe, grocery = b["beirut"], b["harbor"], b["cafe"], b["grocery"]
    hotel, pharmacy, catering = b["hotel"], b["pharmacy"], b["catering"]
    levant, bekaa, cedar, south = s["levant"], s["bekaa"], s["cedar"], s["south"]
    pack, zahle, keserwan, tripoli = s["pack"], s["zahle"], s["keserwan"], s["tripoli"]
    beirut_dest = _dest("Beirut", "Beirut")

    c2 = await sd.cart_checkout(
        buyer=harbor, method="card", start=24,
        lines=[("PHR-LIP", 24), ("SAF-MOP", 12), ("ZFI-HONEY", 8)],
        notes="Guest amenities and housekeeping restock.",
    )
    await sd.fulfil(order_id=sd.order_for(c2, keserwan), supplier=keserwan, buyer=harbor, start=23.5, stage="received")
    await sd.fulfil(order_id=sd.order_for(c2, tripoli), supplier=tripoli, buyer=harbor, start=2.6, stage="in_transit")
    await sd.fulfil(order_id=sd.order_for(c2, zahle), supplier=zahle, buyer=harbor, start=1.2, stage="confirmed")
    await sd.review(order_id=sd.order_for(c2, keserwan), buyer=harbor, days_ago=20, rating=5,
                    comment="Guests love the lip balm sets in the welcome kit.")

    c7 = await sd.cart_checkout(
        buyer=catering, method="card", start=17,
        lines=[("SPK-STORE-XL", 10)],
        notes="Meal-prep containers for the new catering line.",
    )
    await sd.fulfil(order_id=sd.order_for(c7, pack), supplier=pack, buyer=catering, start=16.5, stage="received")
    await sd.review(order_id=sd.order_for(c7, pack), buyer=catering, days_ago=13.5, rating=5,
                    comment="Glass containers are microwave safe and nothing broke in transit.")

    c6 = await sd.cart_checkout(
        buyer=pharmacy, method="cash", start=14,
        lines=[("PHR-COTTON-XL", 16), ("BKT-EARBUDS", 12)],
        notes="Monthly restock.",
    )
    sd.t.at(13.8)
    await sd.checkout.cancel(
        user_id=pharmacy.uid, business=pharmacy.biz, checkout_id=c6["id"],
        reason="Ordered the earbuds by mistake; will reorder cotton separately.",
    )

    c8 = await sd.cart_checkout(
        buyer=beirut, method="cash", start=10,
        lines=[("CDR-BLOCK-15", 400)],
        notes="Second phase of the storefront works.",
    )
    await sd.fulfil(order_id=sd.order_for(c8, cedar), supplier=cedar, buyer=beirut, start=2.4, stage="delivered")

    c3 = await sd.cart_checkout(
        buyer=cafe, method="card", start=6,
        lines=[("TYR-FISH-ICE", 10), ("LEV-BREAD-MIX", 8)],
        notes="Weekend brunch menu.",
    )
    await sd.fulfil(order_id=sd.order_for(c3, south), supplier=south, buyer=cafe, start=1.9, stage="out_for_delivery")

    c4 = await sd.cart_checkout(
        buyer=hotel, method="cash", start=2.5,
        lines=[("SPK-TRAY", 8), ("PHR-HAIR", 12)],
        notes="Front office trays and guest bathroom amenities.",
    )
    await sd.fulfil(order_id=sd.order_for(c4, pack), supplier=pack, buyer=hotel, start=1.0, stage="confirmed")

    await sd.cart_checkout(
        buyer=grocery, method="card", start=0.5, paid=False,
        lines=[("LEV-PASTA-PENNE", 10), ("ZFI-PULSES", 10)],
        notes="Pantry aisle restock.",
    )

                                                                            
    await sd.product_deal(
        buyer=hotel, supplier=levant, sku="LEV-PASTA-5", qty="24",
        requirements="Durum pasta assortment for the hotel kitchen, 24 cartons.",
        quote_note="Five-day lead time from confirmation.",
        dest=_dest("Jounieh", "Mount Lebanon"), start=9, stage="confirmed",
    )
    monitors = await sd.product_deal(
        buyer=harbor, supplier=bekaa, sku="BKT-MON-24", qty="8",
        requirements="27in monitors for the new reservations desk.",
        quote_note="Height-adjustable stands included.",
        dest=beirut_dest, start=12, negotiate=("136.00", "140.00"), stage="in_transit",
    )
    await sd.product_deal(
        buyer=beirut, supplier=bekaa, sku="BKT-PRINT-INK", qty="4",
        requirements="Colour inkjet printers for branch offices.",
        quote_note="Starter ink cartridges included. Volume price from 8 units.",
        dest=beirut_dest, start=6,
    )
    await sd.product_deal(
        buyer=hotel, supplier=levant, sku="LEV-CHOC-MIX", qty="16",
        requirements="Assorted chocolate for minibar and pantry restock.",
        quote_note="Belgian chocolate, mixed dark and milk.",
        dest=_dest("Jounieh", "Mount Lebanon"), start=4, negotiation_open="20.50",
    )
    await sd.product_deal(
        buyer=cafe, supplier=zahle, sku="ZFI-HONEY-THYME", qty="8",
        requirements="Thyme honey for the breakfast menu.",
        quote_note="Limited harvest, glass jars.",
        dest=_dest("Zahle", "Bekaa"), start=3, reject_reason="Above our budget for this quarter.",
    )
    fish_rfq = await sd.sourcing_rfq(
        buyer=cafe, title="Chilled whole fish for cafe kitchen",
        description="Chilled whole fish on ice, around 40 kg per week, delivered Friday mornings.",
        qty="40", unit="kg", product_name="Chilled Whole Fish on Ice", dest=_dest("Zahle", "Bekaa"), start=5,
    )
    sd.t.at(4.6)
    await sd.quote(rfq=fish_rfq, supplier=south, unit_price="14.20",
                   notes="Morning catch from Tyre harbour, packed on ice.", lead_days=1)
    cotton_rfq = await sd.sourcing_rfq(
        buyer=harbor, title="Cotton pads for 200 hotel rooms",
        description="Wholesale cotton pads and swabs for guest bathrooms, quarterly supply.",
        qty="200", unit="box", product_name="Cotton Pads and Swabs", dest=beirut_dest, start=3,
    )
    sd.t.at(2.7)
    await sd.quote(rfq=cotton_rfq, supplier=keserwan, unit_price="6.10",
                   notes="Quarterly contract price. Branded sleeves optional.")
    await sd.sourcing_rfq(
        buyer=hotel, title="Staff T-shirts for hotel F&B team",
        description="1,000 cotton T-shirts with embroidered logo for restaurant and bar staff.",
        qty="1000", unit="piece", product_name="Premium Cotton T-Shirt",
        dest=_dest("Jounieh", "Mount Lebanon"), start=2,
    )
    storage_rfq = await sd.sourcing_rfq(
        buyer=catering, title="Food storage sets for catering prep",
        description="Airtight food storage sets for catering prep, about 40 boxes.",
        qty="40", unit="box", product_name="Airtight Food Storage Set", dest=_dest("Tyre", "South"), start=1.5,
    )
    sd.t.at(1.2)
    await sd.quote(rfq=storage_rfq, supplier=pack, unit_price="16.20", notes="Glass-lidded option on request.")
    sd.t.at(1.0)
    await sd.quote(rfq=storage_rfq, supplier=tripoli, unit_price="12.40",
                   notes="Plastic set of five, made in Tripoli.", lead_days=6)

                                                                            
    sd.t.at(24.5)
    await sd.trust.open_dispute(
        user_id=catering.uid, business=catering.biz, order_id=deal_orders["ppe"],
        reason="Wrong sizes delivered",
        description="Two of the 24 helmet kits were size S instead of the ordered L.",
    )

                                                                            
    await sd.chat(buyer=harbor, supplier=pack, subject="Printed packing tape", start=82.5,
                  order_id=deal_orders["tape"], messages=[
                      ("b", "Can you print our logo on the packing tape for the next batch?"),
                      ("s", "Yes. Printed tape has a 24-roll minimum and adds about four days."),
                      ("b", "Great, we'll take the plain dispensers now and printed rolls next month."),
                  ])
    await sd.chat(buyer=beirut, supplier=cedar, subject="Brick delivery window", start=68.5,
                  order_id=deal_orders["bricks"], messages=[
                      ("b", "Can the pallets be dropped at Hamra before noon? Parking is tight after 1pm."),
                      ("s", "Morning slot confirmed. The crane truck arrives at 8:30."),
                      ("b", "Perfect, our site foreman Khalil will sign for it."),
                  ])
    await sd.chat(buyer=grocery, supplier=levant, subject="Olive oil restock", start=79, messages=[
        ("b", "Do you have 1L extra virgin in stock for next week?"),
        ("s", "Yes, 48 cartons ready from the Mkalles warehouse."),
        ("b", "Please hold them, we're sending the RFQ now."),
    ])
    await sd.chat(buyer=harbor, supplier=bekaa, subject="Monitor stands", start=10.5,
                  order_id=monitors["order"]["id"], messages=[
                      ("b", "Do the monitors come with VESA mounts? The desk has arms."),
                      ("s", "Yes, 100x100 VESA. Stands are in the box too."),
                  ])
    await sd.chat(buyer=catering, supplier=cedar, subject="Helmet sizes", start=24.8,
                  order_id=deal_orders["ppe"], messages=[
                      ("b", "Two kits have small helmets. Can you swap them?"),
                      ("s", "Sorry about that. We'll send two size L kits with the next delivery."),
                  ])
    await sd.chat(buyer=cafe, supplier=south, subject="Friday fish delivery", start=4.8, messages=[
        ("b", "Can you deliver 40 kg every Friday before 9am?"),
        ("s", "Yes, our Zahle route leaves Tyre at 5am on Fridays."),
        ("b", "Great, I'll confirm after this week's trial order."),
    ])
    await sd.chat(buyer=hotel, supplier=levant, subject="Chocolate for minibars", start=3.9, messages=[
        ("b", "We sent a counteroffer at 20.50 per carton. Can you meet us there?"),
        ("s", "Let me check with finance. I'll reply on the negotiation today."),
    ])

                                                                            
    ai = StubAIProvider()
    sourcing = AISourcingService(ai=ai)
    for party, days_ago, prompt in (
        (harbor, 8, "We run a 60-room hotel in Beirut and need packing tape, food storage, and olive oil "
                    "for the restaurant kitchen every month."),
        (grocery, 7, "Neighbourhood grocery in Nabatieh looking for wholesale olive oil, pasta, and honey, "
                     "about 50 cartons a month delivered."),
        (cafe, 5, "Cafe in Zahle needs herbal tea, bread assortments, and airtight storage for prep."),
    ):
        sd.t.at(days_ago)
        analysed = await sourcing.analyze(user_id=party.uid, business=party.biz, business_description=prompt)
        sd.t.at(days_ago - 0.01)
        await sourcing.confirm_requirements(
            user_id=party.uid,
            business=party.biz,
            sourcing_request_id=analysed["sourcing_request_id"],
            requirements=ProcurementRequirements.model_validate(analysed["requirements"]),
        )
        sd.t.at(days_ago - 0.02)
        await sourcing.recommend(business=party.biz, sourcing_request_id=analysed["sourcing_request_id"])

    planner = BusinessPlannerService(ai=ai)
    for party, days_ago, answers in (
        (beirut, 15, {
            "goal": {"business_goal": "Open a second mini-market branch in Achrafieh", "category_hints": ["food", "home"]},
            "location": {"location": "Beirut"},
            "budget": {"budget_range": "10000_25000"},
            "preferences": {"business_model": ["retail"], "experience": "experienced", "risk_preference": "balanced",
                            "customer_type": "consumers", "desired_margin": "25"},
        }),
        (cafe, 9, {
            "goal": {"business_goal": "Add a bakery corner to the cafe", "category_hints": ["food"]},
            "location": {"location": "Zahle"},
            "budget": {"budget_range": "3000_5000"},
            "preferences": {"business_model": ["retail"], "experience": "some", "risk_preference": "low",
                            "customer_type": "consumers", "desired_margin": "35"},
        }),
    ):
        sd.t.at(days_ago)
        session = await planner.create_session(user_id=party.uid)
        for step, payload in answers.items():
            await planner.submit_answers(user_id=party.uid, session_id=session["id"], step=step, answers=payload)
        sd.t.at(days_ago - 0.02)
        await planner.generate_from_session(user_id=party.uid, session_id=session["id"])

                                                                    
    sd.t.at(0.1)
    for sku, qty in (("BKT-MON-24", 4), ("LEV-OIL-5L", 6), ("SPK-CORK", 6)):
        product = await _product_by_sku(sku)
        if str(product.get("status")) == "active":
            await sd.cart.add_item(business=beirut.biz, product_id=str(product["_id"]), quantity=qty)

async def _counts() -> dict[str, int]:
    names = {
        "rfqs": CollectionName.RFQS,
        "quotations": CollectionName.QUOTATIONS,
        "negotiations": CollectionName.NEGOTIATIONS,
        "negotiation_offers": CollectionName.NEGOTIATION_OFFERS,
        "checkouts": CollectionName.CHECKOUTS,
        "orders": CollectionName.ORDERS,
        "shipments": CollectionName.SHIPMENTS,
        "invoices": CollectionName.CUSTOMER_INVOICES,
        "payments": CollectionName.PAYMENTS,
        "reviews": CollectionName.REVIEWS,
        "disputes": CollectionName.DISPUTES,
        "notifications": CollectionName.NOTIFICATIONS,
        "conversations": CollectionName.CONVERSATIONS,
        "messages": CollectionName.MESSAGES,
        "sourcing_requests": CollectionName.SOURCING_REQUESTS,
        "business_plans": CollectionName.BUSINESS_PLANS,
        "audit_logs": CollectionName.AUDIT_LOGS,
    }
    return {
        key: await mongo_manager.collection(name).count_documents({}) for key, name in names.items()
    }
