from app.core.constants import ErrorCode
from app.core.exceptions import AppError


class AIProviderError(AppError):
    def __init__(self, message: str = "AI provider error") -> None:
        super().__init__(ErrorCode.INTERNAL_ERROR, message, status_code=502)
