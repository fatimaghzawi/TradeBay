
from app.core.exceptions import BadRequestError, NotFoundError


class CartEmptyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Cart is empty")

class CartItemNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Cart item not found")

class CartProductUnavailableError(BadRequestError):
    def __init__(self, message: str = "Product is not available to add to cart") -> None:
        super().__init__(message)

class CartBuyerRequiredError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Only buyer companies can use the shopping cart")

class CartInvalidSuggestedPriceError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Suggested unit price must be a non-negative number")

class CartSelfSupplyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("You cannot add your own products to the cart")

class CartPriceRequiredError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "Every cart line needs a unit price before you can place a direct order"
        )

class CartMixedCurrencyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Each supplier order must use a single currency")
