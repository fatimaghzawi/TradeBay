"""Finance domain errors — thin aliases over shared HTTP exceptions."""

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError

__all__ = ["BadRequestError", "ForbiddenError", "NotFoundError"]
