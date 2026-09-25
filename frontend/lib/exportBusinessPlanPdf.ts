

import type { BusinessPlan } from "@/lib/api/businessPlannerApi";
import { formatPlanMoney, sourceBadge } from "@/lib/businessPlanner";
import { mediaUrl } from "@/lib/media";

function esc(value: string | null | undefined): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function exportBusinessPlanPdf(plan: BusinessPlan): void {
  const currency = plan.currency || "USD";
  const money = (v: string | number | null | undefined) => formatPlanMoney(v, currency);
  const concept = plan.concept || {};
  const fp = plan.financial_projection || {};
  const alloc = plan.budget_allocation || {};
  const title = plan.title || "Untitled plan";
  const items = plan.items || [];
  const suppliers = plan.suppliers || [];
  const milestonesList = plan.milestones || [];
  const risksList = plan.risks || [];

  const productCards = items
    .map((item) => {
      const img = item.image_url
        ? `<img src="${esc(mediaUrl(item.image_url))}" alt="" />`
        : `<div class="ph">${esc((item.item_name || "?").slice(0, 2).toUpperCase())}</div>`;
      return `<article class="card">
        <div class="thumb">${img}</div>
        <div>
          <h3>${esc(item.item_name)}</h3>
          <p class="meta">${esc(item.priority)} · ${esc(item.category_name || "General")} · ${esc(sourceBadge(item.source_type))}</p>
          <p>${esc(item.reason || item.description || "")}</p>
          <dl>
            <div><dt>Unit</dt><dd>${esc(money(item.estimated_unit_price))}</dd></div>
            <div><dt>Qty</dt><dd>${esc(String(item.quantity ?? "—"))} ${esc(item.unit || "")}</dd></div>
            <div><dt>Investment</dt><dd>${esc(money(item.estimated_total_price))}</dd></div>
            <div><dt>Target</dt><dd>${esc(money(item.target_selling_price))}</dd></div>
            <div><dt>Margin</dt><dd>${item.estimated_margin != null ? `${esc(String(item.estimated_margin))}%` : "—"}</dd></div>
            <div><dt>Supplier</dt><dd>${esc(item.supplier_name || "—")}</dd></div>
          </dl>
        </div>
      </article>`;
    })
    .join("");

  const supplierCards = suppliers
    .map((s) => {
      const img = s.logo_url
        ? `<img src="${esc(mediaUrl(s.logo_url))}" alt="" />`
        : `<div class="ph">${esc((s.supplier_name || "S").slice(0, 2).toUpperCase())}</div>`;
      return `<article class="sup">
        <div class="thumb">${img}</div>
        <div>
          <h3>${esc(s.supplier_name || "Supplier")}</h3>
          <p>${s.product_count} recommended product${s.product_count === 1 ? "" : "s"}${s.verified ? " · Verified" : ""}</p>
        </div>
      </article>`;
    })
    .join("");

  const budgetRows = Object.entries(alloc)
    .filter(([k]) => k !== "label")
    .map(
      ([k, v]) =>
        `<tr><td>${esc(k.replaceAll("_", " "))}</td><td>${esc(money(v))}</td></tr>`,
    )
    .join("");

  const milestones = milestonesList
    .map(
      (m) => `<li>
        <strong>Phase ${m.order} — ${esc(m.phase)}${m.week ? ` · Week ${m.week}` : ""}</strong>
        <p>${esc(m.title)}</p>
        <p class="muted">${esc(m.description)}</p>
      </li>`,
    )
    .join("");

  const risks = risksList
    .map(
      (r) => `<li>
        <strong>${esc(r.title)}</strong>
        <p>${esc(r.description)}</p>
        <p><em>Mitigation:</em> ${esc(r.mitigation)}</p>
      </li>`,
    )
    .join("");

  const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>${esc(title)} · TradeBay Plan</title>
<style>
  @page { margin: 16mm; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    color: #14201b;
    background: #f4f7f5;
  }
  .sheet {
    max-width: 920px;
    margin: 0 auto;
    padding: 28px 32px 48px;
    background:
      radial-gradient(90% 50% at 100% 0%, rgba(45,184,122,0.12), transparent 55%),
      linear-gradient(180deg, #fff 0%, #f7faf8 100%);
  }
  .hero {
    display: grid;
    gap: 0.35rem;
    padding-bottom: 1.25rem;
    border-bottom: 2px solid #0d3b2a;
    margin-bottom: 1.5rem;
  }
  .kicker {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #1a6b4f;
  }
  h1 {
    margin: 0;
    font-size: 2rem;
    letter-spacing: -0.03em;
  }
  .lede { margin: 0.35rem 0 0; color: #4a5f55; max-width: 42rem; line-height: 1.45; }
  .kpis {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin: 1.25rem 0 1.75rem;
  }
  .kpi {
    background: #fff;
    border: 1px solid #d7e3dc;
    border-radius: 1rem;
    padding: 0.85rem 1rem;
  }
  .kpi span { display: block; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #5a6a62; }
  .kpi strong { display: block; margin-top: 0.25rem; font-size: 1.1rem; }
  h2 {
    margin: 1.75rem 0 0.75rem;
    font-size: 1.15rem;
    color: #0d3b2a;
  }
  .grid { display: grid; gap: 0.85rem; }
  .card, .sup {
    display: grid;
    grid-template-columns: 5.5rem 1fr;
    gap: 0.9rem;
    background: #fff;
    border: 1px solid #d7e3dc;
    border-radius: 1.1rem;
    padding: 0.85rem;
    break-inside: avoid;
  }
  .sup { grid-template-columns: 3.5rem 1fr; align-items: center; }
  .thumb {
    width: 5.5rem;
    height: 5.5rem;
    border-radius: 0.9rem;
    overflow: hidden;
    background: #e8f2ec;
  }
  .sup .thumb { width: 3.5rem; height: 3.5rem; border-radius: 999px; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .ph {
    width: 100%; height: 100%;
    display: grid; place-items: center;
    font-weight: 800; color: #0d3b2a; background: linear-gradient(145deg, #cfe8da, #e8f6ef);
  }
  h3 { margin: 0 0 0.2rem; font-size: 1rem; }
  .meta { margin: 0 0 0.35rem; font-size: 0.75rem; color: #5a6a62; }
  p { margin: 0.2rem 0; font-size: 0.88rem; line-height: 1.4; }
  .muted { color: #5a6a62; }
  dl {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.35rem 0.75rem;
    margin: 0.55rem 0 0;
  }
  dt { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #5a6a62; }
  dd { margin: 0; font-size: 0.82rem; font-weight: 650; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 0.9rem; overflow: hidden; }
  td { padding: 0.55rem 0.75rem; border-bottom: 1px solid #e2ebe6; font-size: 0.88rem; }
  td:last-child { text-align: right; font-weight: 700; }
  ol, ul { padding-left: 1.1rem; }
  li { margin: 0.55rem 0; break-inside: avoid; }
  .foot {
    margin-top: 2rem;
    padding-top: 0.85rem;
    border-top: 1px solid #d7e3dc;
    font-size: 0.75rem;
    color: #5a6a62;
  }
  @media print {
    body { background: #fff; }
    .sheet { padding: 0; background: #fff; }
  }
</style>
</head>
<body>
  <div class="sheet">
    <header class="hero">
      <p class="kicker">TradeBay · Business plan v${plan.version}</p>
      <h1>${esc(title)}</h1>
      <p class="lede">${esc(
        (concept.why_it_fits as string) ||
          (concept.concept as string) ||
          plan.description ||
          "Personalized blueprint from your preferences and TradeBay catalog data.",
      )}</p>
      <p class="muted">${esc(plan.business_type || "")}${plan.location ? ` · ${esc(plan.location)}` : ""} · ${esc(plan.status)}</p>
    </header>

    <section class="kpis">
      <div class="kpi"><span>Startup capital</span><strong>${esc(money(plan.budget))}</strong></div>
      <div class="kpi"><span>Inventory</span><strong>${esc(money(fp.inventory_investment || alloc.inventory))}</strong></div>
      <div class="kpi"><span>Monthly revenue</span><strong>${esc(money(fp.expected_monthly_sales || plan.estimated_monthly_revenue))}</strong></div>
      <div class="kpi"><span>Gross margin</span><strong>${fp.gross_margin_pct || plan.gross_margin_pct ? `${esc(String(fp.gross_margin_pct || plan.gross_margin_pct))}%` : "—"}</strong></div>
    </section>

    <h2>Business concept</h2>
    <p><strong>Name:</strong> ${esc((concept.name_suggestion as string) || title)}</p>
    <p><strong>Model:</strong> ${esc((concept.business_model as string) || "—")}</p>
    <p><strong>Customer:</strong> ${esc((concept.target_customer as string) || plan.preferences?.customer_type || "—")}</p>
    <p><strong>Value:</strong> ${esc((concept.value_proposition as string) || "—")}</p>

    <h2>Product strategy (${items.length})</h2>
    <div class="grid">${productCards || "<p class='muted'>No products listed.</p>"}</div>

    <h2>Budget allocation</h2>
    <table>${budgetRows || "<tr><td colspan='2'>No budget breakdown</td></tr>"}</table>

    <h2>Suppliers (${suppliers.length})</h2>
    <div class="grid">${supplierCards || "<p class='muted'>No suppliers linked.</p>"}</div>

    <h2>Financial projection</h2>
    <table>
      <tr><td>Initial investment</td><td>${esc(money(fp.initial_investment))}</td></tr>
      <tr><td>Monthly operating expenses</td><td>${esc(money(fp.monthly_operating_expenses))}</td></tr>
      <tr><td>Expected monthly sales</td><td>${esc(money(fp.expected_monthly_sales))}</td></tr>
      <tr><td>Gross profit</td><td>${esc(money(fp.gross_profit))}</td></tr>
      <tr><td>Operating profit</td><td>${esc(money(fp.estimated_operating_profit))}</td></tr>
      <tr><td>Break-even units</td><td>${esc(String(fp.break_even_units ?? "—"))}</td></tr>
    </table>

    <h2>Launch roadmap</h2>
    <ol>${milestones || "<li class='muted'>No milestones</li>"}</ol>

    <h2>Risks</h2>
    <ul>${risks || "<li class='muted'>No risks listed</li>"}</ul>

    <p class="foot">TradeBay Business Planner · ${new Date().toLocaleString()}</p>
  </div>
</body>
</html>`;

  const safeName = (title || "tradebay-plan")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60) || "tradebay-plan";

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const revokeLater = () => {
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  // Prefer a real tab (user gesture) — then print / Save as PDF.
  const preview = window.open(url, "_blank");
  if (preview) {
    const tryPrint = () => {
      try {
        preview.focus();
        preview.print();
      } catch {
        /* user can print manually from the tab */
      }
    };
    // Blob tabs may not fire load reliably; retry a few times.
    window.setTimeout(tryPrint, 500);
    window.setTimeout(tryPrint, 1200);
    revokeLater();
    return;
  }

  // Popup blocked — download HTML and print via hidden iframe.
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeName}-plan.html`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  const frame = document.createElement("iframe");
  frame.setAttribute("aria-hidden", "true");
  frame.style.cssText =
    "position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0;pointer-events:none;";
  document.body.appendChild(frame);

  frame.onload = () => {
    window.setTimeout(() => {
      try {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
      } finally {
        window.setTimeout(() => {
          frame.remove();
          revokeLater();
        }, 1500);
      }
    }, 400);
  };
  frame.src = url;
}
