
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True)
class TrackingUpdate:
    status: str
    description: str | None = None
    location: str | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    source: str = "manual"
    tracking_number: str | None = None

class TrackingProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch_updates(self, *, tracking_number: str, carrier: str | None = None) -> list[TrackingUpdate]:
        raise NotImplementedError

    def parse_webhook(self, payload: dict[str, Any]) -> TrackingUpdate | None:
        return None

class ManualTrackingProvider(TrackingProvider):
    name = "manual"

    async def fetch_updates(self, *, tracking_number: str, carrier: str | None = None) -> list[TrackingUpdate]:
        return []

class CarrierWebhookProvider(TrackingProvider):

    name = "carrier_webhook"

    STATUS_MAP: ClassVar[dict[str, str]] = {
        "preparing": "preparing",
        "label_created": "preparing",
        "picked_up": "shipped",
        "shipped": "shipped",
        "in_transit": "in_transit",
        "intransit": "in_transit",
        "out_for_delivery": "out_for_delivery",
        "outfordelivery": "out_for_delivery",
        "delivered": "delivered",
        "failed": "failed",
        "exception": "failed",
    }

    async def fetch_updates(self, *, tracking_number: str, carrier: str | None = None) -> list[TrackingUpdate]:
                                                                  
        return []

    def parse_webhook(self, payload: dict[str, Any]) -> TrackingUpdate | None:
        tracking_number = (
            payload.get("tracking_number")
            or payload.get("trackingNumber")
            or (payload.get("tracking") or {}).get("number")
        )
        raw_status = str(
            payload.get("status")
            or payload.get("event")
            or (payload.get("tracking") or {}).get("status")
            or ""
        ).strip().lower().replace(" ", "_").replace("-", "_")
        status = self.STATUS_MAP.get(raw_status)
        if not tracking_number or not status:
            return None
        occurred = payload.get("occurred_at") or payload.get("timestamp")
        occurred_at = None
        if isinstance(occurred, datetime):
            occurred_at = occurred
        elif isinstance(occurred, str) and occurred:
            try:
                occurred_at = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
            except ValueError:
                occurred_at = None
        return TrackingUpdate(
            status=status,
            description=payload.get("description") or payload.get("message") or f"Carrier update: {raw_status}",
            location=payload.get("location") or payload.get("city"),
            occurred_at=occurred_at,
            metadata={"raw_status": raw_status, "provider": payload.get("provider")},
            source=self.name,
            tracking_number=str(tracking_number),
        )

_PROVIDERS: dict[str, TrackingProvider] = {
    ManualTrackingProvider.name: ManualTrackingProvider(),
    CarrierWebhookProvider.name: CarrierWebhookProvider(),
}

def get_tracking_provider(name: str | None = None) -> TrackingProvider:
    if not name:
        return _PROVIDERS[ManualTrackingProvider.name]
    return _PROVIDERS.get(name, _PROVIDERS[ManualTrackingProvider.name])

def list_tracking_providers() -> list[str]:
    return list(_PROVIDERS.keys())
