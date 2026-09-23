"""Validation error envelope must stay JSON-serializable for ORJSONResponse."""

import asyncio

from app.core.exceptions import register_exception_handlers
from app.modules.identity.schemas import RegisterRequest
from app.shared.schemas.response import success
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def test_custom_password_validator_returns_422_not_500() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/register")
    async def register(body: RegisterRequest) -> dict[str, object]:
        return success({"ok": True})

    async def _run() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/register",
                json={
                    "email": "user@example.com",
                    "password": "NoDigitsHere",
                    "first_name": "A",
                    "last_name": "B",
                },
            )
            assert response.status_code == 422
            body = response.json()
            assert body["error"]["code"] == "VALIDATION_ERROR"
            assert "Password must include at least one number" in body["error"]["message"]

    asyncio.run(_run())
