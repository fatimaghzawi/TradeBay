from enum import StrEnum


class NegotiationStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    AGREED = "AGREED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class NegotiationOfferStatus(StrEnum):
    PROPOSED = "PROPOSED"
    COUNTERED = "COUNTERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


NEGOTIATION_TRANSITIONS: dict[str, set[str]] = {
    NegotiationStatus.OPEN: {
        NegotiationStatus.IN_PROGRESS,
        NegotiationStatus.AGREED,
        NegotiationStatus.CANCELLED,
        NegotiationStatus.EXPIRED,
    },
    NegotiationStatus.IN_PROGRESS: {
        NegotiationStatus.AGREED,
        NegotiationStatus.REJECTED,
        NegotiationStatus.EXPIRED,
        NegotiationStatus.CANCELLED,
    },
}

OFFER_TRANSITIONS: dict[str, set[str]] = {
    NegotiationOfferStatus.PROPOSED: {
        NegotiationOfferStatus.COUNTERED,
        NegotiationOfferStatus.ACCEPTED,
        NegotiationOfferStatus.REJECTED,
        NegotiationOfferStatus.EXPIRED,
    },
}
