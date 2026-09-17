"""AI provider abstraction. Domain services depend on this, not a concrete vendor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, *, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def structured_output(
        self, *, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> dict[str, Any]:
        raise NotImplementedError
