
from app.core.constants import ErrorCode
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class CategoryNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Category not found")

class CategoryInactiveError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Category is inactive and cannot be used for new products")

class CategoryCycleError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Category cannot be its own ancestor (circular reference)")

class CategorySlugTakenError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Category slug is already in use", details={"field": "slug"})

class ProductNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Product not found")

class ProductNotOwnedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "You can only manage products for your own supplier company",
            code=ErrorCode.PERMISSION_DENIED,
        )

class DuplicateSkuError(ConflictError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            "SKU already exists for this supplier",
            details={"field": "sku", "sku": sku},
        )

class InvalidMoqError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Minimum order quantity must be greater than 0")

class InvalidLeadTimeError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Lead time days cannot be negative")

class ProductNotPublishableError(BadRequestError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"This listing can't go live yet: {reason}")

class PriceNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Price tier not found")

class InvalidPriceRangeError(BadRequestError):
    def __init__(self, message: str = "Invalid quantity range for price tier") -> None:
        super().__init__(message)

class OverlappingPriceTierError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Price tiers for this product must not overlap")

class InvalidUnitPriceError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Unit price must be greater than 0")

class InventoryNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Inventory not found for product")

class InsufficientStockError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Not enough stock is available to reserve that quantity.")

class InsufficientReservedError(ConflictError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "Not enough reserved stock for that quantity.")

class InvalidStockQuantityError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Quantity must be greater than 0")
