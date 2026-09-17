"""SourcingAssistantService — produces suggestions; never mutates orders/inventory/finance."""

from __future__ import annotations

from typing import Any

from app.modules.ai.provider import AIProvider
from app.modules.ai.stub_provider import StubAIProvider


class SourcingAssistantService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider or StubAIProvider()

    async def suggest(self, *, query: str) -> dict[str, Any]:
        text = await self.provider.generate(
            prompt=query,
            system="You are a B2B sourcing assistant. Suggest only; do not invent stock or prices.",
        )
        return {
            "summary": text,
            "suggested_product_ids": [],
            "notes": [
                "AI suggestions are non-authoritative.",
                "Core catalog/procurement services remain the source of truth.",
            ],
        }
