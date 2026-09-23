"""Unit tests for tracking webhook mapping and commercial PDF smoke."""

from __future__ import annotations

from app.modules.procurement.documents import render_purchase_order_pdf, render_quotation_pdf
from app.modules.procurement.tracking import CarrierWebhookProvider, get_tracking_provider


def test_carrier_webhook_maps_status() -> None:
    provider = CarrierWebhookProvider()
    update = provider.parse_webhook(
        {
            "tracking_number": "TRK-9",
            "status": "in_transit",
            "description": "Left Beirut hub",
            "location": "Beirut",
        }
    )
    assert update is not None
    assert update.tracking_number == "TRK-9"
    assert update.status == "in_transit"
    assert update.source == "carrier_webhook"


def test_carrier_webhook_rejects_unknown() -> None:
    assert CarrierWebhookProvider().parse_webhook({"foo": "bar"}) is None


def test_get_tracking_provider_default_manual() -> None:
    assert get_tracking_provider().name == "manual"
    assert get_tracking_provider("carrier_webhook").name == "carrier_webhook"


def test_po_pdf_renders_bytes() -> None:
    pdf = render_purchase_order_pdf(
        {
            "order_number": "PO-2026-0001",
            "status": "confirmed",
            "currency": "USD",
            "payment_terms": "Net 30",
            "delivery_terms": "Tyre",
            "payment_status": "unpaid",
            "created_at": "2026-09-23T00:10:40+00:00",
            "quotation_number": "QT-2026-0009",
            "buyer_name": "Cedar Goods Co",
            "buyer_contact_email": "buyer@example.com",
            "buyer_address": {"city": "Beirut", "country": "Lebanon"},
            "supplier_name": "Bekaa Supplies",
            "supplier_contact_email": "sales@example.com",
            "supplier_address": {"city": "Zahle", "country": "Lebanon"},
            "shipping_address": {"city": "Beirut", "street": "Hamra St", "country": "Lebanon"},
            "subtotal": "100.00",
            "discount_total": "0",
            "charge_total": "10.00",
            "tax_total": "0",
            "total": "110.00",
            "items": [
                {
                    "product_name_snapshot": "Widget",
                    "sku_snapshot": "W-1",
                    "quantity": "10",
                    "unit": "pcs",
                    "unit_price": "10.00",
                    "line_total": "100.00",
                }
            ],
        }
    )
    assert pdf.startswith(b"%PDF")
    assert b"PURCHASE ORDER" in pdf or b"Purchase" in pdf or len(pdf) > 500



def test_quotation_pdf_renders_bytes() -> None:
    pdf = render_quotation_pdf(
        {
            "quotation_number": "QT-2026-0001",
            "status": "submitted",
            "current_version": 1,
            "currency": "USD",
            "payment_terms": "Net 15",
            "delivery_terms": "Beirut",
            "subtotal": "50.00",
            "charge_total": "0",
            "tax_total": "0",
            "total": "50.00",
            "lines": [
                {
                    "product_name_snapshot": "Cable",
                    "quantity": "5",
                    "unit_price": "10.00",
                    "line_total": "50.00",
                    "lead_time_days": 3,
                }
            ],
        }
    )
    assert pdf.startswith(b"%PDF")
