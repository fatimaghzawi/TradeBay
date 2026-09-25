
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

    model_config = ConfigDict(extra="ignore", populate_by_name=True, arbitrary_types_allowed=True)

class MongoDocument(MongoEmbedded):

    id: OptionalDocumentId = Field(default=None, alias="_id")

    def to_mongo(self, *, exclude_none: bool = False) -> dict[str, Any]:
        payload = self.model_dump(by_alias=True, exclude_none=exclude_none)
        if payload.get("_id") is None:
            payload.pop("_id", None)
        return {key: _encode(value) for key, value in payload.items()}
