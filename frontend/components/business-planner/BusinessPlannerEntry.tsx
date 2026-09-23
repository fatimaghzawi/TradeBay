"use client";

import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { businessPlannerApi, type BusinessPlan } from "@/lib/api/businessPlannerApi";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useState } from "react";

export function BusinessPlannerEntry() {
  const [plans, setPlans] = useState<BusinessPlan[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10;

  useEffect(() => {
    setLoading(true);
    void businessPlannerApi
      .listPlans(page, pageSize)
      .then((res) => {
        setPlans(res.data);
        setTotal(res.meta.total);
        setError(null);
      })
      .catch((err) => {
        setPlans([]);
        setError(err instanceof ApiError ? err.message : "Could not load your plans.");
      })
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow="Business Planner"
        title="Plan your next business"
        description="Answer a few questions and we’ll draft your plan."
        actions={
          <>
            <InventoryLinkBtn href={ROUTES.businessPlannerNew} tone="primary">
              Build my business
            </InventoryLinkBtn>
            <InventoryLinkBtn href={ROUTES.marketplace} tone="soft">
              I already have a business
            </InventoryLinkBtn>
          </>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Couldn't load plans">
          {error}
        </FeedbackBanner>
      ) : null}

      <InventoryPanel
        title="Your plans"
        subtitle={total > 0 ? `${total} plan${total === 1 ? "" : "s"}` : "Saved plans appear here"}
        action={
          plans.length > 0 ? (
            <InventoryLinkBtn href={ROUTES.businessPlannerNew} tone="accent">
              New plan
            </InventoryLinkBtn>
          ) : null
        }
      >
        {loading ? (
          <InventorySkeleton entity="plans" />
        ) : plans.length === 0 ? (
          <InventoryEmpty
            title="No plans yet"
            body="Start the discovery wizard to create your first plan."
            action={
              <InventoryLinkBtn href={ROUTES.businessPlannerNew} tone="primary">
                Start planning
              </InventoryLinkBtn>
            }
          />
        ) : (
          <ul className="tb-inv-entity-list">
            {plans.map((p) => (
              <li key={p.id}>
                <Link href={ROUTES.businessPlannerPlan(p.id)} className="tb-inv-entity-row">
                  <div>
                    <strong>{p.title || "Untitled plan"}</strong>
                    <span className="tb-inv-entity-sub">
                      {p.location || "Lebanon"} · v{p.version}
                      {p.business_type ? ` · ${p.business_type}` : ""}
                    </span>
                  </div>
                  <div className="tb-inv-entity-meta">
                    <StatusBadge status={p.status || "draft"} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}

        {!loading && totalPages > 1 ? (
          <div className="tb-inv-form-actions mt-4">
            <button
              type="button"
              className="tb-inv-btn tb-inv-btn-ghost"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span className="tb-inv-muted">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="tb-inv-btn tb-inv-btn-ghost"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        ) : null}
      </InventoryPanel>
    </div>
  );
}
