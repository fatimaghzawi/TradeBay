"""Commercial PDF documents for quotations and purchase orders (reportlab)."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#14201b")
MUTED = colors.HexColor("#5a6560")
RULE = colors.HexColor("#d7e0da")
ACCENT = colors.HexColor("#0d3b2a")
PAPER_LINE = colors.HexColor("#e6eee9")


def _money(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def _text(value: Any, fallback: str = "—") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _format_address(addr: Any) -> str | None:
    if not isinstance(addr, dict):
        return None
    parts = [
        addr.get("street"),
        addr.get("city"),
        addr.get("district"),
        addr.get("governorate"),
        addr.get("postal_code"),
        addr.get("country"),
    ]
    line = ", ".join(str(p).strip() for p in parts if p)
    return line or None


def _format_date(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    raw = str(value)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else raw


def _party_block(
    *,
    label: str,
    name: str,
    legal_name: str | None,
    address: Any,
    email: str | None,
    phone: str | None,
    tax_number: str | None,
    styles: Any,
) -> list[Any]:
    bits: list[Any] = [
        Paragraph(
            label.upper(),
            ParagraphStyle(
                f"PartyLabel{label}",
                parent=styles["Normal"],
                fontSize=7,
                textColor=MUTED,
                fontName="Helvetica-Bold",
                spaceAfter=4,
            ),
        ),
        Paragraph(
            _text(name, "—"),
            ParagraphStyle(
                f"PartyName{label}",
                parent=styles["Normal"],
                fontSize=10,
                textColor=INK,
                fontName="Helvetica-Bold",
                spaceAfter=2,
            ),
        ),
    ]
    if legal_name and legal_name != name:
        bits.append(
            Paragraph(
                _text(legal_name),
                ParagraphStyle(
                    f"PartyLegal{label}",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=MUTED,
                    spaceAfter=2,
                ),
            )
        )
    addr = _format_address(address)
    if addr:
        bits.append(
            Paragraph(
                addr,
                ParagraphStyle(
                    f"PartyAddr{label}",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=MUTED,
                    leading=11,
                    spaceAfter=2,
                ),
            )
        )
    contacts = []
    if tax_number:
        contacts.append(f"Tax ID · {tax_number}")
    if email:
        contacts.append(str(email))
    if phone:
        contacts.append(str(phone))
    for c in contacts:
        bits.append(
            Paragraph(
                c,
                ParagraphStyle(
                    f"PartyContact{label}{len(bits)}",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=MUTED,
                    spaceAfter=1,
                ),
            )
        )
    return bits


def _build_pdf(title: str, subtitle: str, meta: list[tuple[str, str]], rows: list[list[str]], totals: list[tuple[str, str]]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TBTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=ACCENT,
        spaceAfter=4,
    )
    sub_style = ParagraphStyle("TBSub", parent=styles["Normal"], textColor=MUTED, spaceAfter=12)
    story: list[Any] = [Paragraph(title, title_style), Paragraph(subtitle, sub_style)]

    meta_data = [[k, v] for k, v in meta]
    meta_table = Table(meta_data, colWidths=[4.5 * cm, 12 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    table = Table(rows, colWidths=[7 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f3eb")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.4 * cm))

    totals_table = Table([[k, v] for k, v in totals], colWidths=[12 * cm, 4.5 * cm])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "TradeBay commercial record — amounts calculated server-side. Catalog prices may change later.",
            ParagraphStyle("TBFoot", parent=styles["Normal"], fontSize=8, textColor=colors.gray),
        )
    )
    doc.build(story)
    return buf.getvalue()


def render_purchase_order_pdf(order: dict[str, Any]) -> bytes:
    """Mirror the quiet on-page purchase order document."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    currency = _text(order.get("currency"), "USD")
    buyer_name = _text(order.get("buyer_name"), "Buyer")
    supplier_name = _text(order.get("supplier_name"), "Supplier")
    buyer_addr = _format_address(order.get("buyer_address"))
    ship_to = _format_address(order.get("shipping_address")) or "Same as bill to"
    header_bits = [
        p
        for p in [
            buyer_addr,
            order.get("buyer_contact_email"),
            order.get("buyer_contact_phone"),
        ]
        if p
    ]

    brand_name = ParagraphStyle(
        "POBrand",
        parent=styles["Normal"],
        fontSize=14,
        leading=17,
        textColor=INK,
        fontName="Helvetica-Bold",
        spaceAfter=3,
    )
    brand_sub = ParagraphStyle(
        "POBrandSub",
        parent=styles["Normal"],
        fontSize=8,
        textColor=MUTED,
        leading=11,
    )
    meta_title = ParagraphStyle(
        "POMetaTitle",
        parent=styles["Normal"],
        fontSize=8,
        textColor=ACCENT,
        fontName="Helvetica-Bold",
        alignment=2,
        spaceAfter=3,
    )
    meta_no = ParagraphStyle(
        "POMetaNo",
        parent=styles["Normal"],
        fontSize=11,
        textColor=INK,
        fontName="Helvetica-Bold",
        alignment=2,
        spaceAfter=2,
    )
    meta_line = ParagraphStyle(
        "POMetaLine",
        parent=styles["Normal"],
        fontSize=8,
        textColor=MUTED,
        alignment=2,
        spaceAfter=1,
    )
    cell = ParagraphStyle("POCell", parent=styles["Normal"], fontSize=8, textColor=INK, leading=11)
    cell_muted = ParagraphStyle("POCellMuted", parent=styles["Normal"], fontSize=7, textColor=MUTED, leading=9)
    term_label = ParagraphStyle(
        "POTermLabel",
        parent=styles["Normal"],
        fontSize=7,
        textColor=MUTED,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    term_value = ParagraphStyle(
        "POTermValue",
        parent=styles["Normal"],
        fontSize=9,
        textColor=INK,
        fontName="Helvetica-Bold",
    )
    note = ParagraphStyle("PONote", parent=styles["Normal"], fontSize=8, textColor=MUTED, leading=11)
    total_label = ParagraphStyle("POTotalLabel", parent=styles["Normal"], fontSize=9, textColor=MUTED)
    total_value = ParagraphStyle(
        "POTotalValue",
        parent=styles["Normal"],
        fontSize=9,
        textColor=INK,
        fontName="Helvetica-Bold",
        alignment=2,
    )
    grand_label = ParagraphStyle(
        "POGrandLabel",
        parent=styles["Normal"],
        fontSize=10,
        textColor=INK,
        fontName="Helvetica-Bold",
    )
    grand_value = ParagraphStyle(
        "POGrandValue",
        parent=styles["Normal"],
        fontSize=12,
        textColor=ACCENT,
        fontName="Helvetica-Bold",
        alignment=2,
    )

    left_header = [
        Paragraph(buyer_name, brand_name),
        Paragraph(" · ".join(str(b) for b in header_bits) if header_bits else "Purchase order", brand_sub),
    ]
    right_header = [
        Paragraph("PURCHASE ORDER", meta_title),
        Paragraph(_text(order.get("order_number"), "PO"), meta_no),
        Paragraph(f"Date · {_format_date(order.get('created_at'))}", meta_line),
    ]
    if order.get("quotation_number"):
        right_header.append(Paragraph(f"Ref · {order['quotation_number']}", meta_line))

    header = Table(
        [[left_header, right_header]],
        colWidths=[10.5 * cm, 6.5 * cm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    vendor = _party_block(
        label="Vendor",
        name=supplier_name,
        legal_name=order.get("supplier_legal_name"),
        address=order.get("supplier_address"),
        email=order.get("supplier_contact_email"),
        phone=order.get("supplier_contact_phone"),
        tax_number=order.get("supplier_tax_number"),
        styles=styles,
    )
    bill_to = _party_block(
        label="Bill to",
        name=buyer_name,
        legal_name=order.get("buyer_legal_name"),
        address=order.get("buyer_address"),
        email=order.get("buyer_contact_email"),
        phone=order.get("buyer_contact_phone"),
        tax_number=order.get("buyer_tax_number"),
        styles=styles,
    )
    ship_block = [
        Paragraph(
            "SHIP TO",
            ParagraphStyle(
                "ShipLabel",
                parent=styles["Normal"],
                fontSize=7,
                textColor=MUTED,
                fontName="Helvetica-Bold",
                spaceAfter=4,
            ),
        ),
        Paragraph(
            ship_to,
            ParagraphStyle(
                "ShipValue",
                parent=styles["Normal"],
                fontSize=8,
                textColor=MUTED,
                leading=11,
            ),
        ),
    ]
    parties = Table([[vendor, bill_to, ship_block]], colWidths=[5.7 * cm, 5.7 * cm, 5.6 * cm])
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    payment_status = _text(order.get("payment_status"), "unpaid").replace("_", " ")
    payment_method = _text(order.get("payment_method"), "Bank transfer")
    tax_name = _text(order.get("tax_name_snapshot"), "VAT")
    tax_pct = order.get("tax_rate_percent")
    if not tax_pct and order.get("tax_rate_snapshot") is not None:
        try:
            from decimal import Decimal

            pct = Decimal(str(order.get("tax_rate_snapshot"))) * Decimal("100")
            tax_pct = f"{format(pct.quantize(Decimal('0.01')), 'f').rstrip('0').rstrip('.')}%"
        except Exception:
            tax_pct = None
    terms = Table(
        [
            [
                [Paragraph("CURRENCY", term_label), Paragraph(currency, term_value)],
                [
                    Paragraph("PAYMENT TERMS", term_label),
                    Paragraph(_text(order.get("payment_terms")), term_value),
                ],
                [
                    Paragraph("PAYMENT METHOD", term_label),
                    Paragraph(payment_method, term_value),
                ],
            ],
            [
                [
                    Paragraph("DELIVERY TERMS", term_label),
                    Paragraph(_text(order.get("delivery_terms")), term_value),
                ],
                [
                    Paragraph("PAYMENT STATUS", term_label),
                    Paragraph(payment_status, term_value),
                ],
                [
                    Paragraph(tax_name.upper(), term_label),
                    Paragraph(_text(tax_pct, "—"), term_value),
                ],
            ],
        ],
        colWidths=[5.7 * cm, 5.7 * cm, 5.6 * cm],
    )
    terms.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    line_rows: list[list[Any]] = [
        [
            Paragraph("#", cell_muted),
            Paragraph("Description", cell_muted),
            Paragraph("Qty", cell_muted),
            Paragraph("Unit price", cell_muted),
            Paragraph("Amount", cell_muted),
        ]
    ]
    for idx, item in enumerate(order.get("items") or [], start=1):
        desc = [Paragraph(_text(item.get("product_name_snapshot"), "Item"), cell)]
        if item.get("sku_snapshot"):
            desc.append(Paragraph(f"SKU {item['sku_snapshot']}", cell_muted))
        qty = _money(item.get("quantity"))
        unit = item.get("unit")
        qty_label = f"{qty} {unit}".strip() if unit else qty
        line_rows.append(
            [
                Paragraph(str(idx), cell_muted),
                desc,
                Paragraph(qty_label, cell),
                Paragraph(f"{currency} {_money(item.get('unit_price'))}", cell),
                Paragraph(f"{currency} {_money(item.get('line_total'))}", cell),
            ]
        )

    lines = Table(line_rows, colWidths=[1.1 * cm, 8.2 * cm, 2.4 * cm, 2.8 * cm, 2.5 * cm])
    lines.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    totals_rows: list[list[Any]] = [
        [
            Paragraph("Subtotal", total_label),
            Paragraph(f"{currency} {_money(order.get('subtotal'))}", total_value),
        ]
    ]
    discount = order.get("discount_total")
    try:
        if discount is not None and float(discount) > 0:
            totals_rows.append(
                [
                    Paragraph("Discount", total_label),
                    Paragraph(f"−{currency} {_money(discount)}", total_value),
                ]
            )
    except (TypeError, ValueError):
        pass
    try:
        if order.get("charge_total") is not None and float(order.get("charge_total") or 0) > 0:
            totals_rows.append(
                [
                    Paragraph("Charges", total_label),
                    Paragraph(f"{currency} {_money(order.get('charge_total'))}", total_value),
                ]
            )
    except (TypeError, ValueError):
        pass
    tax_row_label = tax_name
    if tax_pct:
        tax_row_label = f"{tax_name} ({tax_pct})"
    totals_rows.append(
        [
            Paragraph(tax_row_label, total_label),
            Paragraph(f"{currency} {_money(order.get('tax_total') or '0.00')}", total_value),
        ]
    )
    totals_rows.append(
        [
            Paragraph("Total", grand_label),
            Paragraph(f"{currency} {_money(order.get('total'))}", grand_value),
        ]
    )
    totals = Table(totals_rows, colWidths=[4.5 * cm, 4 * cm])
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEABOVE", (0, -1), (-1, -1), 1, INK),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )

    notes: list[Any] = []
    if order.get("quotation_number"):
        notes.append(Paragraph(f"Issued against quotation {order['quotation_number']}.", note))
    notes.append(Spacer(1, 0.7 * cm))
    notes.append(Paragraph("Authorized by", note))
    notes.append(Spacer(1, 1.1 * cm))
    notes.append(HRFlowable(width="60%", thickness=0.6, color=RULE, spaceBefore=0, spaceAfter=0))

    foot = Table([[notes, totals]], colWidths=[8.5 * cm, 8.5 * cm])
    foot.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )

    story: list[Any] = [
        header,
        HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=2, spaceAfter=14),
        parties,
        Spacer(1, 0.35 * cm),
        HRFlowable(width="100%", thickness=0.6, color=PAPER_LINE, spaceBefore=2, spaceAfter=0),
        terms,
        HRFlowable(width="100%", thickness=0.6, color=PAPER_LINE, spaceBefore=0, spaceAfter=12),
        lines,
        Spacer(1, 0.55 * cm),
        foot,
    ]
    doc.build(story)
    return buf.getvalue()


def render_quotation_pdf(quote: dict[str, Any]) -> bytes:
    rows = [["Product", "Qty", "Unit price", "Line total", "Lead days"]]
    for item in quote.get("lines") or []:
        rows.append(
            [
                str(item.get("product_name_snapshot") or "Item"),
                _money(item.get("quantity")),
                _money(item.get("unit_price")),
                _money(item.get("line_total")),
                str(item.get("lead_time_days") if item.get("lead_time_days") is not None else "—"),
            ]
        )
    currency = quote.get("currency") or "USD"
    return _build_pdf(
        title=f"Quotation {quote.get('quotation_number')}",
        subtitle=f"Status: {quote.get('status')} · v{quote.get('current_version') or 1}",
        meta=[
            ("Quotation", str(quote.get("quotation_number"))),
            ("Payment terms", str(quote.get("payment_terms") or "—")),
            ("Delivery terms", str(quote.get("delivery_terms") or "—")),
            ("Currency", currency),
        ],
        rows=rows,
        totals=[
            ("Subtotal", f"{currency} {_money(quote.get('subtotal'))}"),
            ("Charges", f"{currency} {_money(quote.get('charge_total'))}"),
            ("Tax", f"{currency} {_money(quote.get('tax_total'))}"),
            ("Total", f"{currency} {_money(quote.get('total'))}"),
        ],
    )
