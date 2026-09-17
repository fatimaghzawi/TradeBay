from __future__ import annotations

from typing import Any

from app.modules.procurement.constants import SHIPMENT_STATUS_TRANSITIONS, ShipmentStatus
from app.modules.procurement.repository import ShipmentRepository


class ShipmentService:
    def __init__(self, shipment_repository: ShipmentRepository) -> None:
        self._shipments = shipment_repository

    async def create_for_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def transition_status(self, shipment_id: str, target: ShipmentStatus) -> dict[str, Any]:
        _ = SHIPMENT_STATUS_TRANSITIONS
        raise NotImplementedError
