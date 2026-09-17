from app.modules.ai_sourcing.service import SourcingRecommendationService, SourcingRequestService


def get_sourcing_request_service() -> SourcingRequestService:
    return SourcingRequestService()


def get_sourcing_recommendation_service() -> SourcingRecommendationService:
    return SourcingRecommendationService()
