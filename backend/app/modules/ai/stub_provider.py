from __future__ import annotations

from typing import Any

from app.modules.ai.provider import AIProvider


class StubAIProvider(AIProvider):
    """Deterministic stub for local/dev/test. No external calls."""

    async def generate(self, *, prompt: str, system: str | None = None) -> str:
        _ = system
        return f"[stub] Suggestion based on {len(prompt)} chars of context."

    async def structured_output(
        self, *, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> dict[str, Any]:
        _ = prompt, system
        return {"type": schema.get("title", "suggestion"), "items": []}
