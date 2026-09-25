"use client";

import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Modal } from "@/components/ui/Modal";
import { checkoutApi, type SupplierFinancialOverview, type SupplierFinanceOrder } from "@/lib/api/checkoutApi";
import { ApiError } from "@/lib/api/client";
import { formatDate, formatMoney, isPositive } from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type RangeKey = "7d" | "30d" | "90d" | "year";
type Section = "summary" | "payments" | "balance" | "payouts" | "activity";

const SECTIONS: { id: Section; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "payments", label: "Payments" },
  { id: "balance", label: "Supplier balance" },
  { id: "payouts", label: "Payouts" },
  { id: "activity", label: "Financial activity" },
];

const ACTIVITY_FILTERS: { id: string; label: string }[] = [
  { id: "buyer_payments", label: "Buyer payments" },
  { id: "commission", label: "Commission" },
  { id: "funds_held", label: "Funds held" },
  { id: "funds_released", label: "Funds released" },
  { id: "ready", label: "Ready for payout" },
  { id: "payouts", label: "Supplier payouts" },
  { id: "refunds", label: "Refunds" },
  { id: "credits", label: "Credit notes" },
];

const STATE_LABEL: Record<string, string> = {
  held: "Held",
  ready: "Ready to pay",
  paid: "Paid",
  partial: "Partly paid",
};

function cents(amount: string | null | undefined): bigint {
  const raw = String(amount ?? "0").trim() || "0";
  const negative = raw.startsWith("-");
  const [whole = "0", frac = ""] = (negative ? raw.slice(1) : raw).split(".");
  const value = BigInt(`${whole || "0"}${(frac + "00").slice(0, 2)}`);
  return negative ? -value : value;
}

function shareWidth(part: string, whole: string): string {
  const total = cents(whole);
  if (total <= BigInt(0)) return "0%";
  const pct = (cents(part) * BigInt(1000)) / total;
  if (pct <= BigInt(0)) return "0%";
  return `${(pct / BigInt(10)).toString()}.${(pct % BigInt(10)).toString()}%`;
}

function moneyText(amount: string, currency: string, sign?: "plus" | "plain" | "minus"): string {
  const body = formatMoney(amount, currency);
  if (sign === "plus") return `+${body}`;
  if (sign === "minus") return `−${body}`;
  return body;
}

function withinRange(iso: string | null, range: RangeKey | "custom" | "all", from: string, to: string): boolean {
  if (!iso || range === "all") return true;
  const when = new Date(iso).getTime();
  if (Number.isNaN(when)) return false;
  if (range === "custom") {
    const start = from ? new Date(`${from}T00:00:00Z`).getTime() : Number.NEGATIVE_INFINITY;
    const end = to ? new Date(`${to}T23:59:59Z`).getTime() : Number.POSITIVE_INFINITY;
    return when >= start && when <= end;
  }
  const days = range === "7d" ? 7 : range === "30d" ? 30 : range === "90d" ? 90 : 365;
  const start = Date.now() - days * 24 * 60 * 60 * 1000;
  if (range === "year") {
    const yearStart = Date.UTC(new Date().getUTCFullYear(), 0, 1);
    return when >= yearStart;
  }
  return when >= start;
}

