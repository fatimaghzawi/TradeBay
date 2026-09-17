from __future__ import annotations

from typing import Any

from app.modules.ai.provider import AIProvider
from app.modules.ai.stub_provider import StubAIProvider


class RecommendationService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider or StubAIProvider()

    async def recommend(self, *, limit: int = 10) -> dict[str, Any]:
        payload = await self.provider.structured_output(
            prompt=f"Recommend up to {limit} products",
            schema={"title": "recommendations", "type": "object"},
        )
        return {"items": payload.get("items", []), "limit": limit}
