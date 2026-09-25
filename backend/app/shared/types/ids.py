
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BeforeValidator, Field

ObjectIdStr = Annotated[str, Field(min_length=24, max_length=24, pattern=r"^[a-fA-F0-9]{24}$")]

def _coerce_object_id(value: Any) -> str:
    if value is None:
        raise ValueError("ObjectId is required")
    text = str(value)
    if not isinstance(text, str):
        raise TypeError("ObjectId must be a string")
    return text

CoercedObjectId = Annotated[str, BeforeValidator(_coerce_object_id)]

def _to_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError(f"Invalid ObjectId: {value!r}")

def _to_optional_object_id(value: Any) -> ObjectId | None:
    if value is None:
        return None
    return _to_object_id(value)

DocumentId = Annotated[ObjectId, BeforeValidator(_to_object_id)]
"""Required ObjectId reference. Accepts a 24-hex string or an ObjectId."""

OptionalDocumentId = Annotated[ObjectId | None, BeforeValidator(_to_optional_object_id)]
"""Nullable ObjectId reference."""
