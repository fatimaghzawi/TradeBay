
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.modules.catalog.constants import ProductStatus
from app.modules.identity.constants import BusinessAccountType
from app.modules.procurement.constants import RFQType, RFQVisibility
from app.modules.procurement.exceptions import (
    ProductRFQValidationError,
    SourcingRFQValidationError,
)
from app.modules.procurement.service import ProcurementService
from bson import ObjectId


def _buyer() -> dict[str, Any]:
    return {"_id": ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa"), "type": BusinessAccountType.BUYER}

def _supplier_id() -> ObjectId:
    return ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")

@pytest.mark.asyncio
async def test_create_product_rfq_rejects_missing_product() -> None:
    service = ProcurementService()
    with patch("app.modules.procurement.service.mongo_manager") as mongo:
        mongo.collection.return_value.find_one = AsyncMock(return_value=None)
        with pytest.raises(ProductRFQValidationError, match="does not exist"):
            await service.create_product_rfq(
                user_id="cccccccccccccccccccccccc",
                business=_buyer(),
                payload={"product_id": "dddddddddddddddddddddddd", "quantity": "10"},
            )

@pytest.mark.asyncio
async def test_create_product_rfq_rejects_inactive_product() -> None:
    service = ProcurementService()
    product = {
        "_id": ObjectId("dddddddddddddddddddddddd"),
        "status": ProductStatus.INACTIVE,
        "business_account_id": _supplier_id(),
        "name": "Cup",
    }
    with patch("app.modules.procurement.service.mongo_manager") as mongo:
        mongo.collection.return_value.find_one = AsyncMock(return_value=product)
        with pytest.raises(ProductRFQValidationError, match="not active"):
            await service.create_product_rfq(
                user_id="cccccccccccccccccccccccc",
                business=_buyer(),
                payload={"product_id": "dddddddddddddddddddddddd", "quantity": "10"},
            )

@pytest.mark.asyncio
async def test_create_product_rfq_rejects_self_supply() -> None:
    service = ProcurementService()
    buyer = _buyer()
    product = {
        "_id": ObjectId("dddddddddddddddddddddddd"),
        "status": ProductStatus.ACTIVE,
        "business_account_id": buyer["_id"],
        "name": "Own product",
    }
    with patch("app.modules.procurement.service.mongo_manager") as mongo:
        mongo.collection.return_value.find_one = AsyncMock(return_value=product)
        with pytest.raises(ProductRFQValidationError, match="own product"):
            await service.create_product_rfq(
                user_id="cccccccccccccccccccccccc",
                business=buyer,
                payload={"product_id": "dddddddddddddddddddddddd", "quantity": "10"},
            )

@pytest.mark.asyncio
async def test_create_product_rfq_rejects_supplier_override() -> None:
    service = ProcurementService()
    sid = _supplier_id()
    product = {
        "_id": ObjectId("dddddddddddddddddddddddd"),
        "status": ProductStatus.ACTIVE,
        "business_account_id": sid,
        "name": "Cup",
        "sku": "CC-1",
        "unit": "unit",
        "moq": 1,
    }
    with patch("app.modules.procurement.service.mongo_manager") as mongo:
        mongo.collection.return_value.find_one = AsyncMock(return_value=product)
        with pytest.raises(ProductRFQValidationError, match="can't be changed"):
            await service.create_product_rfq(
                user_id="cccccccccccccccccccccccc",
                business=_buyer(),
                payload={
                    "product_id": "dddddddddddddddddddddddd",
                    "quantity": "10",
                    "supplier_business_id": "eeeeeeeeeeeeeeeeeeeeeeee",
                },
            )

@pytest.mark.asyncio
async def test_create_sourcing_rfq_rejects_locked_supplier() -> None:
    service = ProcurementService()
    with pytest.raises(SourcingRFQValidationError, match="can't be tied"):
        await service.create_sourcing_rfq(
            user_id="cccccccccccccccccccccccc",
            business=_buyer(),
            payload={
                "title": "Cups",
                "description": "Need biodegradable cups",
                "quantity": "10000",
                "supplier_business_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
            },
        )

@pytest.mark.asyncio
async def test_create_sourcing_rfq_requires_requirement_text() -> None:
    service = ProcurementService()
    with pytest.raises(SourcingRFQValidationError, match="description"):
        await service.create_sourcing_rfq(
            user_id="cccccccccccccccccccccccc",
            business=_buyer(),
            payload={"title": "Cups", "quantity": "100"},
        )

@pytest.mark.asyncio
async def test_upsert_quotation_blocks_wrong_supplier_on_product_rfq() -> None:
    service = ProcurementService()
    rfq_id = "ffffffffffffffffffffffff"
    owner = str(_supplier_id())
    other = "eeeeeeeeeeeeeeeeeeeeeeee"
    rfq = {
        "_id": ObjectId(rfq_id),
        "status": "published",
        "rfq_type": RFQType.PRODUCT,
        "supplier_business_id": ObjectId(owner),
        "visibility": RFQVisibility.INVITED,
        "supplier_invites": [{"supplier_business_id": ObjectId(owner)}],
        "buyer_business_id": ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa"),
        "currency": "USD",
    }
    service.rfqs.get_by_id = AsyncMock(return_value=rfq)  # type: ignore[method-assign]
    service._verified_supplier_ids = AsyncMock(return_value={other})  # type: ignore[method-assign]
    service._require_supplier = MagicMock(return_value=other)  # type: ignore[method-assign]

    from app.modules.procurement.exceptions import ProcurementForbiddenError

    with pytest.raises(ProcurementForbiddenError, match="product owner"):
        await service.upsert_quotation(
            user_id="cccccccccccccccccccccccc",
            business={"_id": ObjectId(other), "type": BusinessAccountType.SUPPLIER},
            rfq_id=rfq_id,
            payload={"lines": []},
            submit=True,
        )

def test_rfq_type_constants() -> None:
    assert RFQType.PRODUCT == "product"
    assert RFQType.SOURCING == "sourcing"

def test_rfq_is_unsent_until_suppliers_are_invited() -> None:
    from app.modules.procurement.service import rfq_is_unsent

    assert rfq_is_unsent({"status": "draft", "supplier_invites": []}) is True
    assert rfq_is_unsent({"status": "published", "supplier_invites": []}) is True
    assert rfq_is_unsent({"status": "published", "supplier_invites": [{"status": "invited"}]}) is False
    assert rfq_is_unsent({"status": "cancelled", "supplier_invites": []}) is False

def test_freeze_catalog_price_ignores_later_buyer_override() -> None:
    from app.modules.procurement.service import freeze_catalog_price

    frozen = freeze_catalog_price(
        previous=Decimal("12.50"),
        looked_up=Decimal("99.00"),
        client=Decimal("1.00"),
    )
    assert frozen == Decimal("12.50")

def test_freeze_catalog_price_uses_lookup_on_first_snapshot() -> None:
    from app.modules.procurement.service import freeze_catalog_price

    frozen = freeze_catalog_price(
        previous=None,
        looked_up=Decimal("18.00"),
        client=Decimal("1.00"),
    )
    assert frozen == Decimal("18.00")

def test_group_catalog_items_by_supplier() -> None:
    from app.modules.procurement.service import group_catalog_items_by_supplier

    items = [
        {"product_id": "p1", "product_name": "A", "supplier_business_id": "s1"},
        {"product_id": "p2", "product_name": "B"},
        {"product_id": "p3", "product_name": "C"},
        {"product_name": "Open spec"},
    ]
    groups = group_catalog_items_by_supplier(
        items,
        product_owners={"p2": "s1", "p3": "s2"},
    )
    assert [row["product_name"] for row in groups["s1"]] == ["A", "B"]
    assert [row["product_name"] for row in groups["s2"]] == ["C"]
    assert [row["product_name"] for row in groups[""]] == ["Open spec"]

def test_supplier_requests_map_invite_and_quote_stages() -> None:
    rows = ProcurementService()._supplier_requests(
        items=[
            {
                "id": "i1",
                "supplier_business_id": "s1",
                "supplier_name": "Paper Co",
                "product_name": "Cups",
                "quantity": "500",
                "unit": "unit",
            }
        ],
        invites=[{"supplier_business_id": "s1", "supplier_name": "Paper Co", "status": "viewed"}],
        quotations=[{"id": "q1", "supplier_id": "s1", "status": "submitted"}],
        rfq_status="responding",
    )
    assert len(rows) == 1
    assert rows[0]["stage"] == "quoted"
    assert rows[0]["products"][0]["product_name"] == "Cups"

def test_quotation_cannot_be_edited_after_submit() -> None:
    from app.modules.procurement.service import quotation_cannot_be_edited

    assert quotation_cannot_be_edited("draft") is None
    assert quotation_cannot_be_edited("submitted") == (
        "This quotation was already submitted and cannot be changed"
    )
    assert quotation_cannot_be_edited("negotiating") == (
        "This quotation was already submitted and cannot be changed"
    )
    assert quotation_cannot_be_edited("submitted", allow_revision=True) is None
    assert quotation_cannot_be_edited("accepted") == (
        "This quotation was accepted, so it can no longer be changed."
    )
    assert quotation_cannot_be_edited("rejected") == (
        "The buyer declined this quotation, so it can no longer be changed."
    )
    assert quotation_cannot_be_edited("rejected", allow_revision=True) is None
    assert quotation_cannot_be_edited("accepted", allow_revision=True) == (
        "This quotation was accepted, so it can no longer be changed."
    )
    assert quotation_cannot_be_edited("withdrawn") == (
        "This quotation was withdrawn, so it can no longer be changed."
    )

def test_rfq_dates_must_be_future_and_ordered() -> None:
    from datetime import timedelta

    from app.modules.procurement.exceptions import ProcurementValidationError
    from app.modules.procurement.service import assert_rfq_dates
    from app.shared.utils.datetime import utc_now

    now = utc_now()
    assert_rfq_dates(None, None)
    assert_rfq_dates(now + timedelta(days=10), now + timedelta(days=3))
    with pytest.raises(ProcurementValidationError, match="quote deadline must be in the future"):
        assert_rfq_dates(None, now - timedelta(hours=1))
    with pytest.raises(ProcurementValidationError, match="can't be earlier"):
        assert_rfq_dates(now + timedelta(days=2), now + timedelta(days=5))

def test_deadline_and_validity_helpers() -> None:
    from datetime import timedelta

    from app.modules.procurement.service import quotation_expired, rfq_deadline_passed
    from app.shared.utils.datetime import utc_now

    now = utc_now()
    assert rfq_deadline_passed({"response_deadline": now - timedelta(minutes=1)})
    assert not rfq_deadline_passed({"response_deadline": now + timedelta(days=1)})
    assert not rfq_deadline_passed({})
    naive_past = (now - timedelta(days=1)).replace(tzinfo=None)
    assert quotation_expired({"valid_until": naive_past})
    assert not quotation_expired({"valid_until": None})
