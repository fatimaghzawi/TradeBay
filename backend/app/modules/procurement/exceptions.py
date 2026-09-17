from app.core.exceptions import AppError, ConflictError


class ProcurementError(AppError):
    pass


class InvalidStateTransitionError(ConflictError):
    def __init__(self, entity: str, current: str, target: str) -> None:
        super().__init__(
            f"Invalid {entity} transition from {current} to {target}",
            details={"entity": entity, "current": current, "target": target},
        )
