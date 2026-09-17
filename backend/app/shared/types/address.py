"""Postal address value object.

Embedded rather than a collection — an address is never queried on its own. Used by
business accounts, RFQ destinations, order shipping/billing, shipments, and letterhead.
"""

from __future__ import annotations

from app.shared.types.document import MongoEmbedded


class AddressEmbedded(MongoEmbedded):
    """ERD embed: street / city / district / governorate / postal_code.

    `line1`/`state`/`country` are accepted aliases so older documents still load.
    """

    street: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    district: str | None = None
    governorate: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
