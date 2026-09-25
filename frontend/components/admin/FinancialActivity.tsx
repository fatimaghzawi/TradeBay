"use client";

import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { platformMoneyApi, type FinanceStory, type PlatformMoneyOverview } from "@/lib/api/platformMoneyApi";
import { ApiError } from "@/lib/api/client";
import { formatDateTime, formatMoney, isPositive, paymentMethodLabel } from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

type KindFilter = "all" | "buyer_payment" | "held" | "released" | "payout" | "commission" | "refund";
type StateFilter = "all" | "pending" | "held" | "ready" | "paid" | "refunded" | "failed";
type WhenFilter = "all" | "today" | "7d" | "30d" | "month" | "custom";

const KIND_LABEL: Record<string, string> = {
  buyer_payment: "Buyer payment received",
  payout: "Supplier payout completed",
  refund: "Refund to the buyer",
};

const STATE_LABEL: Record<string, string> = {
  pending: "Pending",
  held: "Held",
  ready: "Ready for payout",
  paid: "Paid",
  refunded: "Refunded",
  failed: "Failed",
};

function whenStamp(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function inRange(iso: string | null, when: WhenFilter, from: string, to: string): boolean {
  if (when === "all") return true;
  if (!iso) return false;
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return false;
  const now = new Date();
  if (when === "custom") {
    const start = from ? new Date(`${from}T00:00:00`).getTime() : Number.NEGATIVE_INFINITY;
    const end = to ? new Date(`${to}T23:59:59`).getTime() : Number.POSITIVE_INFINITY;
    return time >= start && time <= end;
  }
  if (when === "today") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    return time >= start;
  }
  if (when === "month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1).getTime();
    return time >= start;
  }
  const days = when === "7d" ? 7 : 30;
  return time >= Date.now() - days * 24 * 60 * 60 * 1000;
}

function matchesKind(story: FinanceStory, kind: KindFilter): boolean {
  if (kind === "all") return true;
  if (kind === "buyer_payment") return story.kind === "buyer_payment";
  if (kind === "payout") return story.kind === "payout";
  if (kind === "refund") return story.kind === "refund";
  if (kind === "held") return story.kind === "buyer_payment" && story.state === "held";
  if (kind === "released") return story.kind === "buyer_payment" && (story.state === "ready" || story.state === "paid");
  if (kind === "commission") return story.kind === "buyer_payment" && isPositive(story.commission);
  return true;
}

