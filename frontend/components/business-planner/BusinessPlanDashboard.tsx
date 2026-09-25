"use client";

import {
  InventoryBtn,
  InventoryEmpty,
  InventoryKpi,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  InventoryTabs,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { BackLink } from "@/components/ui/BackLink";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import {
  BUDGET_KEYS,
  PLAN_SECTIONS,
} from "@/features/business-planner/constants";
import { useBusinessPlan } from "@/features/business-planner/useBusinessPlan";
import { ROUTES } from "@/lib/constants";
import { formatPlanMoney, sourceBadge } from "@/lib/businessPlanner";
import { exportBusinessPlanPdf } from "@/lib/exportBusinessPlanPdf";
import { mediaUrl } from "@/lib/media";
import Link from "next/link";
import { useState } from "react";

type Props = { planId: string };

export function BusinessPlanDashboard({ planId }: Props) {
  const bp = useBusinessPlan(planId);
  const [exportError, setExportError] = useState<string | null>(null);
  const currency = bp.plan?.currency || "USD";
  const money = (v: string | number | null | undefined) => formatPlanMoney(v, currency);

  if (bp.loading) {
    return (
      <div className="tb-inv-page">
        <InventoryPageHeader eyebrow="Business Planner" title="Loading plan…" />
        <InventorySkeleton entity="plan" />
      </div>
    );
  }

  if (!bp.plan) {
    return (
      <div className="tb-inv-page">
        <FeedbackBanner tone="error" title="Plan unavailable">
          {bp.error || "Plan not found"}
        </FeedbackBanner>
        <BackLink href={ROUTES.businessPlanner}>Back to plans</BackLink>
      </div>
    );
  }

  const plan = bp.plan;
  const concept = plan.concept || {};
  const fp = plan.financial_projection || {};
  const alloc = plan.budget_allocation || {};
  const snapshot = plan.market_snapshot || {};

  function onExport() {
    setExportError(null);
    try {
      exportBusinessPlanPdf(plan);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not export plan");
    }
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow={`Business Planner · v${plan.version}`}
        title={plan.title || "Untitled plan"}
        description={
          (concept.why_it_fits as string) ||
          (concept.concept as string) ||
          plan.description ||
          undefined
        }
        meta={
          <div className="tb-inv-page-meta-row">
            <StatusBadge status={plan.status || "draft"} />
            {plan.business_type ? (
              <span className="tb-inv-chip">{plan.business_type}</span>
            ) : null}
            <span className="tb-inv-muted">{plan.location || "Lebanon"}</span>
          </div>
        }
        actions={
          <InventoryBtn busy={bp.busy} disabled={bp.busy} onClick={onExport}>
            Export plan
          </InventoryBtn>
        }
      />

      <div className="tb-inv-kpi-grid">
        <InventoryKpi label="Startup capital" value={money(plan.budget)} index={0} />
        <InventoryKpi
          label="Inventory"
          value={money(fp.inventory_investment || alloc.inventory)}
          index={1}
        />
        <InventoryKpi
          label="Est. monthly revenue"
          value={money(fp.expected_monthly_sales || plan.estimated_monthly_revenue)}
          index={2}
        />
        <InventoryKpi
          label="Est. gross margin"
          value={
            fp.gross_margin_pct || plan.gross_margin_pct
              ? `${fp.gross_margin_pct || plan.gross_margin_pct}%`
              : "—"
          }
          tone="ok"
          index={3}
        />
      </div>

      {bp.error || exportError ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {bp.error || exportError}
        </FeedbackBanner>
      ) : null}
      {bp.info ? (
        <FeedbackBanner tone="success" title="Updated">
          {bp.info}
        </FeedbackBanner>
      ) : null}

      <InventoryTabs
        tabs={PLAN_SECTIONS.map((s) => ({ id: s.id, label: s.label }))}
        value={bp.section}
        onChange={(id) => bp.setSection(id as typeof bp.section)}
      />

      {bp.section === "overview" ? (
        <InventoryPanel title="Your business">
          <dl className="tb-inv-dl">
            <div>
              <dt>Suggested name</dt>
              <dd>{(concept.name_suggestion as string) || plan.title || "—"}</dd>
            </div>
            <div>
              <dt>Concept</dt>
              <dd>{(concept.concept as string) || plan.description || "—"}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{(concept.business_model as string) || "—"}</dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd>{plan.location || (concept.target_location as string) || "—"}</dd>
            </div>
            <div>
              <dt>Target customer</dt>
              <dd>{(concept.target_customer as string) || plan.preferences?.customer_type || "—"}</dd>
            </div>
            <div>
              <dt>Value proposition</dt>
              <dd>{(concept.value_proposition as string) || "—"}</dd>
            </div>
          </dl>

          {Object.keys(snapshot).length > 0 ? (
            <>
              <h3 className="bp-subhead">Market snapshot</h3>
              <div className="tb-inv-kpi-grid">
                {snapshot.supplier_density != null ? (
                  <InventoryKpi
                    label="Supplier density"
                    value={String(snapshot.supplier_density)}
                  />
                ) : null}
                {snapshot.category_coverage != null ? (
                  <InventoryKpi
                    label="Category coverage"
                    value={String(snapshot.category_coverage)}
                  />
                ) : null}
                {snapshot.message ? (
                  <p className="tb-inv-muted sm:col-span-2">{String(snapshot.message)}</p>
                ) : null}
              </div>
            </>
          ) : null}

          {plan.parent_plan_id ? (
            <p className="tb-inv-muted mt-3">
              Version {plan.version}.{" "}
              <Link href={ROUTES.businessPlannerPlan(plan.parent_plan_id)}>
                Open previous version
              </Link>
            </p>
          ) : null}

          <h3 className="bp-subhead">Next actions</h3>
          <p className="tb-inv-muted">
            {String(plan.progress?.next_action || "Review products and compare suppliers")}
          </p>
          <ul className="bp-next-list">
            {plan.next_actions
              .filter((a) => !["rfq", "assistant", "settings", "sourcing"].includes(a.key))
              .map((a) => (
                <li key={a.key}>
                  <button
                    type="button"
                    className="tb-btn tb-btn--secondary"
                    onClick={() => bp.handleNextAction(a.key)}
                  >
                    {a.label}
                  </button>
                </li>
              ))}
            <li>
              <button type="button" className="tb-btn tb-btn--primary" onClick={onExport}>
                Export plan PDF
              </button>
            </li>
          </ul>

          {plan.assumptions?.length ? (
            <>
              <h3 className="bp-subhead">Assumptions</h3>
              <ul className="bp-assumptions">
                {plan.assumptions.map((a, i) => (
                  <li key={i}>
                    <span className="tb-inv-chip">{a.label}</span> {a.text}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </InventoryPanel>
      ) : null}

      {bp.section === "products" ? (
        <InventoryPanel title="Product strategy">
          {plan.items.length === 0 ? (
            <InventoryEmpty title="No products yet" />
          ) : (
            <ul className="bp-product-grid">
              {plan.items.map((item) => (
                <li key={item.id} className="bp-product-card">
                  <div className="bp-product-card__media">
                    {item.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(item.image_url)} alt="" />
                    ) : (
                      <span>{(item.item_name || "?").slice(0, 2).toUpperCase()}</span>
                    )}
                    <em className="bp-product-card__priority">{item.priority}</em>
                  </div>
                  <div className="bp-product-card__body">
                    <h3>{item.item_name}</h3>
                    <p className="bp-product-card__meta">
                      {item.category_name || "General"}
                      {item.supplier_name ? ` · ${item.supplier_name}` : ""}
                    </p>
                    {item.reason ? <p className="bp-product-card__reason">{item.reason}</p> : null}
                    <dl className="bp-product-card__stats">
                      <div>
                        <dt>Unit</dt>
                        <dd>{money(item.estimated_unit_price)}</dd>
                      </div>
                      <div>
                        <dt>Qty</dt>
                        <dd>
                          {item.quantity ?? "—"} {item.unit}
                        </dd>
                      </div>
                      <div>
                        <dt>Investment</dt>
                        <dd>{money(item.estimated_total_price)}</dd>
                      </div>
                      <div>
                        <dt>Target</dt>
                        <dd>{money(item.target_selling_price)}</dd>
                      </div>
                      <div>
                        <dt>Margin</dt>
                        <dd>
                          {item.estimated_margin != null ? `${item.estimated_margin}%` : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Source</dt>
                        <dd>{sourceBadge(item.source_type)}</dd>
                      </div>
                    </dl>
                    {item.product_id ? (
                      <Link
                        className="bp-product-card__link"
                        href={ROUTES.inventoryProduct(item.product_id)}
                      >
                        View product
                      </Link>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </InventoryPanel>
      ) : null}

      {bp.section === "budget" ? (
        <InventoryPanel title="Startup budget">
          <div className="bp-budget-stack">
            {BUDGET_KEYS.map((key) => {
              const value = Number(alloc[key] || 0);
              const total = Number(alloc.available_budget || plan.budget || 1) || 1;
              const pct = Math.min(100, Math.round((value / total) * 100));
              return (
                <div key={key} className="tb-inv-stock-bar">
                  <div className="tb-inv-stock-bar-head">
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>
                      {money(alloc[key])} <em>{pct}%</em>
                    </strong>
                  </div>
                  <div className="tb-inv-stock-bar-track">
                    <div style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-4">
            <strong>Total required:</strong> {money(alloc.total_required)} vs{" "}
            <strong>available:</strong> {money(alloc.available_budget || plan.budget)}
          </p>
          {plan.budget_adjustments?.length ? (
            <>
              <h3 className="bp-subhead">Budget adjustments</h3>
              <ul className="bp-assumptions">
                {plan.budget_adjustments.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </>
          ) : null}
          {alloc.label ? <p className="tb-inv-muted mt-2">{alloc.label}</p> : null}
        </InventoryPanel>
      ) : null}

      {bp.section === "suppliers" ? (
        <InventoryPanel title="Supplier recommendations">
          {plan.suppliers.length === 0 ? (
            <InventoryEmpty title="No suppliers yet" />
          ) : (
            <ul className="bp-supplier-grid">
              {plan.suppliers.map((s) => (
                <li key={s.supplier_business_id} className="bp-supplier-card">
                  <div className="bp-supplier-card__logo">
                    {s.logo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(s.logo_url)} alt="" />
                    ) : (
                      <span>{(s.supplier_name || "S").slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div className="bp-supplier-card__body">
                    <div className="bp-supplier-card__head">
                      <h3>{s.supplier_name || "Supplier"}</h3>
                      {s.verified ? <StatusBadge status="verified" /> : null}
                    </div>
                    <p>
                      {s.product_count} recommended product
                      {s.product_count === 1 ? "" : "s"}
                    </p>
                    <div className="bp-supplier-card__actions">
                      <Link href={ROUTES.supplierProfile(s.supplier_business_id)}>Profile</Link>
                      <Link href={ROUTES.supplierProducts(s.supplier_business_id)}>Products</Link>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </InventoryPanel>
      ) : null}

      {bp.section === "launch" ? (
        <InventoryPanel title="Launch roadmap">
          <ol className="bp-roadmap">
            {plan.milestones.map((m) => (
              <li key={`${m.order}-${m.phase}`} className={m.status === "COMPLETE" ? "is-done" : ""}>
                <div className="bp-roadmap__head">
                  <strong>
                    Phase {m.order} — {m.phase}
                    {m.week ? ` · Week ${m.week}` : ""}
                  </strong>
                  {m.status !== "COMPLETE" ? (
                    <InventoryBtn
                      tone="soft"
                      busy={bp.busy}
                      disabled={bp.busy}
                      onClick={() => bp.markMilestone(m.order)}
                    >
                      Mark complete
                    </InventoryBtn>
                  ) : (
                    <StatusBadge status="completed" />
                  )}
                </div>
                <p>{m.title}</p>
                <p className="tb-inv-muted">{m.description}</p>
                {m.tasks?.length ? (
                  <ul>
                    {m.tasks.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ol>
        </InventoryPanel>
      ) : null}

      {bp.section === "finance" ? (
        <InventoryPanel title="Financial projection">
          <dl className="tb-inv-dl">
            {(
              [
                ["Initial investment", fp.initial_investment, "money"],
                ["Inventory investment", fp.inventory_investment, "money"],
                ["Monthly operating expenses", fp.monthly_operating_expenses, "money"],
                ["Expected monthly sales", fp.expected_monthly_sales, "money"],
                ["Gross revenue", fp.gross_revenue, "money"],
                ["Cost of goods", fp.cost_of_goods, "money"],
                ["Gross profit", fp.gross_profit, "money"],
                ["Gross margin", fp.gross_margin_pct ? `${fp.gross_margin_pct}%` : null, "raw"],
                ["Est. operating profit", fp.estimated_operating_profit, "money"],
                ["Break-even units", fp.break_even_units, "raw"],
                ["Cash reserve", fp.cash_reserve, "money"],
              ] as const
            ).map(([label, value, kind]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{kind === "money" ? money(value) : (value ?? "—")}</dd>
              </div>
            ))}
          </dl>
          {fp.label ? <p className="tb-inv-muted mt-3">{fp.label}</p> : null}
        </InventoryPanel>
      ) : null}

      {bp.section === "risks" ? (
        <InventoryPanel title="Main risks">
          {plan.risks.length === 0 ? (
            <InventoryEmpty title="No risks listed" />
          ) : (
            <ul className="bp-risk-list">
              {plan.risks.map((r, i) => (
                <li key={i}>
                  <h3>{r.title}</h3>
                  <p>{r.description}</p>
                  <p>
                    <strong>Why it matters:</strong> {r.why_it_matters}
                  </p>
                  <p>
                    <strong>Mitigation:</strong> {r.mitigation}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </InventoryPanel>
      ) : null}
    </div>
  );
}
