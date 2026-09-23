"""Procurement domain errors."""

from __future__ import annotations

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class RFQNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("RFQ not found")


class QuotationNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Quotation not found")


class OrderNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Purchase order not found")


class ShipmentNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Shipment not found")


class ProcurementForbiddenError(ForbiddenError):
    def __init__(self, message: str = "You do not have access to this procurement record") -> None:
        super().__init__(message)


class ProcurementValidationError(BadRequestError):
    pass


class ProcurementConflictError(ConflictError):
    pass


class ProductRFQValidationError(ProcurementValidationError):
    """Product RFQ invariant violations (ownership, inactive product, etc.)."""


class SourcingRFQValidationError(ProcurementValidationError):
    """Sourcing RFQ invariant violations."""
