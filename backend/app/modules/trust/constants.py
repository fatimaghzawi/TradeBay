from enum import StrEnum


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    MODERATED = "moderated"
    REMOVED = "removed"


class DisputeStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


DISPUTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    DisputeStatus.OPEN: {DisputeStatus.UNDER_REVIEW, DisputeStatus.CLOSED},
    DisputeStatus.UNDER_REVIEW: {DisputeStatus.RESOLVED, DisputeStatus.CLOSED},
    DisputeStatus.RESOLVED: {DisputeStatus.CLOSED},
}
