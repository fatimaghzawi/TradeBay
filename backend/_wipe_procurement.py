"""Clear procurement, chat, negotiation, order, and related finance data."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


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


COLS = [
    "rfqs",
    "rfq_items",
    "quotations",
    "quotation_items",
    "orders",
    "order_items",
    "shipments",
    "shipment_items",
    "negotiations",
    "negotiation_offers",
    "negotiation_offer_items",
    "carts",
    "cart_items",
    "conversations",
    "conversation_participants",
    "messages",
    "sourcing_requests",
    "sourcing_request_items",
    "sourcing_recommendations",
    "customer_invoices",
    "payments",
    "credit_notes",
    "refunds",
    "financial_transactions",
    "commission_records",
    "supplier_payables",
    "supplier_payouts",
    "settlement_batches",
    "platform_transactions",
    "reviews",
    "disputes",
    "notifications",
]


async def main() -> None:
    _load_dotenv()
    uri = os.environ["MONGODB_URI"]
    db_name = os.environ.get("MONGODB_DATABASE", "tradebay")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=30000)
    db = client[db_name]
    print(f"database: {db_name}")
    total = 0
    for name in COLS:
        result = await db[name].delete_many({})
        total += result.deleted_count
        print(f"  {name}: {result.deleted_count}")
    counters = await db["document_counters"].delete_many({})
    print(f"  document_counters: {counters.deleted_count}")
    total += counters.deleted_count
    client.close()
    print(f"done — {total} documents removed")


if __name__ == "__main__":
    asyncio.run(main())
