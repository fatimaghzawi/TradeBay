
from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from typing import Any

import pytest
from app.db.mongodb import mongo_manager
from app.modules.catalog.exceptions import InsufficientReservedError
from app.modules.catalog.service import CatalogService
from app.modules.identity.constants import SYSTEM_ROLE_PLATFORM_ADMIN
from app.modules.identity.email import MemoryEmailSender
from app.shared.utils.datetime import utc_now
from bson import ObjectId
from httpx import AsyncClient


async def _verify_email(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/auth/email/verify", json={"token": token})
    assert response.status_code == 200, response.text

async def _register(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    *,
    business_type: str = "supplier",
    business_name: str | None = None,
) -> dict[str, Any]:
    email = f"{business_type}_{os.urandom(4).hex()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Sam",
            "last_name": "Supplier" if business_type == "supplier" else "Buyer",
            "business_name": business_name or f"{business_type.title()} Co {os.urandom(2).hex()}",
            "business_type": business_type,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    token = email_inbox.last_token(to=email, template="email_verification")
    assert token
    client.cookies = response.cookies
    await _verify_email(client, token)
    return {
        "email": email,
        "password": "SecurePass123!",
        "user": payload["user"],
        "business": payload.get("business"),
        "cookies": response.cookies,
    }

async def _mark_supplier_verified(business_id: str) -> None:
    now = utc_now()
    await mongo_manager.database["business_accounts"].update_one(
        {"_id": ObjectId(business_id)},
        {"$set": {"status": "verified", "updated_at": now}},
    )
    await mongo_manager.database["supplier_profiles"].update_one(
        {"business_account_id": ObjectId(business_id)},
        {
            "$set": {
                "verification_status": "verified",
                "verified_at": now,
                "updated_at": now,
            }
        },
    )

async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    client.cookies = response.cookies

async def _elevate_platform_admin(user_id: str) -> str:
    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    assert platform is not None
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    assert role is not None
    now = utc_now()
    await mongo_manager.database["business_memberships"].update_one(
        {
            "user_id": ObjectId(user_id),
            "business_account_id": platform["_id"],
        },
        {
            "$set": {
                "user_id": ObjectId(user_id),
                "business_account_id": platform["_id"],
                "role_id": role["_id"],
                "status": "active",
                "joined_at": now,
                "created_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    return str(platform["_id"])

async def _switch_business(client: AsyncClient, business_id: str) -> None:
    response = await client.post(
        "/api/v1/businesses/current/switch",
        json={"business_id": business_id},
    )
    assert response.status_code == 200, response.text

async def _seed_category(client: AsyncClient, email: str, password: str, user_id: str) -> str:
    platform_id = await _elevate_platform_admin(user_id)
    await _login(client, email, password)
    await _switch_business(client, platform_id)
    created = await client.post(
        "/api/v1/catalog/categories",
        json={"name": f"Electronics {os.urandom(2).hex()}", "description": "Root"},
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]

@pytest.fixture
async def verified_supplier(
    client: AsyncClient, email_inbox: MemoryEmailSender
) -> dict[str, Any]:
    supplier = await _register(client, email_inbox, business_type="supplier")
    business_id = supplier["business"]["id"]
    await _mark_supplier_verified(business_id)
    await _login(client, supplier["email"], supplier["password"])
    category_id = await _seed_category(
        client, supplier["email"], supplier["password"], supplier["user"]["id"]
    )
                                                       
    await _switch_business(client, business_id)
    supplier["category_id"] = category_id
    return supplier

@pytest.mark.asyncio
async def test_category_tree_and_cycle_prevention(
    client: AsyncClient, email_inbox: MemoryEmailSender
) -> None:
    admin = await _register(client, email_inbox, business_type="buyer", business_name="Admin Co")
    platform_id = await _elevate_platform_admin(admin["user"]["id"])
    await _login(client, admin["email"], admin["password"])
    await _switch_business(client, platform_id)

    root = await client.post(
        "/api/v1/catalog/categories",
        json={"name": "Electronics", "slug": f"electronics-{os.urandom(2).hex()}"},
    )
    assert root.status_code == 200, root.text
    root_id = root.json()["data"]["id"]

    child = await client.post(
        "/api/v1/catalog/categories",
        json={
            "name": "Computer Accessories",
            "parent_category_id": root_id,
            "slug": f"accessories-{os.urandom(2).hex()}",
        },
    )
    assert child.status_code == 200, child.text
    child_id = child.json()["data"]["id"]

    cycle = await client.patch(
        f"/api/v1/catalog/categories/{root_id}",
        json={"parent_category_id": child_id},
    )
    assert cycle.status_code == 400, cycle.text

    bad_parent = await client.post(
        "/api/v1/catalog/categories",
        json={
            "name": "Orphan",
            "parent_category_id": "000000000000000000000000",
        },
    )
    assert bad_parent.status_code == 404, bad_parent.text

@pytest.mark.asyncio
async def test_supplier_product_sku_and_ownership(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    verified_supplier: dict[str, Any],
) -> None:
    category_id = verified_supplier["category_id"]
    created = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "sku": "CHG-001",
            "name": "USB-C Charger",
            "unit": "piece",
            "origin": "Turkey",
            "moq": 50,
            "lead_time_days": 3,
        },
    )
    assert created.status_code == 200, created.text
    product = created.json()["data"]
    assert product["sku"] == "CHG-001"
    assert product["origin"] == "Turkey"
    assert product["moq"] == 50
    assert product["lead_time_days"] == 3
    assert product["status"] == "draft"
    assert product["inventory"]["available_quantity"] in {"0", "0.0", "0.00"}

    dup = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "sku": "chg-001",
            "name": "Duplicate SKU",
            "moq": 10,
        },
    )
    assert dup.status_code == 409, dup.text

    bad_moq = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "sku": "CHG-002",
            "name": "Bad MOQ",
            "moq": 0,
        },
    )
    assert bad_moq.status_code == 422, bad_moq.text

    bad_lead = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "sku": "CHG-003",
            "name": "Bad lead",
            "moq": 1,
            "lead_time_days": -1,
        },
    )
    assert bad_lead.status_code == 422, bad_lead.text

                                             
    other = await _register(client, email_inbox, business_type="supplier", business_name="Other Supply")
    await _mark_supplier_verified(other["business"]["id"])
    await _login(client, other["email"], other["password"])
                              
    other_product = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "sku": "CHG-001",
            "name": "USB-C Charger B",
            "moq": 20,
        },
    )
    assert other_product.status_code == 200, other_product.text

                                            
    await _login(client, other["email"], other["password"])
    stolen = await client.patch(
        f"/api/v1/catalog/products/{product['id']}",
        json={"name": "Hijacked"},
    )
    assert stolen.status_code == 403, stolen.text

