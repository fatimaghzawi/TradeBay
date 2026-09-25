
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert response.headers.get("x-request-id")

@pytest.mark.asyncio
async def test_ready(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["mongodb"] is True

@pytest.mark.asyncio
async def test_docs_available_in_non_production(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
