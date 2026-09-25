
from bson import ObjectId
from bson.errors import InvalidId

from app.core.exceptions import BadRequestError


def parse_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise BadRequestError("Invalid identifier", details={"id": value}) from exc

def is_valid_object_id(value: str) -> bool:
    return ObjectId.is_valid(value)
