from enum import StrEnum


class SourcingRequestStatus(StrEnum):
    DRAFT = "DRAFT"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"
    CONVERTED_TO_RFQ = "CONVERTED_TO_RFQ"


class AvailabilityStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    IN_STOCK = "IN_STOCK"
    LIMITED = "LIMITED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
