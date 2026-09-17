from __future__ import annotations

from typing import Any

from app.modules.trust.repository import ReviewRepository


class ReviewService:
    def __init__(self, review_repository: ReviewRepository) -> None:
        self._reviews = review_repository

    async def submit_review(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
