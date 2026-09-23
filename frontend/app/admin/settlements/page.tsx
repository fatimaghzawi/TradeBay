"use client";

import {
  InventoryBtn,
  InventoryEmpty,
  InventoryKpi,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  platformMoneyApi,
  type PlatformMoneyOverview,
  type PlatformTransaction,
  type SupplierPayout,
} from "@/lib/api/platformMoneyApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export default function AdminSettlementsPage() {
  const { hasPermission } = useAuth();
  const { success, error: toastError } = useToast();
  const [overview, setOverview] = useState<PlatformMoneyOverview | null>(null);
  const [payouts, setPayouts] = useState<SupplierPayout[]>([]);
  const [transactions, setTransactions] = useState<PlatformTransaction[]>([]);
  const [releaseOrderId, setReleaseOrderId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const canApprove = hasPermission("settlements.approve");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, pay, tx] = await Promise.all([
        platformMoneyApi.overview(),
        platformMoneyApi.listPayouts({ page_size: 50 }),
        platformMoneyApi.listTransactions({ page_size: 40 }),
      ]);
      setOverview(ov);
      setPayouts(pay.data);
      setTransactions(tx.data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load settlements");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function processPayout(id: string) {
    setBusy(id);
    void platformMoneyApi
      .processPayout(id)
      .then(() => {
        success("Payout processed");
        return load();
      })
      .catch((err) =>
        toastError("Process failed", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  function failPayout(id: string) {
    const reason = window.prompt("Failure reason (optional)") ?? undefined;
    setBusy(id);
    void platformMoneyApi
      .failPayout(id, reason || undefined)
      .then(() => {
        success("Payout marked failed");
        return load();
      })
      .catch((err) =>
        toastError("Couldn't update", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  function releaseFunds() {
    const orderId = releaseOrderId.trim();
    if (!orderId) return;
    setBusy("release");
    void platformMoneyApi
      .releaseOrderFunds(orderId)
      .then(() => {
        success("Funds released — payout created if eligible");
        setReleaseOrderId("");
        return load();
      })
      .catch((err) =>
        toastError("Release failed", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  const currency = overview?.currency ?? "USD";

  return (
    <div className="tb-inv-page tb-cc">
      <InventoryPageHeader
        eyebrow="Admin · Finance"
        mark="Platform"
        title="Settlements"
        actions={
          <>
            <InventoryLinkBtn href={ROUTES.admin.finance} tone="soft">
              Finance desk →
            </InventoryLinkBtn>
            <InventoryLinkBtn href={ROUTES.admin.home} tone="ghost">
              ← Command center
            </InventoryLinkBtn>
          </>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Settlements error">
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-inv-kpi-grid">
        <InventoryKpi
          index={0}
          label="Held"
          value={overview ? `${currency} ${overview.held_amount}` : "—"}
          hint="Payments not yet released"
          tone="warn"
          icon="$"
        />
        <InventoryKpi
          index={1}
          label="Pending payouts"
          value={overview?.pending_payouts_count ?? "—"}
          hint={
            overview
              ? `${currency} ${overview.pending_payouts_net} net`
              : "Awaiting process"
          }
          tone="accent"
          icon="☰"
        />
        <InventoryKpi
          index={2}
          label="Released"
          value={overview ? `${currency} ${overview.released_amount}` : "—"}
          hint="Moved into settlement"
          icon="◎"
        />
        <InventoryKpi
          index={3}
          label="Open payables"
          value={overview?.open_payables_count ?? "—"}
          hint="Supplier AP still open"
          icon="◇"
        />
      </div>

      {canApprove ? (
        <InventoryPanel
          title="Release held funds"
          subtitle="After fulfilment, release an order’s held payment to create the supplier payout."
        >
          <div className="flex flex-wrap items-end gap-3 px-1 pb-1">
            <label className="flex min-w-[16rem] flex-1 flex-col gap-1 text-sm">
              <span className="font-semibold text-[#0d3b2a]">Purchase order</span>
              <input
                className="tb-inv-inline-input !w-full"
                value={releaseOrderId}
                onChange={(e) => setReleaseOrderId(e.target.value)}
                placeholder="Order number"
              />
            </label>
            <InventoryBtn
              tone="accent" busy={busy === "release"} disabled={busy === "release" || !releaseOrderId.trim()}
              onClick={releaseFunds}
            >
              {busy === "release" ? "Releasing…" : "Release funds"}
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      <div className="tb-inv-split">
        <InventoryPanel title="Supplier payouts" flush>
          {loading && payouts.length === 0 ? (
            <LoadingEntity entity="settlements" className="px-5 py-4" />
          ) : payouts.length === 0 ? (
            <InventoryEmpty
              title="No payouts yet"
              body="Payouts appear after funds are released on a fulfilled order."
            />
          ) : (
            <ul className="tb-inv-entity-list px-5 pb-4">
              {payouts.map((p) => (
                <li key={p.id} className="tb-inv-entity-row !items-start">
                  <div>
                    <strong>{p.payout_number}</strong>
                    <span className="tb-inv-entity-sub">
                      {p.currency} {p.net_amount} net
                      {p.platform_fee_amount
                        ? ` · fee ${p.platform_fee_amount}`
                        : ""}
                    </span>
                    {p.failure_reason ? (
                      <div className="tb-inv-muted mt-1">{p.failure_reason}</div>
                    ) : null}
                  </div>
                  <div className="tb-inv-entity-meta">
                    <StatusBadge status={p.status} />
                    {canApprove &&
                    (p.status === "pending" || p.status === "processing") ? (
                      <>
                        <InventoryBtn
                          tone="accent" busy={busy === p.id} disabled={busy === p.id}
                          onClick={() => processPayout(p.id)}
                        >
                          Process
                        </InventoryBtn>
                        <InventoryBtn
                          tone="ghost" busy={busy === p.id} disabled={busy === p.id}
                          onClick={() => failPayout(p.id)}
                        >
                          Fail
                        </InventoryBtn>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </InventoryPanel>

        <InventoryPanel title="Routing ledger" flush>
          {loading && transactions.length === 0 ? (
            <LoadingEntity entity="settlements" className="px-5 py-4" />
          ) : transactions.length === 0 ? (
            <InventoryEmpty
              title="Ledger empty"
              body="Buyer payments, fees, releases, and payouts post here."
            />
          ) : (
            <ul className="tb-inv-entity-list px-5 pb-4">
              {transactions.map((tx) => (
                <li key={tx.id} className="tb-inv-entity-row">
                  <div>
                    <strong>{tx.type.replaceAll("_", " ")}</strong>
                    <span className="tb-inv-entity-sub">
                      {tx.transaction_number}
                      {tx.funds_state ? ` · ${tx.funds_state}` : ""}
                      {tx.order_id ? (
                        <>
                          {" · "}
                          <Link
                            href={ROUTES.procurementOrder(tx.order_id)}
                            className="font-semibold text-[var(--tb-accent)]"
                          >
                            Order
                          </Link>
                        </>
                      ) : null}
                    </span>
                  </div>
                  <div className="tb-inv-entity-meta">
                    <span className="font-semibold">
                      {tx.currency} {tx.amount}
                    </span>
                    <StatusBadge status={tx.status || "posted"} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </InventoryPanel>
      </div>
    </div>
  );
}
