from app.modules.platform_money.repository import (
    CommissionRepository,
    PayableRepository,
    SettlementRepository,
)


class CommissionService:
    def __init__(self, repo: CommissionRepository | None = None) -> None:
        self.repo = repo or CommissionRepository()


class SupplierPayableService:
    def __init__(self, repo: PayableRepository | None = None) -> None:
        self.repo = repo or PayableRepository()


class SettlementService:
    def __init__(self, repo: SettlementRepository | None = None) -> None:
        self.repo = repo or SettlementRepository()
