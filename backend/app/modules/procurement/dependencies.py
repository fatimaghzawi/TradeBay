from app.modules.procurement.service import OrderService, RFQService


def get_rfq_service() -> RFQService:
    return RFQService()


def get_order_service() -> OrderService:
    return OrderService()
