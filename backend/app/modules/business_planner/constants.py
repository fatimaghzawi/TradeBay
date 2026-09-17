from enum import StrEnum


class BusinessPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SAVED = "SAVED"
    CONVERTED_TO_SOURCING = "CONVERTED_TO_SOURCING"


class PlanItemPriority(StrEnum):
    ESSENTIAL = "ESSENTIAL"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"


class PriceEstimateSourceType(StrEnum):
    MARKETPLACE = "MARKETPLACE"
    HISTORICAL = "HISTORICAL"
    AI_ESTIMATE = "AI_ESTIMATE"
