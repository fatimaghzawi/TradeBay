from __future__ import annotations

from typing import Any


class NegotiationService:
    async def open_thread(self, *, quotation_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def post_message(self, *, thread_id: str, body: str) -> dict[str, Any]:
        raise NotImplementedError
