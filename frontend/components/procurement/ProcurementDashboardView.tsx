"use client";

import {
  InventoryEmpty,
  InventoryKpi,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventorySkeleton,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import {
  procurementApi,
  type ProcurementDashboard,
} from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLivePoll } from "@/lib/live/useLivePoll";

function actionHref(key: string, isSupplier: boolean): string {
  if (key === "quotes" || key === "rfqs" || key === "invites") {
    return isSupplier ? ROUTES.quotations : ROUTES.procurement;
  }
  if (key === "orders" || key === "ack") return ROUTES.orders;
  return ROUTES.procurement;
}

export function ProcurementDashboardView() {
  const { business, hasPermission } = useAuth();
  const isSupplier = business?.type === "supplier";
  const [dash, setDash] = useState<ProcurementDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async (opts?: { soft?: boolean }) => {
    if (!opts?.soft) setLoading(true);
    try {
      const data = await procurementApi.dashboard();
      setDash(data);
      setError(null);
    } catch (err) {
      if (!opts?.soft) {
        setError(err instanceof ApiError ? err.message : "Couldn't load procurement.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, business?.id]);

  useLivePoll(() => reload({ soft: true }), { intervalMs: 8000 });

  const actions = (dash?.next_actions ?? []).filter(Boolean) as { key: string; label: string }[];
  const quoteTotal =
    dash?.rfqs.reduce((n, r) => n + (r.quotation_count || 0), 0) ?? 0;

  return (
    <div className="tb-inv-page tb-proc-desk">
      <InventoryPageHeader
        eyebrow={isSupplier ? "Fulfilment" : "Procurement"}
        title={isSupplier ? "Supplier desk" : "Buying desk"}
        description={
          isSupplier
            ? "Incoming RFQs, quotations, and negotiations."
            : "Send RFQs, review quotations, and negotiate."
        }
        meta={
          dash ? (
            <>
              <span className="tb-inv-chip">{dash.rfqs.length} open RFQs</span>
              <span className="tb-inv-chip">{quoteTotal} quotes</span>
            </>
          ) : null
        }
        actions={
          !isSupplier && hasPermission("rfqs.create") ? (
            <InventoryLinkBtn href={ROUTES.procurementNew} tone="accent">
              + Create RFQ
            </InventoryLinkBtn>
          ) : (
            <InventoryLinkBtn href={ROUTES.quotations} tone="soft">
              Quotations →
            </InventoryLinkBtn>
          )
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Procurement unavailable">
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <div className="tb-proc-panel">
          <InventorySkeleton entity="orders" />
        </div>
      ) : null}

      {!loading && dash ? (
        <>
          <section className="tb-inv-kpi-grid" aria-label="Pipeline snapshot">
            <InventoryKpi
              index={0}
              label={isSupplier ? "Invitations" : "Active RFQs"}
              value={dash.rfqs.length}
            />
            <InventoryKpi
              index={1}
              label="Orders"
              value="Soon"
              tone="accent"
            />
            <InventoryKpi
              index={2}
              label="Next actions"
              value={actions.length}
              tone={actions.length > 0 ? "warn" : "ok"}
            />
            <InventoryKpi
              index={3}
              label="Quotes in view"
              value={quoteTotal}
              tone="ok"
            />
          </section>

          <nav className="tb-proc-lanes" aria-label="Commerce shortcuts">
            <Link href={ROUTES.quotations} className="tb-proc-lane">
              <strong>Quotations</strong>
              <span>{isSupplier ? "Incoming RFQs and your responses" : "Review and accept supplier quotations"}</span>
            </Link>
            <Link href={ROUTES.orders} className="tb-proc-lane">
              <strong>Purchase orders</strong>
              <span>Coming soon</span>
            </Link>
            <Link href={ROUTES.finance} className="tb-proc-lane">
              <strong>Finance</strong>
              <span>Coming soon</span>
            </Link>
          </nav>

          {actions.length > 0 ? (
            <section className="tb-proc-panel tb-proc-actions" aria-labelledby="tb-proc-actions-title">
              <header className="tb-proc-panel__head">
                <div>
                  <h2 id="tb-proc-actions-title">Next actions</h2>
                </div>
              </header>
              <ul className="tb-proc-action-list">
                {actions.map((a) => (
                  <li key={a.key}>
                    <Link href={actionHref(a.key, isSupplier)} className="tb-proc-action">
                      <span>{a.label}</span>
                      <em aria-hidden>→</em>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <div className="tb-proc-split">
            <section className="tb-proc-panel" aria-labelledby="tb-proc-rfqs-title">
              <header className="tb-proc-panel__head">
                <div>
                  <h2 id="tb-proc-rfqs-title">
                    {isSupplier ? "On your desk" : "Deals in play"}
                  </h2>
                  <p>
                    {isSupplier
                      ? "Requests waiting for your quotation"
                      : "Your open RFQs"}
                  </p>
                </div>
                <InventoryLinkBtn
                  href={isSupplier ? ROUTES.quotations : ROUTES.procurementNew}
                  tone="ghost"
                >
                  {isSupplier ? "View all" : "New RFQ"}
                </InventoryLinkBtn>
              </header>

              {dash.rfqs.length === 0 ? (
                <InventoryEmpty
                  title="No RFQs yet"
                  body={
                    isSupplier
                      ? "When buyers invite you, requests appear here."
                      : "Create an RFQ to invite verified suppliers."
                  }
                  action={
                    !isSupplier && hasPermission("rfqs.create") ? (
                      <InventoryLinkBtn href={ROUTES.procurementNew} tone="accent">
                        Create RFQ
                      </InventoryLinkBtn>
                    ) : null
                  }
                />
              ) : (
                <ul className="tb-proc-list">
                  {dash.rfqs.map((rfq) => (
                    <li key={rfq.id}>
                      <Link
                        href={ROUTES.procurementRfq(rfq.id)}
                        className="tb-proc-row"
                      >
                        <div className="tb-proc-row__main">
                          <strong>{rfq.rfq_number}</strong>
                          <span>{rfq.title || "Untitled request"}</span>
                          <span className="tb-proc-row__meta">
                            {isSupplier && rfq.buyer_name
                              ? `From ${rfq.buyer_name} · `
                              : ""}
                            {rfq.quotation_count
                              ? `${rfq.quotation_count} on the table`
                              : isSupplier
                                ? "Awaiting your quotation"
                                : `${rfq.invite_count} invited`}
                          </span>
                        </div>
                        <StatusBadge status={rfq.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="tb-proc-panel" aria-labelledby="tb-proc-pos-title">
              <header className="tb-proc-panel__head">
                <div>
                  <h2 id="tb-proc-pos-title">Purchase orders</h2>
                  <p>Coming soon</p>
                </div>
                <InventoryLinkBtn href={ROUTES.orders} tone="ghost">
                  Open
                </InventoryLinkBtn>
              </header>

              <InventoryEmpty
                title="Orders are coming soon"
                action={
                  <InventoryLinkBtn href={ROUTES.orders} tone="soft">
                    Coming soon →
                  </InventoryLinkBtn>
                }
              />
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
