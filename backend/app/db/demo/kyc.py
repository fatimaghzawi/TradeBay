"""Demo KYC PDFs and brand marks for the Lebanese trading directory.

Logos and certificates are original TradeBay demo artwork — not third-party
company trademarks.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.modules.identity.storage import VERIFICATION_DIR, verification_file_url

REPO_ROOT = Path(__file__).resolve().parents[4]
LOGO_DIR = REPO_ROOT / "frontend" / "public" / "images" / "logos"
COVER_DIR = REPO_ROOT / "frontend" / "public" / "images" / "covers"

PALETTES: list[tuple[str, str, str]] = [
    ("#0d3b2a", "#e8a05c", "#f4ebe1"),
    ("#1b3a4b", "#c9a227", "#f7f3e8"),
    ("#3d1f12", "#f15a24", "#f6efe4"),
    ("#14243a", "#5dcc9a", "#e8eef6"),
    ("#2a1840", "#f0b06a", "#f3eaf8"),
    ("#12332a", "#7cb342", "#eef6e8"),
    ("#4a1020", "#e8a05c", "#fbeee8"),
    ("#102030", "#5ec8ff", "#e8f2f8"),
    ("#2c2416", "#d4a017", "#f8f1de"),
    ("#1a2e22", "#8fd3b0", "#eaf6ef"),
    ("#241018", "#f08a8f", "#fdecee"),
    ("#0f2438", "#f0b06a", "#f6efe4"),
    ("#163028", "#c5a059", "#f4efe4"),
    ("#2a1810", "#e86f2a", "#f8eee6"),
    ("#102818", "#3dce7a", "#eaf8f0"),
    ("#1c2030", "#9ab0c8", "#eef2f7"),
]


def _esc_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(*, title: str, lines: list[str]) -> bytes:
    ops = ["BT", "/F1 18 Tf", "56 740 Td", f"({_esc_pdf(title)}) Tj", "/F1 11 Tf"]
    for line in lines:
        ops.append("0 -20 Td")
        ops.append(f"({_esc_pdf(line)}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1", "replace")
    obj4 = (
        b"4 0 obj << /Length "
        + str(len(stream)).encode("ascii")
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n"
    )
    chunks = [
        b"%PDF-1.4\n",
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        ),
        obj4,
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    assembled = b"".join(chunks)
    offsets = []
    pos = 0
    for chunk in chunks:
        if chunk is chunks[0]:
            pos += len(chunk)
            continue
        offsets.append(pos)
        pos += len(chunk)
    xref = ["xref\n0 6\n0000000000 65535 f \n"]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n")
    tail = (
        "".join(xref)
        + "trailer << /Size 6 /Root 1 0 R >>\n"
        + f"startxref\n{len(assembled)}\n%%EOF\n"
    )
    return assembled + tail.encode("ascii")


def write_logo(*, slug: str, initials: str, palette_index: int, mark: str = "circle") -> str:
    bg, accent, _paper = PALETTES[palette_index % len(PALETTES)]
    safe = (initials or "TB")[:3].upper()
    if mark == "diamond":
        shape = f'<rect x="34" y="18" width="28" height="28" rx="4" transform="rotate(45 48 32)" fill="{accent}"/>'
    elif mark == "bar":
        shape = (
            f'<rect x="22" y="22" width="52" height="10" rx="5" fill="{accent}"/>'
            f'<rect x="22" y="38" width="36" height="8" rx="4" fill="{accent}" opacity="0.7"/>'
        )
    elif mark == "cedar":
        shape = (
            f'<path d="M48 16 L62 40 H34 Z" fill="{accent}"/>'
            f'<path d="M48 28 L64 52 H32 Z" fill="{accent}" opacity="0.85"/>'
            f'<rect x="45" y="50" width="6" height="12" fill="{accent}"/>'
        )
    else:
        shape = f'<circle cx="48" cy="34" r="14" fill="{accent}"/>'
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none">
  <rect width="96" height="96" rx="22" fill="{bg}"/>
  {shape}
  <text x="48" y="80" text-anchor="middle" font-family="Georgia, serif" font-size="15" font-weight="700" fill="{accent}">{safe}</text>
</svg>
"""
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGO_DIR / f"{slug}.svg"
    path.write_text(svg, encoding="utf-8")
    return f"/images/logos/{slug}.svg"


def write_cover(*, slug: str, palette_index: int) -> str:
    bg, accent, paper = PALETTES[palette_index % len(PALETTES)]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 180" fill="none">
  <rect width="640" height="180" fill="{bg}"/>
  <circle cx="560" cy="20" r="90" fill="{accent}" opacity="0.18"/>
  <rect x="0" y="150" width="640" height="30" fill="{accent}" opacity="0.85"/>
  <rect x="36" y="36" width="180" height="12" rx="6" fill="{paper}" opacity="0.35"/>
</svg>
"""
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    path = COVER_DIR / f"{slug}.svg"
    path.write_text(svg, encoding="utf-8")
    return f"/images/covers/{slug}.svg"


def write_verification_pack(
    *,
    business_id: str,
    company_name: str,
    legal_name: str,
    tax_number: str,
    registration_number: str,
    address: dict[str, str],
    verified: bool,
) -> list[dict[str, object]]:
    from app.shared.utils.datetime import utc_now

    now = utc_now()
    street = address.get("street") or "—"
    city = address.get("city") or "—"
    governorate = address.get("governorate") or "Lebanon"
    folder = VERIFICATION_DIR / str(business_id)
    folder.mkdir(parents=True, exist_ok=True)
    specs = [
        (
            "commercial_registration",
            "Commercial Register extract",
            [
                f"Company: {legal_name}",
                f"Trade name: {company_name}",
                f"Register no: {registration_number}",
                f"Issued in: {city}, {governorate}",
                "Issuing office: Commercial Register of Lebanon (demo)",
                "This PDF is TradeBay demo artwork for development only.",
            ],
        ),
        (
            "tax_certificate",
            "Ministry of Finance tax certificate",
            [
                f"Taxpayer: {legal_name}",
                f"VAT / tax no: {tax_number}",
                f"Registered address: {street}",
                f"{city}, {governorate}, Lebanon",
                "Status: registered (demo)",
                "This PDF is TradeBay demo artwork for development only.",
            ],
        ),
        (
            "address_proof",
            "Proof of business address",
            [
                f"Occupant: {legal_name}",
                f"Premises: {street}",
                f"{address.get('district') or city}, {city}",
                f"{governorate} Governorate, {address.get('postal_code') or '—'} Lebanon",
                "Utility / lease extract (demo)",
                "This PDF is TradeBay demo artwork for development only.",
            ],
        ),
    ]
    docs: list[dict[str, object]] = []
    for doc_type, title, lines in specs:
        for leftover in folder.glob(f"{doc_type}-*"):
            leftover.unlink(missing_ok=True)
        filename = f"{doc_type}-{uuid.uuid4().hex}.pdf"
        (folder / filename).write_bytes(build_pdf(title=title, lines=lines))
        url = verification_file_url(
            business_id=str(business_id),
            document_type=doc_type,
            filename=filename,
        )
        docs.append(
            {
                "document_type": doc_type,
                "url": url,
                "file_name": f"{doc_type}.pdf",
                "uploaded_at": now,
                "verified_at": now if verified else None,
            }
        )
    return docs