@pytest.mark.asyncio
async def test_pricing_tiers_and_match(
    client: AsyncClient, verified_supplier: dict[str, Any]
) -> None:
    product = (
        await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": verified_supplier["category_id"],
                "sku": f"PRC-{os.urandom(2).hex()}",
                "name": "Tiered Charger",
                "moq": 50,
            },
        )
    ).json()["data"]
    product_id = product["id"]

    t1 = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 50, "max_quantity": 99, "unit_price": "4.50"},
    )
    assert t1.status_code == 200, t1.text

    overlap = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 80, "max_quantity": 120, "unit_price": "4.20"},
    )
    assert overlap.status_code == 409, overlap.text

    zero = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 100, "max_quantity": 200, "unit_price": "0"},
    )
    assert zero.status_code == 422, zero.text

    bad_range = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 200, "max_quantity": 100, "unit_price": "3.00"},
    )
    assert bad_range.status_code == 422, bad_range.text

    t2 = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 100, "max_quantity": 499, "unit_price": "4.10"},
    )
    assert t2.status_code == 200, t2.text
    t3 = await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 500, "max_quantity": None, "unit_price": "3.70"},
    )
    assert t3.status_code == 200, t3.text

    matched = await client.get(
        f"/api/v1/catalog/products/{product_id}/prices",
        params={"quantity": 250},
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["meta"]["matched_tier"]["unit_price"] == "4.10"

@pytest.mark.asyncio
async def test_inventory_workflows_and_concurrency(
    client: AsyncClient, verified_supplier: dict[str, Any]
) -> None:
    product = (
        await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": verified_supplier["category_id"],
                "sku": f"INV-{os.urandom(2).hex()}",
                "name": "Stocked Charger",
                "moq": 10,
            },
        )
    ).json()["data"]
    product_id = product["id"]

                                                       
    await client.post(
        f"/api/v1/catalog/products/{product_id}/prices",
        json={"min_quantity": 10, "max_quantity": None, "unit_price": "5.00"},
    )

    stocked = await client.post(
        f"/api/v1/inventory/products/{product_id}/stock",
        json={"quantity": "100"},
    )
    assert stocked.status_code == 200, stocked.text
    assert stocked.json()["data"]["inventory"]["available_quantity"] == "100"
    assert stocked.json()["data"]["transaction"]["transaction_type"] == "stock_received"

    reserved = await client.post(
        f"/api/v1/inventory/products/{product_id}/reserve",
        json={"quantity": "20"},
    )
    assert reserved.status_code == 200, reserved.text
    inv = reserved.json()["data"]["inventory"]
    assert inv["available_quantity"] == "80"
    assert inv["reserved_quantity"] == "20"

    over = await client.post(
        f"/api/v1/inventory/products/{product_id}/reserve",
        json={"quantity": "100"},
    )
    assert over.status_code == 409, over.text

    released = await client.post(
        f"/api/v1/inventory/products/{product_id}/release",
        json={"quantity": "20"},
    )
    assert released.status_code == 200, released.text
    inv = released.json()["data"]["inventory"]
    assert inv["available_quantity"] == "100"
    assert inv["reserved_quantity"] == "0"

    await client.post(
        f"/api/v1/inventory/products/{product_id}/reserve",
        json={"quantity": "30"},
    )
    sold = await client.post(
        f"/api/v1/inventory/products/{product_id}/sale",
        json={"quantity": "30"},
    )
    assert sold.status_code == 200, sold.text
    inv = sold.json()["data"]["inventory"]
    assert inv["available_quantity"] == "70"
    assert inv["reserved_quantity"] == "0"

    negative = await client.post(
        f"/api/v1/inventory/products/{product_id}/stock",
        json={"quantity": "-5"},
    )
    assert negative.status_code == 422, negative.text

    txs = await client.get(f"/api/v1/inventory/products/{product_id}/transactions")
    assert txs.status_code == 200, txs.text
    assert txs.json()["meta"]["total"] >= 4

                                             
    activated = await client.patch(
        f"/api/v1/catalog/products/{product_id}",
        json={"status": "active"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["data"]["status"] == "active"

                                                
    await client.post(
        f"/api/v1/inventory/products/{product_id}/stock",
        json={"quantity": "10"},
    )
                                      
    results = await asyncio.gather(
        client.post(
            f"/api/v1/inventory/products/{product_id}/reserve",
            json={"quantity": "50"},
        ),
        client.post(
            f"/api/v1/inventory/products/{product_id}/reserve",
            json={"quantity": "50"},
        ),
        return_exceptions=True,
    )
    statuses = []
    for result in results:
        if isinstance(result, Exception):
            statuses.append(500)
        else:
            statuses.append(result.status_code)
    assert 200 in statuses
                                                                                                           
    success_count = statuses.count(200)
    assert success_count == 1, statuses
    assert 409 in statuses

    final = await client.get(f"/api/v1/inventory/products/{product_id}")
    assert final.status_code == 200, final.text
    available = float(final.json()["data"]["available_quantity"])
    reserved_qty = float(final.json()["data"]["reserved_quantity"])
    assert available + reserved_qty == 80.0

                                                                                 
                                             
    order_id = str(ObjectId())
    supplier_business_id = verified_supplier["business"]["id"]
    supplier_user_id = verified_supplier["user"]["id"]
    await CatalogService().reserve_stock(
        product_id,
        business_id=supplier_business_id,
        user_id=supplier_user_id,
        quantity=Decimal("5"),
        reference_type="order",
        reference_id=order_id,
    )
    manual_release = await client.post(
        f"/api/v1/inventory/products/{product_id}/release",
        json={"quantity": str(int(reserved_qty) + 5)},
    )
    assert manual_release.status_code == 409, manual_release.text
    for attempt in range(2):
        try:
            await CatalogService().release_stock(
                product_id,
                business_id=supplier_business_id,
                user_id=supplier_user_id,
                quantity=Decimal("5"),
                reference_type="order",
                reference_id=order_id,
            )
            assert attempt == 0
        except InsufficientReservedError:
            assert attempt == 1

@pytest.mark.asyncio
async def test_buyer_cannot_modify_supplier_catalog(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    verified_supplier: dict[str, Any],
) -> None:
    product = (
        await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": verified_supplier["category_id"],
                "sku": f"BUY-{os.urandom(2).hex()}",
                "name": "Visible later",
                "moq": 5,
            },
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/catalog/products/{product['id']}/prices",
        json={"min_quantity": 5, "max_quantity": None, "unit_price": "2.00"},
    )
    await client.post(
        f"/api/v1/inventory/products/{product['id']}/stock",
        json={"quantity": "25"},
    )
    await client.patch(
        f"/api/v1/catalog/products/{product['id']}",
        json={"status": "active"},
    )

    buyer = await _register(client, email_inbox, business_type="buyer")
    await _login(client, buyer["email"], buyer["password"])

    create_denied = await client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": verified_supplier["category_id"],
            "sku": "HACK-1",
            "name": "Nope",
            "moq": 1,
        },
    )
    assert create_denied.status_code in {403, 400}, create_denied.text

    patch_denied = await client.patch(
        f"/api/v1/catalog/products/{product['id']}",
        json={"name": "Stolen"},
    )
    assert patch_denied.status_code == 403, patch_denied.text

    stock_denied = await client.post(
        f"/api/v1/inventory/products/{product['id']}/stock",
        json={"quantity": "5"},
    )
    assert stock_denied.status_code == 403, stock_denied.text

    listed = await client.get("/api/v1/catalog/products")
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert product["id"] in ids