export function SupplierFinancials({ supplierId, supplierName }: { supplierId: string; supplierName: string }) {
  const [data, setData] = useState<SupplierFinancialOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("summary");
  const [reconcile, setReconcile] = useState(false);
  const [orderQuery, setOrderQuery] = useState("");
  const [activityRange, setActivityRange] = useState<RangeKey | "all" | "custom">("all");
  const [activityFrom, setActivityFrom] = useState("");
  const [activityTo, setActivityTo] = useState("");
  const [activityKind, setActivityKind] = useState("all");
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void checkoutApi
      .adminSupplierOverview(supplierId, "30d")
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "This supplier's finances couldn't be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [supplierId]);

  const currency = data?.currency || "USD";
  const name = data?.supplier_name || supplierName;
  const outstandingOrders = useMemo(
    () => (data?.orders ?? []).filter((order) => isPositive(order.remaining)),
    [data],
  );

  if (loading && !data) return <LoadingEntity entity="supplier finances" />;
  if (error && !data) {
    return (
      <FeedbackBanner tone="error" title="Finances unavailable">
        {error}
      </FeedbackBanner>
    );
  }
  if (!data) return null;
  if (data.paid_order_count === 0) {
    return (
      <p className="mt-6 text-sm text-muted-foreground">
        No paid orders yet. This supplier’s balance, commission, and payouts appear after a buyer pays.
      </p>
    );
  }

  return (
    <div className="tb-fin-desk mt-6">
      <header className="tb-sup-fin__hero">
        <button type="button" className="tb-sup-fin__owed" onClick={() => setReconcile(true)}>
          <span>Supplier balance</span>
          <strong>{formatMoney(data.outstanding, currency)}</strong>
          <em>owed · open the reconciliation</em>
        </button>
        <ul className="tb-sup-fin__facts">
          <li>
            <span>Payment status</span>
            <strong>
              {isPositive(data.held)
                ? `${formatMoney(data.held, currency)} held`
                : isPositive(data.ready)
                  ? `${formatMoney(data.ready, currency)} ready`
                  : "Settled"}
            </strong>
          </li>
          <li>
            <span>Orders</span>
            <strong>
              {data.paid_order_count} paid
            </strong>
          </li>
          <li>
            <span>Last payment</span>
            <strong>
              {data.last_payment
                ? `${formatMoney(data.last_payment.amount, currency)} · ${formatDate(data.last_payment.paid_at)}`
                : "—"}
            </strong>
          </li>
        </ul>
        <div className="tb-sup-fin__bar" role="img" aria-label="Supplier earnings split into paid, held, and ready">
          <i data-state="paid" style={{ width: shareWidth(data.paid, data.supplier_earnings) }} />
          <i data-state="held" style={{ width: shareWidth(data.held, data.supplier_earnings) }} />
          <i data-state="ready" style={{ width: shareWidth(data.ready, data.supplier_earnings) }} />
        </div>
      </header>

      <nav className="tb-sup-fin__nav" aria-label="Supplier financial sections">
        {SECTIONS.map((item) => (
          <button key={item.id} type="button" data-active={section === item.id || undefined} onClick={() => setSection(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>

      {section === "summary" ? (
        <div className="mt-5 grid gap-5">
          <Equation data={data} currency={currency} onOpen={() => setReconcile(true)} />
          <Flow data={data} currency={currency} />
        </div>
      ) : null}

      {section === "payments" ? (
        <OrdersTable orders={data.orders} currency={currency} />
      ) : null}

      {section === "balance" ? (
        <ReconcileBody data={data} currency={currency} orders={outstandingOrders} />
      ) : null}

      {section === "payouts" ? <PayoutList data={data} currency={currency} /> : null}

      {section === "activity" ? (
        <Activity
          data={data}
          currency={currency}
          range={activityRange}
          from={activityFrom}
          to={activityTo}
          kind={activityKind}
          query={orderQuery}
          onRange={setActivityRange}
          onFrom={setActivityFrom}
          onTo={setActivityTo}
          onKind={setActivityKind}
          onQuery={setOrderQuery}
        />
      ) : null}

      <Modal open={reconcile} onClose={() => setReconcile(false)} title="Balance reconciliation" kicker={name}>
        <ReconcileBody data={data} currency={currency} orders={outstandingOrders} />
      </Modal>
    </div>
  );
}

function Equation({
  data,
  currency,
  onOpen,
}: {
  data: SupplierFinancialOverview;
  currency: string;
  onOpen: () => void;
}) {
  const lines = [
    ["Gross sales", data.gross_sales, "Total value of paid orders."],
    ["TradeBay commission", data.commission, "Commission retained by TradeBay."],
    ["Supplier earnings", data.supplier_earnings, "Gross sales minus TradeBay commission."],
    ["Already paid", data.paid, "Recorded as paid to the supplier."],
    ["Outstanding", data.outstanding, "Amount TradeBay currently owes this supplier."],
  ] as const;
  return (
    <section>
      <h2 className="tb-section-label">Financial overview</h2>
      <ol className="tb-sup-fin__eq">
        {lines.map(([label, amount, hint], index) => {
          const op = index === 0 ? "" : index === 2 || index === 4 ? "=" : "−";
          return (
            <li key={label} data-op={index === 2 || index === 4 ? "result" : index === 0 ? "start" : "minus"}>
              <b aria-hidden>{op}</b>
              <span>
                {label}
                <em>{hint}</em>
              </span>
              <button type="button" onClick={onOpen}>
                {formatMoney(amount, currency)}
              </button>
            </li>
          );
        })}
      </ol>
      <p className="tb-sup-fin__note">
        Currently held {formatMoney(data.held, currency)} · Ready to pay {formatMoney(data.ready, currency)}. Outstanding
        is held plus ready, after what has already been paid.
      </p>
    </section>
  );
}

function Flow({ data, currency }: { data: SupplierFinancialOverview; currency: string }) {
  return (
    <section>
      <h2 className="tb-section-label">Where is this supplier&apos;s money?</h2>
      <ol className="tb-sup-fin__flow">
        <li>
          <span>Buyer payments</span>
          <strong>{formatMoney(data.gross_sales, currency)}</strong>
        </li>
        <li>
          <span>TradeBay commission</span>
          <strong>{formatMoney(data.commission, currency)}</strong>
        </li>
        <li data-end>
          <span>Supplier earnings</span>
          <strong>{formatMoney(data.supplier_earnings, currency)}</strong>
        </li>
      </ol>
      <div className="tb-sup-fin__bar tb-sup-fin__bar--legend" role="img" aria-label="Paid, held, and ready portions of supplier earnings">
        <i data-state="paid" style={{ width: shareWidth(data.paid, data.supplier_earnings) }} />
        <i data-state="held" style={{ width: shareWidth(data.held, data.supplier_earnings) }} />
        <i data-state="ready" style={{ width: shareWidth(data.ready, data.supplier_earnings) }} />
      </div>
      <ul className="tb-sup-fin__legend">
        <li data-state="paid">
          <span>Paid</span>
          <strong>{formatMoney(data.paid, currency)}</strong>
        </li>
        <li data-state="held">
          <span>Held</span>
          <strong>{formatMoney(data.held, currency)}</strong>
        </li>
        <li data-state="ready">
          <span>Ready to pay</span>
          <strong>{formatMoney(data.ready, currency)}</strong>
        </li>
      </ul>
    </section>
  );
}

function OrdersTable({ orders, currency }: { orders: SupplierFinanceOrder[]; currency: string }) {
  return (
    <section className="mt-5">
      <h2 className="tb-section-label">Orders and supplier earnings</h2>
      <p className="mt-1 text-sm text-muted-foreground">Every paid order for this supplier.</p>
      <div className="tb-co-scroll mt-3">
        <table className="tb-inv-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Buyer</th>
              <th>Order value</th>
              <th>Commission</th>
              <th>Supplier earnings</th>
              <th>Money state</th>
              <th>Paid</th>
              <th>Remaining</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.order_id}>
                <td>
                  <Link href={ROUTES.procurementOrder(order.order_id)} className="tb-co-link">
                    {order.order_number || "Order"}
                  </Link>
                </td>
                <td>{order.buyer_name || "—"}</td>
                <td className="tb-co-num">{formatMoney(order.order_value, currency)}</td>
                <td className="tb-co-num">{formatMoney(order.commission, currency)}</td>
                <td className="tb-co-num">{formatMoney(order.supplier_earnings, currency)}</td>
                <td>
                  <span className="tb-sup-fin__state" data-state={order.money_state}>
                    {STATE_LABEL[order.money_state] || order.money_state}
                  </span>
                </td>
                <td className="tb-co-num">{formatMoney(order.paid, currency)}</td>
                <td className="tb-co-num">{formatMoney(order.remaining, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Lifecycle orders={orders} />
    </section>
  );
}

function Lifecycle({ orders }: { orders: SupplierFinanceOrder[] }) {
  const steps: { key: keyof SupplierFinanceOrder["lifecycle"]; label: string }[] = [
    { key: "buyer_paid", label: "Buyer paid" },
    { key: "held", label: "Held" },
    { key: "fulfilled", label: "Fulfilled" },
    { key: "released", label: "Released" },
    { key: "supplier_paid", label: "Supplier paid" },
  ];
  return (
    <section className="mt-6">
      <h2 className="tb-section-label">Payment lifecycle</h2>
      <ul className="mt-3 grid gap-3">
        {orders.map((order) => (
          <li key={order.order_id} className="tb-sup-fin__life">
            <strong>{order.order_number || "Order"}</strong>
            <ol>
              {steps.map((step) => (
                <li key={step.key} data-on={order.lifecycle[step.key] || undefined}>
                  <i aria-hidden />
                  {step.label}
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReconcileBody({
  data,
  currency,
  orders,
}: {
  data: SupplierFinancialOverview;
  currency: string;
  orders: SupplierFinanceOrder[];
}) {
  const lines = [
    ["Gross buyer payments", data.gross_sales, "plus"],
    ["TradeBay commission", data.commission, "minus"],
    ["Supplier earnings", data.supplier_earnings, "result"],
    ["Already paid", data.paid, "minus"],
    ["Outstanding", data.outstanding, "result"],
  ] as const;
  return (
    <div className="grid gap-4">
      <ol className="tb-sup-fin__eq">
        {lines.map(([label, amount, op]) => (
          <li key={label} data-op={op}>
            <span>{label}</span>
            <strong>{moneyText(amount, currency, op === "plus" ? "plus" : op === "minus" ? "minus" : "plain")}</strong>
          </li>
        ))}
      </ol>
      <div>
        <h3 className="tb-section-label">Outstanding by order</h3>
        {orders.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No orders currently contribute to the outstanding balance.</p>
        ) : (
          <ul className="tb-data mt-2">
            {orders.map((order) => (
              <li key={order.order_id} className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]">
                <span>
                  {order.order_number || "Order"}
                  <span className="text-muted-foreground"> · {STATE_LABEL[order.money_state] || order.money_state}</span>
                </span>
                <strong>{formatMoney(order.remaining, currency)}</strong>
              </li>
            ))}
            <li className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]">
              <span>Total outstanding</span>
              <strong>{formatMoney(data.outstanding, currency)}</strong>
            </li>
          </ul>
        )}
      </div>
    </div>
  );
}

function PayoutList({ data, currency }: { data: SupplierFinancialOverview; currency: string }) {
  return (
    <section className="mt-5">
      <h2 className="tb-section-label">Payouts</h2>
      {data.payouts.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">No supplier payouts have been created.</p>
      ) : (
        <ul className="tb-data mt-3">
          {data.payouts.map((payout) => (
            <li key={payout.id} className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]">
              <div>
                <strong>{payout.payout_number || "Payout"}</strong>
                <p className="text-sm text-muted-foreground">
                  {payout.order_number || "Supplier payout"} · {payout.status || "—"}
                  {payout.completed_at ? ` · ${formatDate(payout.completed_at)}` : ""}
                </p>
              </div>
              <strong>{formatMoney(payout.net_amount, payout.currency || currency)}</strong>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Activity({
  data,
  currency,
  range,
  from,
  to,
  kind,
  query,
  onRange,
  onFrom,
  onTo,
  onKind,
  onQuery,
}: {
  data: SupplierFinancialOverview;
  currency: string;
  range: RangeKey | "all" | "custom";
  from: string;
  to: string;
  kind: string;
  query: string;
  onRange: (range: RangeKey | "all" | "custom") => void;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
  onKind: (value: string) => void;
  onQuery: (value: string) => void;
}) {
  const needle = query.trim().toLowerCase();
  const events = data.activity.filter((event) => {
    if (kind !== "all" && !event.filters.includes(kind)) return false;
    if (needle && !(event.order_number || "").toLowerCase().includes(needle)) return false;
    return withinRange(event.created_at, range, from, to);
  });
  return (
    <section className="mt-5 grid gap-3">
      <h2 className="tb-section-label">Recent financial activity</h2>
      <div className="tb-fin-chart__ranges">
        {(
          [
            ["all", "All"],
            ["7d", "7 days"],
            ["30d", "30 days"],
            ["90d", "90 days"],
            ["year", "This year"],
            ["custom", "Custom"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" data-active={range === id || undefined} onClick={() => onRange(id)}>
            {label}
          </button>
        ))}
      </div>
      {range === "custom" ? (
        <div className="flex flex-wrap gap-2">
          <input type="date" value={from} onChange={(event) => onFrom(event.target.value)} className="h-9 rounded-lg border border-input px-3 text-sm" />
          <input type="date" value={to} onChange={(event) => onTo(event.target.value)} className="h-9 rounded-lg border border-input px-3 text-sm" />
        </div>
      ) : null}
      <div className="tb-fin-chart__ranges">
        <button type="button" data-active={kind === "all" || undefined} onClick={() => onKind("all")}>
          All activity
        </button>
        {ACTIVITY_FILTERS.map((item) => (
          <button key={item.id} type="button" data-active={kind === item.id || undefined} onClick={() => onKind(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      <input
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        placeholder="Search by order number"
        className="h-9 max-w-xs rounded-lg border border-input px-3 text-sm"
      />
      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground">No financial activity matches these filters.</p>
      ) : (
        <ul className="tb-sup-fin__timeline">
          {events.map((event) => (
            <li key={event.id} className="tb-sup-fin__event">
              <div>
                <strong>{event.title}</strong>
                <p>
                  {event.order_number || "Supplier"} · {formatDate(event.created_at)}
                </p>
                <p>{event.detail}</p>
              </div>
              <strong data-sign={event.sign}>{moneyText(event.amount, currency, event.sign)}</strong>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
