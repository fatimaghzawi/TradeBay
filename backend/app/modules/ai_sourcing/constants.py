from enum import StrEnum


class SourcingRequestStatus(StrEnum):
    DRAFT = "DRAFT"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"
    CONVERTED_TO_RFQ = "CONVERTED_TO_RFQ"


class VisualSessionStatus(StrEnum):
    """AI Visual Sourcing session lifecycle."""

    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    REQUIREMENTS_READY = "REQUIREMENTS_READY"
    GENERATING_CONCEPTS = "GENERATING_CONCEPTS"
    CONCEPT_SELECTION = "CONCEPT_SELECTION"
    READY_FOR_SOURCING = "READY_FOR_SOURCING"
    CONVERTED_TO_RFQ = "CONVERTED_TO_RFQ"
    CANCELLED = "CANCELLED"


class SourcingMode(StrEnum):
    CATALOG = "catalog"
    VISUAL = "visual"


class AssetKind(StrEnum):
    LOGO = "logo"
    REFERENCE = "reference"
    DOCUMENT = "document"
    CONCEPT = "concept"


class AvailabilityStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    IN_STOCK = "IN_STOCK"
    LIMITED = "LIMITED"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class RelevanceLabel(StrEnum):
    HIGHLY_RELEVANT = "highly_relevant"
    RELEVANT = "relevant"
    PARTIAL = "partial"


class ManufacturabilityStatus(StrEnum):
    EXACT = "exact"
    WITH_MODIFICATIONS = "with_modifications"
    CANNOT_FULFILL = "cannot_fulfill"

                                                     
WEIGHT_CATEGORY = 0.28
WEIGHT_NAME = 0.30
WEIGHT_DESCRIPTION = 0.12
WEIGHT_VERIFIED = 0.12
WEIGHT_INVENTORY = 0.10
WEIGHT_MOQ = 0.08

RECOMMENDATION_LIMIT = 24
PRODUCT_CANDIDATE_LIMIT = 80
CONCEPT_BATCH_SIZE = 4
