"""Seed RFQs, quotes, orders, finance, reviews, chats, and AI sourcing via domain services.

Every actor here is a synthetic demo company. Public Lebanese businesses researched
for category inspiration are listed in SOURCES.md and are not TradeBay members.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.ai_sourcing.constants import (
    AvailabilityStatus,
    RelevanceLabel,
    SourcingRequestStatus,
)
from app.modules.communication.constants import ConversationType, MessageType
from app.modules.communication.service import CommunicationService
from app.modules.finance.service import FinanceService
from app.modules.procurement.commercial import money, quantize
from app.modules.procurement.constants import ShipmentStatus
from app.modules.procurement.service import ProcurementService
from app.modules.settings.tax import compute_tax
from app.modules.trust.notify import notify
from app.modules.trust.service import TrustService
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

TAX_RATE = Decimal("0.11")
DEST_BEIRUT = {
    "street": "Hamra Street 42, Picard Building",
    "city": "Beirut",
    "district": "Ras Beirut",
    "governorate": "Beirut",
    "postal_code": "1103",
    "country": "Lebanon",
}


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
        raise RuntimeError(f"Demo product missing: {sku}")
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


async def _quote(
    proc: ProcurementService,
    *,
    rfq: dict[str, Any],
    supplier: dict[str, Any],
    supplier_user_id: str,
    unit_price: str,
    quantity: str | None = None,
    notes: str = "Demo quotation — not a real commercial offer.",
) -> dict[str, Any]:
    item = rfq["items"][0]
    qty = quantity or item["quantity"]
    line_sub = quantize(money(qty) * money(unit_price))
    tax = compute_tax(subtotal=line_sub, rate=TAX_RATE)["tax_amount"]
    return await proc.upsert_quotation(
        user_id=supplier_user_id,
        business=_biz(supplier),
        rfq_id=rfq["id"],
        payload={
            "payment_terms": "Net 30",
            "delivery_terms": "Ex-works Lebanon",
            "currency": "USD",
            "notes": notes,
            "document_tax": "0",
            "lines": [
                {
                    "rfq_item_id": item["id"],
                    "quantity": qty,
                    "unit_price": unit_price,
                    "moq": 1,
                    "lead_time_days": 7,
                    "tax": format(tax, "f"),
                }
            ],
        },
        submit=True,
    )


async def _fulfil(
    proc: ProcurementService,
    *,
    order: dict[str, Any],
    supplier: dict[str, Any],
    supplier_user_id: str,
    buyer: dict[str, Any],
    buyer_user_id: str,
    pay: bool,
    review: tuple[int, str] | None,
) -> None:
    order = await proc.acknowledge_order(
        user_id=supplier_user_id,
        business=_biz(supplier),
        order_id=order["id"],
    )
    line = order["items"][0]
    shipment = await proc.create_shipment(
        user_id=supplier_user_id,
        business=_biz(supplier),
        order_id=order["id"],
        payload={
            "carrier_name": "Demo Levant Freight",
            "tracking_number": f"TB-TRK-{str(order['order_number'])[-4:]}",
            "origin": "Lebanon",
            "lines": [{"order_item_id": line["id"], "quantity": line["quantity"]}],
        },
    )
    for status, loc, note in (
        (ShipmentStatus.SHIPPED, "Beirut", "Loaded"),
        (ShipmentStatus.DELIVERED, "Buyer site", "Delivered"),
    ):
        shipment = await proc.add_tracking_event(
            user_id=supplier_user_id,
            business=_biz(supplier),
            shipment_id=shipment["id"],
            payload={"status": status, "location": loc, "description": note},
        )
    await proc.receive_shipment(
        user_id=buyer_user_id,
        business=_biz(buyer),
        shipment_id=shipment["id"],
        payload={
            "notes": "Received in full (demo).",
            "lines": [
                {
                    "order_item_id": line["id"],
                    "received_quantity": line["quantity"],
                    "damaged_quantity": "0",
                    "missing_quantity": "0",
                    "rejected_quantity": "0",
                }
            ],
        },
    )
    invoice = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
        {"order_id": parse_object_id(order["id"])}
    )
    if pay and invoice is not None:
        await FinanceService().record_payment(
            user_id=buyer_user_id,
            business=_biz(buyer),
            invoice_id=str(invoice["_id"]),
            amount=format(money(invoice["total"]), "f"),
            payment_method="bank_transfer",
            complete=True,
        )
    if review:
        await TrustService().create_review(
            user_id=buyer_user_id,
            business=_biz(buyer),
            order_id=order["id"],
            rating=review[0],
            comment=review[1],
        )


async def _product_rfq(
    proc: ProcurementService,
    *,
    buyer: dict[str, Any],
    buyer_user: dict[str, Any],
    product: dict[str, Any],
    qty: str,
    requirements: str,
    dest: dict[str, str],
) -> dict[str, Any]:
    return await proc.create_product_rfq(
        user_id=str(buyer_user["_id"]),
        business=_biz(buyer),
        payload={
            "product_id": str(product["_id"]),
            "quantity": qty,
            "unit": product.get("unit") or "unit",
            "requirements": requirements,
            "publish": True,
            "destination": dest,
        },
    )


async def _chat(
    comm: CommunicationService,
    *,
    buyer: dict[str, Any],
    buyer_user: dict[str, Any],
    supplier: dict[str, Any],
    supplier_user: dict[str, Any],
    subject: str,
    buyer_msg: str,
    supplier_msg: str,
) -> None:
    thread = await comm.open_or_get(
        user_id=str(buyer_user["_id"]),
        business=_biz(buyer),
        counterparty_business_id=str(supplier["_id"]),
        type_=ConversationType.DIRECT,
        subject=subject,
    )
    await comm.open_or_get(
        user_id=str(supplier_user["_id"]),
        business=_biz(supplier),
        counterparty_business_id=str(buyer["_id"]),
        type_=ConversationType.DIRECT,
        subject=subject,
    )
    await comm.send_message(
        user_id=str(buyer_user["_id"]),
        business=_biz(buyer),
        conversation_id=thread["id"],
        body=buyer_msg,
        message_type=MessageType.TEXT,
    )
    await comm.send_message(
        user_id=str(supplier_user["_id"]),
        business=_biz(supplier),
        conversation_id=thread["id"],
        body=supplier_msg,
        message_type=MessageType.TEXT,
    )


async def _insert_sourcing_demo(
    *,
    buyer: dict[str, Any],
    buyer_user: dict[str, Any],
    prompt: str,
    concept_name: str,
    matches: list[tuple[dict[str, Any], dict[str, Any], float, str, str]],
) -> None:
    now = utc_now()
    src_id = ObjectId()
    item_id = ObjectId()
    src = {
        "_id": src_id,
        "buyer_user_id": buyer_user["_id"],
        "buyer_business_id": buyer["_id"],
        "original_prompt": prompt,
        "destination": "Beirut, Lebanon",
        "status": SourcingRequestStatus.COMPLETED,
        "rfq_id": None,
        "requirements": {
            "business_type": "hospitality" if "cup" in prompt.lower() else "retail",
            "product_requirements": ["wholesale", "Lebanon delivery"],
            "location": "Beirut",
        },
        "ai_summary": (
            "Demo extraction only. Catalog matches are suggestions, not supplier replies "
            "and not a claim that these companies use TradeBay."
        ),
        "created_at": now,
        "updated_at": now,
        "is_demo_seed": True,
        "data_source": "synthetic_demo",
    }
    first_product = matches[0][0]
    qty = Decimal("5000") if "cup" in prompt.lower() else Decimal("200")
    item_doc = {
        "_id": item_id,
        "sourcing_request_id": src_id,
        "product_id": first_product["_id"],
        "category_id": first_product.get("category_id"),
        "requested_name": concept_name,
        "description": "Demo product concept — not a real branded SKU.",
        "quantity": to_decimal128(qty),
        "unit": "piece",
        "created_at": now,
    }
    recs = []
    for product, supplier_doc, score, label, reason in matches:
        recs.append(
            {
                "_id": ObjectId(),
                "sourcing_request_id": src_id,
                "sourcing_request_item_id": item_id,
                "product_id": product["_id"],
                "business_account_id": supplier_doc["_id"],
                "reason": reason,
                "match_score": score,
                "relevance_label": label,
                "matched_requirements": ["Lebanon wholesale"] if score >= 0.6 else [],
                "unmatched_requirements": ["custom logo"] if score < 0.9 else [],
                "reasons": [reason, "Demo recommendation — not a live supplier response."],
                "estimated_unit_price": to_decimal128(
                    money(await _tier_price(product["_id"], str(product.get("moq") or 1)))
                ),
                "availability_status": AvailabilityStatus.IN_STOCK,
                "created_at": now,
            }
        )
    await mongo_manager.collection(CollectionName.SOURCING_REQUESTS).insert_one(src)
    await mongo_manager.collection(CollectionName.SOURCING_REQUEST_ITEMS).insert_one(item_doc)
    await mongo_manager.collection(CollectionName.SOURCING_RECOMMENDATIONS).insert_many(recs)


async def seed_marketplace_activity(
    *,
    buyers: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    suppliers: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, int]:
    """Drive RFQ → PO → invoice through domain services. Synthetic actors only."""
    proc = ProcurementService()
    comm = CommunicationService()

    beirut, sara = buyers["beirut"]
    harbor, omar = buyers["harbor"]
    cafe, lara = buyers["cafe"]
    grocery, nabil = buyers["grocery"]
    hotel, rita = buyers["hotel"]
    pharmacy, dany = buyers["pharmacy"]
    catering, fadia = buyers["catering"]

    levant, karim = suppliers["levant"]
    bekaa, rami = suppliers["bekaa"]
    cedar, maya = suppliers["cedar"]
    south, hassan = suppliers["south"]
    pack, samer = suppliers["pack"]
    zahle, youssef = suppliers["zahle"]
    keserwan, karine = suppliers["keserwan"]
    saida, ziad = suppliers["saida"]

    oil = await _product_by_sku("LEV-OIL-1L")
    pasta = await _product_by_sku("LEV-PASTA-5")
    tape = await _product_by_sku("SPK-TAPE")
    storage = await _product_by_sku("SPK-STORE")
    chocolate = await _product_by_sku("LEV-CHOC-MIX")
    bricks = await _product_by_sku("CDR-BLOCK-20")
    paint = await _product_by_sku("CDR-PAINT-20")
    ppe = await _product_by_sku("CDR-PPE")
    printer = await _product_by_sku("BKT-PRINT-INK")
    router = await _product_by_sku("BKT-ROUTER")
    bread = await _product_by_sku("LEV-BREAD-MIX")
    pantry = await _product_by_sku("LEV-PANTRY-JAR")
    cotton = await _product_by_sku("PHR-COTTON")
    tea = await _product_by_sku("MSP-TEA-HERB")
    honey = await _product_by_sku("ZFI-HONEY")
    fish = await _product_by_sku("TYR-FISH-ICE")

    async def deal(
        *,
        buyer: dict[str, Any],
        buyer_user: dict[str, Any],
        supplier: dict[str, Any],
        supplier_user: dict[str, Any],
        product: dict[str, Any],
        qty: str,
        requirements: str,
        dest: dict[str, str],
        award: bool,
        confirm: bool = False,
        fulfil: bool = False,
        pay: bool = False,
        review: tuple[int, str] | None = None,
    ) -> dict[str, Any]:
        rfq = await _product_rfq(
            proc,
            buyer=buyer,
            buyer_user=buyer_user,
            product=product,
            qty=qty,
            requirements=requirements,
            dest=dest,
        )
        quote = await _quote(
            proc,
            rfq=rfq,
            supplier=supplier,
            supplier_user_id=str(supplier_user["_id"]),
            unit_price=await _tier_price(product["_id"], qty),
        )
        order = None
        if award:
            order = await proc.award(
                user_id=str(buyer_user["_id"]),
                business=_biz(buyer),
                rfq_id=rfq["id"],
                quotation_id=quote["id"],
                confirm=True,
            )
            if confirm and not fulfil:
                await proc.acknowledge_order(
                    user_id=str(supplier_user["_id"]),
                    business=_biz(supplier),
                    order_id=order["id"],
                )
            if fulfil:
                await _fulfil(
                    proc,
                    order=order,
                    supplier=supplier,
                    supplier_user_id=str(supplier_user["_id"]),
                    buyer=buyer,
                    buyer_user_id=str(buyer_user["_id"]),
                    pay=pay,
                    review=review,
                )
        return {"rfq": rfq, "quote": quote, "order": order}

    await deal(
        buyer=harbor,
        buyer_user=omar,
        supplier=pack,
        supplier_user=samer,
        product=tape,
        qty="48",
        requirements="Need packing tape dispensers for restaurant dispatch. Demo RFQ only.",
        dest=DEST_BEIRUT,
        award=True,
        fulfil=True,
        pay=True,
        review=(5, "Good product quality and delivery time. Demo review."),
    )
    await deal(
        buyer=grocery,
        buyer_user=nabil,
        supplier=levant,
        supplier_user=karim,
        product=oil,
        qty="48",
        requirements="Wholesale extra virgin olive oil in 1L, about 48 cartons.",
        dest=_dest("Nabatieh", "Nabatieh"),
        award=True,
        fulfil=True,
        pay=True,
        review=(5, "Oil quality was consistent across cartons."),
    )
    await deal(
        buyer=beirut,
        buyer_user=sara,
        supplier=cedar,
        supplier_user=maya,
        product=bricks,
        qty="80",
        requirements="Clay bricks and concrete blocks for a small renovation job.",
        dest=DEST_BEIRUT,
        award=True,
        fulfil=True,
        pay=True,
        review=(4, "On-time delivery. Blocks arrived intact."),
    )
    await deal(
        buyer=cafe,
        buyer_user=lara,
        supplier=pack,
        supplier_user=samer,
        product=storage,
        qty="40",
        requirements="Looking for airtight food storage sets for cafe prep.",
        dest=_dest("Zahle", "Bekaa"),
        award=True,
        fulfil=True,
        pay=False,
        review=(4, "Containers held up well for prep storage."),
    )
    await deal(
        buyer=hotel,
        buyer_user=rita,
        supplier=levant,
        supplier_user=karim,
        product=bread,
        qty="24",
        requirements="Bakery bread assortment for hotel breakfast service.",
        dest=_dest("Jounieh", "Mount Lebanon"),
        award=True,
        fulfil=True,
        pay=True,
        review=(5, "Bread assortment was consistent. Demo review."),
    )
    await deal(
        buyer=beirut,
        buyer_user=sara,
        supplier=cedar,
        supplier_user=maya,
        product=paint,
        qty="8",
        requirements="Paint buckets and roller kits for a facade touch-up.",
        dest=DEST_BEIRUT,
        award=True,
        fulfil=True,
        pay=False,
        review=(4, "Coverage was as expected for a demo order."),
    )
    await deal(
        buyer=beirut,
        buyer_user=sara,
        supplier=bekaa,
        supplier_user=rami,
        product=router,
        qty="8",
        requirements="Wi-Fi routers for branch offices.",
        dest=DEST_BEIRUT,
        award=True,
        fulfil=True,
        pay=True,
        review=(5, "Routers arrived sealed."),
    )
    await deal(
        buyer=pharmacy,
        buyer_user=dany,
        supplier=keserwan,
        supplier_user=karine,
        product=cotton,
        qty="16",
        requirements="Cotton pads and swabs for pharmacy retail shelves.",
        dest=_dest("Tripoli", "North"),
        award=True,
        fulfil=True,
        pay=True,
        review=(4, "Packaging intact. Demo review."),
    )
    await deal(
        buyer=catering,
        buyer_user=fadia,
        supplier=cedar,
        supplier_user=maya,
        product=ppe,
        qty="24",
        requirements="Safety helmet and PPE kits for a store renovation crew.",
        dest=_dest("Tyre", "South"),
        award=True,
        fulfil=True,
        pay=False,
        review=(3, "Fit was mixed across the pack."),
    )
    await deal(
        buyer=catering,
        buyer_user=fadia,
        supplier=pack,
        supplier_user=samer,
        product=storage,
        qty="20",
        requirements="Food storage sets for weekend catering prep.",
        dest=_dest("Tyre", "South"),
        award=True,
        fulfil=True,
        pay=True,
        review=(5, "Absorbent and consistent count per pack."),
    )
    await deal(
        buyer=grocery,
        buyer_user=nabil,
        supplier=zahle,
        supplier_user=youssef,
        product=honey,
        qty="10",
        requirements="Wildflower honey cartons for a farm-shop restock.",
        dest=_dest("Zahle", "Bekaa"),
        award=True,
        fulfil=True,
        pay=True,
        review=(4, "Bags were dry and labelled."),
    )
    await deal(
        buyer=hotel,
        buyer_user=rita,
        supplier=levant,
        supplier_user=karim,
        product=pasta,
        qty="24",
        requirements="Durum pasta assortment for hotel kitchen, 24 cartons.",
        dest=_dest("Jounieh", "Mount Lebanon"),
        award=True,
        confirm=True,
        fulfil=False,
    )
    await deal(
        buyer=beirut,
        buyer_user=sara,
        supplier=bekaa,
        supplier_user=rami,
        product=printer,
        qty="4",
        requirements="Color inkjet printers for branch offices.",
        dest=DEST_BEIRUT,
        award=False,
    )
    await deal(
        buyer=hotel,
        buyer_user=rita,
        supplier=levant,
        supplier_user=karim,
        product=chocolate,
        qty="16",
        requirements="Assorted chocolate for hotel pantry restock.",
        dest=_dest("Jounieh", "Mount Lebanon"),
        award=False,
    )
    await deal(
        buyer=cafe,
        buyer_user=lara,
        supplier=saida,
        supplier_user=ziad,
        product=tea,
        qty="16",
        requirements="Mountain herbal tea for cafe service.",
        dest=_dest("Zahle", "Bekaa"),
        award=False,
    )

    rfq_pasta = await proc.create_sourcing_rfq(
        user_id=str(nabil["_id"]),
        business=_biz(grocery),
        payload={
            "title": "Durum pasta assortment for grocery restock",
            "description": "Need about 20 cartons of durum pasta for retail shelves. Demo sourcing RFQ.",
            "quantity": "20",
            "unit": "carton",
            "product_name": "Durum Pasta Assortment",
            "visibility": "open",
            "publish": True,
            "destination": _dest("Nabatieh", "Nabatieh"),
        },
    )
    pasta_price = await _tier_price(pasta["_id"], "20")
    levant_pasta_quote = await _quote(
        proc,
        rfq=rfq_pasta,
        supplier=levant,
        supplier_user_id=str(karim["_id"]),
        unit_price=pasta_price,
    )
    pasta_order = await proc.award(
        user_id=str(nabil["_id"]),
        business=_biz(grocery),
        rfq_id=rfq_pasta["id"],
        quotation_id=levant_pasta_quote["id"],
        confirm=True,
    )
    await _fulfil(
        proc,
        order=pasta_order,
        supplier=levant,
        supplier_user_id=str(karim["_id"]),
        buyer=grocery,
        buyer_user_id=str(nabil["_id"]),
        pay=True,
        review=(4, "Pasta cartons arrived clean and dry."),
    )

    rfq_fish = await proc.create_sourcing_rfq(
        user_id=str(lara["_id"]),
        business=_biz(cafe),
        payload={
            "title": "Chilled whole fish for cafe kitchen",
            "description": "Looking for chilled whole fish on ice, around 40 kg per week.",
            "quantity": "40",
            "unit": "kg",
            "product_name": "Chilled Whole Fish on Ice",
            "visibility": "open",
            "publish": True,
            "destination": _dest("Zahle", "Bekaa"),
        },
    )
    await _quote(
        proc,
        rfq=rfq_fish,
        supplier=south,
        supplier_user_id=str(hassan["_id"]),
        unit_price=await _tier_price(fish["_id"], "40"),
        notes="Demo offer for chilled whole fish.",
    )
    await proc.create_sourcing_rfq(
        user_id=str(omar["_id"]),
        business=_biz(harbor),
        payload={
            "title": "Cotton pads for 200 hotel rooms",
            "description": "Need wholesale cotton pads and swabs for guest bathrooms. Demo sourcing RFQ.",
            "quantity": "200",
            "unit": "box",
            "product_name": "Cotton Pads and Swabs",
            "visibility": "open",
            "publish": True,
            "destination": DEST_BEIRUT,
        },
    )
    await proc.create_sourcing_rfq(
        user_id=str(rita["_id"]),
        business=_biz(hotel),
        payload={
            "title": "Staff T-shirts for hotel F&B team",
            "description": "Looking for 1,000 premium T-shirts for retail and staff. Demo RFQ.",
            "quantity": "1000",
            "unit": "piece",
            "product_name": "Premium Cotton T-Shirt",
            "visibility": "open",
            "publish": True,
            "destination": _dest("Jounieh", "Mount Lebanon"),
        },
    )
    await proc.create_sourcing_rfq(
        user_id=str(fadia["_id"]),
        business=_biz(catering),
        payload={
            "title": "Food storage sets for catering prep",
            "description": "Need airtight food storage sets for catering prep, about 40 boxes.",
            "quantity": "40",
            "unit": "box",
            "product_name": "Airtight Food Storage Set",
            "visibility": "open",
            "publish": True,
            "destination": _dest("Tyre", "South"),
        },
    )

    await _chat(
        comm,
        buyer=harbor,
        buyer_user=omar,
        supplier=pack,
        supplier_user=samer,
        subject="Packing tape branding (demo)",
        buyer_msg="I need packing tape dispensers. Can you add our logo on the tape? (demo chat)",
        supplier_msg="Yes, we can quote printed tape. MOQ is 24 units. Demo reply only.",
    )
    await _chat(
        comm,
        buyer=grocery,
        buyer_user=nabil,
        supplier=levant,
        supplier_user=karim,
        subject="Olive oil restock (demo)",
        buyer_msg="Do you have 1L extra virgin in stock for next week?",
        supplier_msg="Yes — 48-carton MOQ, ready from Mkalles warehouse. Demo message.",
    )
    await _chat(
        comm,
        buyer=cafe,
        buyer_user=lara,
        supplier=pack,
        supplier_user=samer,
        subject="Takeaway containers (demo)",
        buyer_msg="Are the food storage sets leak-proof for prep?",
        supplier_msg="Lids lock for cold storage. Not for microwave. Demo reply.",
    )
    await _chat(
        comm,
        buyer=hotel,
        buyer_user=rita,
        supplier=levant,
        supplier_user=karim,
        subject="Pasta lead time (demo)",
        buyer_msg="Can you ship 24 cartons of durum pasta this week?",
        supplier_msg="Yes, 5-day lead time from confirmation. Demo reply.",
    )
    await _chat(
        comm,
        buyer=beirut,
        buyer_user=sara,
        supplier=cedar,
        supplier_user=maya,
        subject="Brick delivery window (demo)",
        buyer_msg="Can the brick palettes be dropped at Hamra before noon?",
        supplier_msg="Morning slot is available from the Port Free Zone. Demo message.",
    )
    await _chat(
        comm,
        buyer=beirut,
        buyer_user=sara,
        supplier=bekaa,
        supplier_user=rami,
        subject="Printer quote (demo)",
        buyer_msg="Need 4 inkjet printers for branches. Any volume break after 8?",
        supplier_msg="Volume price starts at 8 units. Demo quotation terms only.",
    )
    await _chat(
        comm,
        buyer=catering,
        buyer_user=fadia,
        supplier=pack,
        supplier_user=samer,
        subject="Storage set branding (demo)",
        buyer_msg="Can the storage lids be labelled with a small logo?",
        supplier_msg="Yes, print MOQ is 20 sets. Demo reply.",
    )

    await _insert_sourcing_demo(
        buyer=harbor,
        buyer_user=omar,
        prompt=(
            "I need packing tape and airtight food storage for a cafe commissary. "
            "They should be durable and suitable for daily prep."
        ),
        concept_name="Cafe packing and storage kit",
        matches=[
            (tape, pack, 0.92, RelevanceLabel.HIGHLY_RELEVANT, "Packing tape from the packaging supplier"),
            (storage, pack, 0.84, RelevanceLabel.RELEVANT, "Food storage from the same supplier"),
            (oil, levant, 0.35, RelevanceLabel.PARTIAL, "Food supplier, not packing"),
        ],
    )
    await _insert_sourcing_demo(
        buyer=grocery,
        buyer_user=nabil,
        prompt="Need wholesale olive oil in 1L bottles, approximately 48 cartons, plus pasta.",
        concept_name="Bulk Extra Virgin Olive Oil 1L",
        matches=[
            (oil, levant, 0.88, RelevanceLabel.HIGHLY_RELEVANT, "Closest listed olive oil SKU"),
            (pasta, levant, 0.64, RelevanceLabel.RELEVANT, "Same pantry supplier"),
            (tea, saida, 0.40, RelevanceLabel.PARTIAL, "Related Lebanese grocery"),
        ],
    )

    now = utc_now()
    for buyer_doc, desc, btype, loc, reqs, cats in (
        (
            harbor,
            "Synthetic hotel/restaurant buyer stocking F&B disposables.",
            "hospitality",
            "Beirut",
            ["packing tape", "food storage", "olive oil"],
            ["packaging", "food"],
        ),
        (
            grocery,
            "Synthetic neighborhood grocery restocking pantry staples.",
            "retail",
            "Nabatieh",
            ["olive oil", "pasta", "bread"],
            ["food"],
        ),
        (
            cafe,
            "Synthetic cafe group buying herbal tea and food storage.",
            "hospitality",
            "Zahle",
            ["herbal tea", "food storage", "olive oil"],
            ["packaging", "food"],
        ),
    ):
        await mongo_manager.collection(CollectionName.BUSINESS_PROCUREMENT_PROFILES).insert_one(
            {
                "_id": ObjectId(),
                "business_account_id": buyer_doc["_id"],
                "business_description": desc,
                "business_type": btype,
                "location": loc,
                "product_requirements": reqs,
                "categories": cats,
                "purchase_frequency": "monthly",
                "ai_summary": "Demo procurement profile.",
                "created_at": now,
                "updated_at": now,
                "is_demo_seed": True,
                "data_source": "synthetic_demo",
            }
        )

    notif_count = await mongo_manager.collection(CollectionName.NOTIFICATIONS).count_documents({})
    if notif_count < 20:
        await notify(
            recipient_business_id=harbor["_id"],
            type="QUOTATION_RECEIVED",
            title="New quotation received (demo)",
            message="A demo quotation is waiting on an RFQ.",
            reference_type="rfq",
        )
        await notify(
            recipient_business_id=pack["_id"],
            type="RFQ_RECEIVED",
            title="RFQ response requested (demo)",
            message="A buyer published a demo RFQ in your category.",
            reference_type="rfq",
        )
        await notify(
            recipient_user_id=str(omar["_id"]),
            recipient_business_id=harbor["_id"],
            type="SUPPLIER_VERIFICATION",
            title="Supplier verification status (demo)",
            message="Demo notice only — not a real verification event.",
        )

    return {
        "rfqs": await mongo_manager.collection(CollectionName.RFQS).count_documents({}),
        "quotations": await mongo_manager.collection(CollectionName.QUOTATIONS).count_documents({}),
        "orders": await mongo_manager.collection(CollectionName.ORDERS).count_documents({}),
        "invoices": await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).count_documents(
            {}
        ),
        "payments": await mongo_manager.collection(CollectionName.PAYMENTS).count_documents({}),
        "reviews": await mongo_manager.collection(CollectionName.REVIEWS).count_documents({}),
        "notifications": await mongo_manager.collection(
            CollectionName.NOTIFICATIONS
        ).count_documents({}),
        "conversations": await mongo_manager.collection(
            CollectionName.CONVERSATIONS
        ).count_documents({}),
        "sourcing_requests": await mongo_manager.collection(
            CollectionName.SOURCING_REQUESTS
        ).count_documents({}),
    }
