"""AI Sourcing domain exceptions."""

from app.core.constants import ErrorCode
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError


class SourcingRequestNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Sourcing request not found")


class SourcingNotOwnedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "You can only access sourcing requests for your own business",
            code=ErrorCode.PERMISSION_DENIED,
        )


class SourcingRequirementsMissingError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Confirm requirements before searching TradeBay")


class BuyerBusinessRequiredError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("AI Sourcing is available for buyer businesses with an active company context")
