"""Business Planner domain errors."""

from __future__ import annotations

from typing import Any

from app.core.constants import ErrorCode
from app.core.exceptions import AppError, BadRequestError, ForbiddenError, NotFoundError


class PlanNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Business plan not found")


class PlanNotOwnedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("You do not have access to this business plan")


class SessionNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Planner session not found")


class SessionNotOwnedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("You do not have access to this planner session")


class PlannerValidationError(BadRequestError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)


class PlannerGenerationError(AppError):
    def __init__(self, message: str = "Could not generate a business plan right now") -> None:
        super().__init__(ErrorCode.INTERNAL_ERROR, message, status_code=503)


class PlannerInsufficientDataError(BadRequestError):
    def __init__(
        self,
        message: str = "TradeBay does not currently have enough marketplace data to estimate this accurately.",
    ) -> None:
        super().__init__(message)
