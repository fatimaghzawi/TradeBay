from app.modules.negotiation.service import NegotiationService


def get_negotiation_service() -> NegotiationService:
    return NegotiationService()