export function FinancialActivity({ overview }: { overview: PlatformMoneyOverview }) {
  const [stories, setStories] = useState<FinanceStory[]>([]);
  const [today, setToday] = useState<FinancialToday | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<KindFilter>("all");
  const [state, setState] = useState<StateFilter>("all");
  const [when, setWhen] = useState<WhenFilter>("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"timeline" | "table">("timeline");
  const [open, setOpen] = useState<FinanceStory | null>(null);
  const currency = overview.currency || "USD";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void platformMoneyApi
      .financialActivity()
      .then((result) => {
        if (cancelled) return;
        setStories(result.stories);
        setToday(result.today);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Financial activity couldn't be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return stories.filter((story) => {
      if (!matchesKind(story, kind)) return false;
      if (state !== "all" && story.state !== state) return false;
      if (!inRange(story.posted_at, when, from, to)) return false;
      if (!needle) return true;
      return [story.order_number, story.buyer_name, story.supplier_name, story.payment_reference, story.payout_number, story.transaction_number, story.id]
        .some((value) => (value || "").toLowerCase().includes(needle));
    });
  }, [stories, kind, state, when, from, to, query]);

  if (loading) return <LoadingEntity entity="financial activity" />;
  if (error) {
    return (
      <FeedbackBanner tone="error" title="Financial activity couldn't be loaded">
        {error}
      </FeedbackBanner>
    );
  }

  return (
    <div className="tb-fact mt-4">
      <header>
        <h2>Financial activity</h2>
        <p>A complete history of money received, held, released, paid to suppliers, refunded, and earned by TradeBay.</p>
      </header>
      <div className="tb-fact__today">
        <article><span>Buyer payments today</span><strong>{formatMoney(today?.buyer_payments, currency)}</strong></article>
        <article><span>Supplier payouts today</span><strong>{formatMoney(today?.payouts, currency)}</strong></article>
        <article><span>TradeBay commission today</span><strong>{formatMoney(today?.commission, currency)}</strong></article>
        <article><span>Money currently held</span><strong>{formatMoney(overview.held_amount, currency)}</strong></article>
      </div>
      <ol className="tb-fact__flow">
        <li><span>Buyer payments</span><strong>{formatMoney(overview.buyer_payments_amount, currency)}</strong></li>
        <li><span>Currently held</span><strong>{formatMoney(overview.held_amount, currency)}</strong></li>
        <li><span>Released</span><strong>{formatMoney(overview.released_amount, currency)}</strong><em>Released is not the same as paid.</em></li>
        <li><span>Supplier payouts</span><strong>{formatMoney(overview.payouts_completed_amount, currency)}</strong></li>
        <li data-earn><span>TradeBay earnings</span><strong>{formatMoney(overview.fees_recognized_amount, currency)}</strong></li>
      </ol>
      <div className="tb-fact__filters">
        <select value={kind} onChange={(event) => setKind(event.target.value as KindFilter)} aria-label="Activity type">
          <option value="all">All activity</option>
          <option value="buyer_payment">Buyer payments</option>
          <option value="held">Funds held</option>
          <option value="released">Funds released</option>
          <option value="payout">Supplier payouts</option>
          <option value="commission">TradeBay commissions</option>
          <option value="refund">Refunds</option>
        </select>
        <select value={state} onChange={(event) => setState(event.target.value as StateFilter)} aria-label="Money state">
          <option value="all">Any money state</option>
          <option value="pending">Pending</option>
          <option value="held">Held</option>
          <option value="ready">Ready for payout</option>
          <option value="paid">Paid</option>
          <option value="refunded">Refunded</option>
          <option value="failed">Failed</option>
        </select>
        <select value={when} onChange={(event) => setWhen(event.target.value as WhenFilter)} aria-label="Date">
          <option value="all">Any date</option>
          <option value="today">Today</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="month">This month</option>
          <option value="custom">Custom range</option>
        </select>
        {when === "custom" ? (
          <>
            <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} aria-label="From" />
            <input type="date" value={to} onChange={(event) => setTo(event.target.value)} aria-label="To" />
          </>
        ) : null}
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Order, buyer, supplier, payment, or payout"
          aria-label="Search financial activity"
        />
        <div className="tb-fact__view">
          <button type="button" data-active={view === "timeline" || undefined} onClick={() => setView("timeline")}>Timeline</button>
          <button type="button" data-active={view === "table" || undefined} onClick={() => setView("table")}>Table</button>
        </div>
      </div>
      {visible.length === 0 ? (
        <p className="tb-fin-empty">No financial activity matches these filters.</p>
      ) : view === "table" ? (
        <div className="tb-co-scroll">
          <table className="tb-inv-table">
            <thead>
              <tr>
                <th>Date</th><th>Event</th><th>Order</th><th>Buyer</th><th>Supplier</th><th>Amount</th><th>State</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((story) => (
                <tr key={story.id} onClick={() => setOpen(story)}>
                  <td>{whenStamp(story.posted_at)}</td>
                  <td>{KIND_LABEL[story.kind] || story.kind}</td>
                  <td>{story.order_number || "—"}</td>
                  <td>{story.buyer_name || "—"}</td>
                  <td>{story.supplier_name || "—"}</td>
                  <td>{formatMoney(story.amount, story.currency)}</td>
                  <td>{STATE_LABEL[story.state] || story.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ul className="tb-fact__list">
          {visible.map((story) => (
            <li key={story.id}>
              <article className="tb-fact__card" data-kind={story.kind}>
                <time>{whenStamp(story.posted_at)}</time>
                <h3>{KIND_LABEL[story.kind] || "Money movement"}</h3>
                {story.order_number ? <p className="tb-fact__po">{story.order_number}</p> : null}
                <strong>{formatMoney(story.amount, story.currency)}</strong>
                <p>
                  {story.kind === "payout"
                    ? `TradeBay paid ${story.supplier_name || "the supplier"}.`
                    : story.kind === "refund"
                      ? `Money returned${story.order_number ? ` for ${story.order_number}` : ""}.`
                      : `Buyer payment received${story.supplier_name ? ` for the ${story.supplier_name} order` : ""}.`}
                </p>
                {story.kind === "buyer_payment" ? (
                  <dl>
                    {story.buyer_name ? <div><dt>Buyer</dt><dd>{story.buyer_name}</dd></div> : null}
                    {story.supplier_name ? <div><dt>Supplier</dt><dd>{story.supplier_name}</dd></div> : null}
                    {story.payment_method ? <div><dt>Method</dt><dd>{paymentMethodLabel(story.payment_method)}</dd></div> : null}
                    <div><dt>Buyer paid</dt><dd>{formatMoney(story.buyer_paid, story.currency)}</dd></div>
                    <div><dt>TradeBay commission</dt><dd>{formatMoney(story.commission, story.currency)}</dd></div>
                    <div><dt>Supplier earnings</dt><dd>{formatMoney(story.supplier_earnings, story.currency)}</dd></div>
                  </dl>
                ) : (
                  <dl>
                    {story.supplier_name ? <div><dt>Supplier</dt><dd>{story.supplier_name}</dd></div> : null}
                    {story.order_number ? <div><dt>Order</dt><dd>{story.order_number}</dd></div> : null}
                  </dl>
                )}
                <p className="tb-fact__state" data-state={story.state}>
                  {STATE_LABEL[story.state] || story.state}
                </p>
                <button type="button" className="tb-co-link" onClick={() => setOpen(story)}>
                  View financial details
                </button>
              </article>
            </li>
          ))}
        </ul>
      )}
      {open ? <StoryDrawer story={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

type FinancialToday = { buyer_payments: string; payouts: string; commission: string };

function StoryDrawer({ story, onClose }: { story: FinanceStory; onClose: () => void }) {
  const currency = story.currency || "USD";
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const figures = [
    ["Buyer paid", story.buyer_paid],
    ["TradeBay commission", story.commission],
    ["Supplier earnings", story.supplier_earnings],
    ["Supplier paid", story.supplier_paid],
    ["Still owed to the supplier", story.remaining],
  ] as const;

  const panel = (
    <div className="tb-fact__shade">
      <button type="button" className="tb-fact__shade-hit" aria-label="Close financial details" onClick={onClose} />
      <aside className="tb-fact__drawer" role="dialog" aria-modal="true" aria-label="Financial details">
        <header className="tb-fact__drawer-bar">
          <div>
            <p>{KIND_LABEL[story.kind] || "Money movement"}</p>
            <h2>{story.order_number || story.supplier_name || "Financial details"}</h2>
          </div>
          <button type="button" className="tb-fact__close" onClick={onClose}>
            <span aria-hidden>×</span>
            Close
          </button>
        </header>
        <div className="tb-fact__drawer-body">
          <p className="tb-fact__drawer-amount">{formatMoney(story.amount, currency)}</p>
          <p className="tb-fact__state" data-state={story.state}>{STATE_LABEL[story.state] || story.state}</p>
          <dl className="tb-fact__figures">
            {figures.map(([label, amount]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{formatMoney(amount, currency)}</dd>
              </div>
            ))}
            {isPositive(story.held_amount) ? (
              <div>
                <dt>Currently held</dt>
                <dd>{formatMoney(story.held_amount, currency)}</dd>
              </div>
            ) : null}
          </dl>
          {story.reason ? (
            <section className="tb-fact__why">
              <h3>Why this money is here</h3>
              <p>{story.reason}</p>
              {story.next_step ? <p>{story.next_step}</p> : null}
            </section>
          ) : null}
          <section>
            <h3>What happened</h3>
            <ol className="tb-fact__steps">
              {story.stages.map((stage) => (
                <li key={stage.key} data-done={stage.done || undefined} data-current={stage.current || undefined}>
                  <span>{stage.label}</span>
                  <strong>{stage.amount ? formatMoney(stage.amount, currency) : "Not yet"}</strong>
                </li>
              ))}
            </ol>
          </section>
          <section>
            <h3>Financial references</h3>
            <dl className="tb-fact__figures">
              <div><dt>Order</dt><dd>{story.order_number || "—"}</dd></div>
              <div><dt>Payment</dt><dd>{story.payment_reference || "—"}</dd></div>
              <div><dt>Supplier payable</dt><dd>{story.payable_number || "—"}</dd></div>
              <div><dt>Payout</dt><dd>{story.payout_number || "—"}</dd></div>
              <div><dt>Transaction</dt><dd>{story.transaction_number || story.id}</dd></div>
            </dl>
          </section>
          <div className="tb-fact__links">
            {story.order_id ? <Link href={ROUTES.procurementOrder(story.order_id)}>View order</Link> : null}
            {story.supplier_id ? <Link href={ROUTES.admin.businessDetail(story.supplier_id)}>View supplier</Link> : null}
          </div>
        </div>
      </aside>
    </div>
  );

  if (typeof document === "undefined") return panel;
  return createPortal(panel, document.body);
}
