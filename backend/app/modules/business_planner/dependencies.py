from app.modules.business_planner.service import BusinessPlanService, PriceEstimateService


def get_business_plan_service() -> BusinessPlanService:
    return BusinessPlanService()


def get_price_estimate_service() -> PriceEstimateService:
    return PriceEstimateService()
