
from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

@pytest.mark.anyio
async def test_planner_session_to_generate(
    client: AsyncClient,
    registered_user: dict[str, Any],
) -> None:
                              
    token = registered_user.get("verification_token")
    if token:
        await client.post("/api/v1/auth/verify-email", json={"token": token})
    await _login(client, registered_user["email"], registered_user["password"])

    created = await client.post("/api/v1/business-planner/sessions", json={})
    assert created.status_code == 200, created.text
    session = created.json()["data"]
    session_id = session["id"]

    for step, answers in [
        ("goal", {"business_goal": "Electronics", "unsure_goal": False}),
        ("location", {"location": "Tyre"}),
        ("budget", {"budget_range": "3000_5000", "inventory_budget": "1500"}),
        (
            "preferences",
            {
                "business_model": ["Online"],
                "experience": "Beginner",
                "time_commitment": "Part-time",
                "risk_preference": "Balanced",
                "desired_margin": "20-30%",
                "product_preferences": ["Low-MOQ products", "Essential products"],
            },
        ),
    ]:
        resp = await client.post(
            f"/api/v1/business-planner/sessions/{session_id}/answers",
            json={"step": step, "answers": answers},
        )
        assert resp.status_code == 200, resp.text

    next_q = await client.post(f"/api/v1/business-planner/sessions/{session_id}/next-questions")
    assert next_q.status_code == 200, next_q.text

    generated = await client.post(f"/api/v1/business-planner/sessions/{session_id}/generate")
    assert generated.status_code == 200, generated.text
    plan = generated.json()["data"]
    assert plan["id"]
    assert plan["location"] == "Tyre"
    assert "financial_projection" in plan
    assert plan["financial_projection"].get("label")
    assert "budget_allocation" in plan
    assert isinstance(plan["items"], list)

    got = await client.get(f"/api/v1/business-plans/{plan['id']}")
    assert got.status_code == 200
    detail = got.json()["data"]
    assert detail["id"] == plan["id"]

    preview = await client.post(f"/api/v1/business-plans/{plan['id']}/rfq-preview")
    assert preview.status_code == 200
    body = preview.json()["data"]
    assert body["publishable"] is False
    assert "rfq_draft" in body

    assistant = await client.post(
        f"/api/v1/business-plans/{plan['id']}/assistant",
        json={"message": "Why did you choose these products?"},
    )
    assert assistant.status_code == 200
    assert assistant.json()["data"]["reply"]

    listed = await client.get("/api/v1/business-plans")
    assert listed.status_code == 200
    assert any(row["id"] == plan["id"] for row in listed.json()["data"])

    session_get = await client.get(f"/api/v1/business-planner/sessions/{session_id}")
    assert session_get.status_code == 200
    assert session_get.json()["data"]["id"] == session_id

    regen = await client.post(
        f"/api/v1/business-plans/{plan['id']}/regenerate",
        json={"reason": "Lower initial investment"},
    )
    assert regen.status_code == 200, regen.text
    new_plan = regen.json()["data"]
    assert new_plan["id"] != plan["id"]
    assert new_plan["parent_plan_id"] == plan["id"]
    assert int(new_plan["version"]) == int(plan.get("version") or 1) + 1

    draft = await client.post(f"/api/v1/business-plans/{new_plan['id']}/sourcing-draft")
    assert draft.status_code == 200, draft.text
    draft_body = draft.json()["data"]
    assert draft_body["status"] == "DRAFT"
    assert draft_body["sourcing_request_id"]
    assert "not send" in draft_body["message"].lower() or "review" in draft_body["message"].lower()

@pytest.mark.anyio
async def test_planner_ownership_enforced(
    client: AsyncClient,
    registered_user: dict[str, Any],
) -> None:
    token = registered_user.get("verification_token")
    if token:
        await client.post("/api/v1/auth/verify-email", json={"token": token})
    await _login(client, registered_user["email"], registered_user["password"])

    created = await client.post("/api/v1/business-planner/sessions", json={})
    session_id = created.json()["data"]["id"]
    await client.post(
        f"/api/v1/business-planner/sessions/{session_id}/answers",
        json={"step": "goal", "answers": {"business_goal": "Fashion", "unsure_goal": False}},
    )
    await client.post(
        f"/api/v1/business-planner/sessions/{session_id}/answers",
        json={"step": "location", "answers": {"location": "Beirut"}},
    )
    await client.post(
        f"/api/v1/business-planner/sessions/{session_id}/answers",
        json={"step": "budget", "answers": {"budget_range": "5000_10000"}},
    )
    await client.post(
        f"/api/v1/business-planner/sessions/{session_id}/answers",
        json={
            "step": "preferences",
            "answers": {
                "business_model": ["Both"],
                "experience": "Some experience",
                "risk_preference": "Conservative",
                "desired_margin": "30-40%",
                "product_preferences": ["High-margin products"],
            },
        },
    )
    plan = (
        await client.post(f"/api/v1/business-planner/sessions/{session_id}/generate")
    ).json()["data"]

                                     
    client.cookies.clear()
    forbidden = await client.get(f"/api/v1/business-plans/{plan['id']}")
    assert forbidden.status_code in {401, 403}
