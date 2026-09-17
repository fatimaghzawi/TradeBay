from app.modules.trust.repository import DisputeRepository, NotificationRepository, ReviewRepository


class ReviewService:
    def __init__(self, repo: ReviewRepository | None = None) -> None:
        self.repo = repo or ReviewRepository()


class DisputeService:
    def __init__(self, repo: DisputeRepository | None = None) -> None:
        self.repo = repo or DisputeRepository()


class NotificationService:
    def __init__(self, repo: NotificationRepository | None = None) -> None:
        self.repo = repo or NotificationRepository()
