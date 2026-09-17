"""Postal address value object.

Embedded rather than a collection — an address is never queried on its own. Used by
business accounts, RFQ destinations, order shipping/billing, shipments, and letterhead.
"""

from __future__ import annotations

from app.shared.types.document import MongoEmbedded


class AddressEmbedded(MongoEmbedded):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
