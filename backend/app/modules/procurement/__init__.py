"""Procurement & fulfillment — RFQ → quotation → PO → shipment → receive.

Uses ERD commercial models. Totals are Decimal-only. Award creates the
purchase order (``orders``). Finance/platform money are called from the service
when an order is confirmed.

Read in this order:

1. ``constants.py`` — RFQ/order/shipment status machines
2. ``models.py`` · ``schemas.py``
3. ``repository.py`` · ``commercial.py`` · ``documents.py`` · ``tracking.py``
4. ``service.py`` — main orchestration (largest file in this domain)
5. ``router.py`` — HTTP surface
"""
