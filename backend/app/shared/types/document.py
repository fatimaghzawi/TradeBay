"""Base shapes for MongoDB documents.

`models.py` in each module describes what is *stored*; `schemas.py` describes
what crosses the API boundary. These bases belong to the storage side, so they
speak BSON types (ObjectId, Decimal128) rather than JSON-friendly ones.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import Decimal128
from pydantic import BaseModel, ConfigDict, Field

from app.shared.types.ids import OptionalDocumentId


def _encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return Decimal128(value)
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value


class MongoEmbedded(BaseModel):
    """An object embedded inside a parent document. Has no `_id`."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, arbitrary_types_allowed=True)


class MongoDocument(MongoEmbedded):
    """A document stored in its own collection."""

    id: OptionalDocumentId = Field(default=None, alias="_id")

    def to_mongo(self, *, exclude_none: bool = False) -> dict[str, Any]:
        """Dump ready for insert/update: Decimal becomes Decimal128, unset `_id` is dropped."""
        payload = self.model_dump(by_alias=True, exclude_none=exclude_none)
        if payload.get("_id") is None:
            payload.pop("_id", None)
        return {key: _encode(value) for key, value in payload.items()}
