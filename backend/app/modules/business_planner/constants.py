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


class ItemSourceType(StrEnum):
    MARKETPLACE = "MARKETPLACE"
    AI_ESTIMATE = "AI_ESTIMATE"


class PlannerSessionStatus(StrEnum):
    COLLECTING = "COLLECTING"
    READY = "READY"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class MilestoneStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    SKIPPED = "SKIPPED"


class PlannerMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# Discovery step keys (frontend + session answers)
STEP_GOAL = "goal"
STEP_LOCATION = "location"
STEP_BUDGET = "budget"
STEP_PREFERENCES = "preferences"
STEP_ADAPTIVE = "adaptive"

BUDGET_RANGES: dict[str, tuple[str | None, str | None]] = {
    "under_1000": ("0", "1000"),
    "1000_3000": ("1000", "3000"),
    "3000_5000": ("3000", "5000"),
    "5000_10000": ("5000", "10000"),
    "10000_25000": ("10000", "25000"),
    "25000_plus": ("25000", None),
    "unknown": (None, None),
}

DEFAULT_BUDGET_SPLIT = {
    "inventory": "0.45",
    "equipment": "0.08",
    "rent": "0.15",
    "marketing": "0.08",
    "logistics": "0.07",
    "operations": "0.05",
    "reserve": "0.07",
    "working_capital": "0.05",
}
