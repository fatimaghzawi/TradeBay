"""Consistent API response envelopes."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0


class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta


def success(data: T, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "meta": meta or {}}


def paginated(
    items: list[Any],
    *,
    page: int = 1,
    page_size: int = 20,
    total: int = 0,
) -> dict[str, Any]:
    return {
        "data": items,
        "meta": {"page": page, "page_size": page_size, "total": total},
    }
