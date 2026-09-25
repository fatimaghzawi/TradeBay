"use client";

import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { procurementApi, type RFQSummary } from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { statusLabel } from "@/lib/procurement/rfqLifecycle";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { BackLink } from "@/components/ui/BackLink";

export default function QuotationsPage() {
  const { business } = useAuth();
  const asSupplier = business?.type === "supplier";
  const [rfqs, setRfqs] = useState<RFQSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(
    async (opts?: { soft?: boolean }) => {
      if (!opts?.soft) setLoading(true);
      try {
        const res = await procurementApi.listRfqs({ page_size: 50, as_supplier: asSupplier });
        const live = asSupplier
          ? res.data
          : res.data.filter((rfq) => !["cancelled", "expired"].includes(rfq.status));
        setRfqs(live);
        setError(null);
      } catch (err) {
        if (!opts?.soft) {
          setError(err instanceof ApiError ? err.message : "Couldn't load quotations");
        }
      } finally {
        setLoading(false);
      }
    },
    [asSupplier],
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  useLivePoll(() => reload({ soft: true }), {
    intervalMs: 6000,
    enabled: true,
  });

  return (
    <div className="tb-inv-page tb-deal">
      <InventoryPageHeader
        eyebrow={asSupplier ? "Your desk" : "Buying desk"}
        title={asSupplier ? "Requests on your desk" : "Deals in play"}
        description={
          asSupplier
            ? "Open a request and send your quotation."
            : "Your RFQs and supplier quotations."
        }
        meta={<span className="tb-inv-chip">{rfqs.length} live</span>}
        actions={
          <BackLink href={ROUTES.procurement}>Procurement hub</BackLink>
        }
      />
      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}
      {loading ? (
        <LoadingEntity entity="deals" />
      ) : rfqs.length === 0 ? (
        <InventoryEmpty
          title={asSupplier ? "No quotations yet" : "No deals yet"}
          body={
            asSupplier
              ? "New requests will appear here."
              : "Create an RFQ to get started."
          }
        />
      ) : (
        <ul className="tb-deal-inbox">
          {rfqs.map((rfq) => (
            <li key={rfq.id}>
              <Link href={ROUTES.procurementRfq(rfq.id)} className="tb-deal-card">
                <div className="tb-deal-card__top">
                  <em>{rfq.rfq_number}</em>
                  <StatusBadge status={rfq.status} />
                </div>
                <strong>{rfq.title}</strong>
                <p>
                  {asSupplier && rfq.buyer_name ? `From ${rfq.buyer_name} · ` : ""}
                  {rfq.quotation_count
                    ? `${rfq.quotation_count} quotation${rfq.quotation_count === 1 ? "" : "s"} received`
                    : asSupplier
                      ? "Awaiting your quotation"
                      : rfq.status === "draft"
                        ? "Draft — not sent yet"
                        : "Sent — waiting for their quotation"}
                  {" · "}
                  {statusLabel(rfq.status)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
