
from __future__ import annotations

from app.shared.types.document import MongoEmbedded


class AddressEmbedded(MongoEmbedded):

    street: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    district: str | None = None
    governorate: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
