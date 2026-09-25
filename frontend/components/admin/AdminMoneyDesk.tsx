"use client";

import { FinancialActivity } from "@/components/admin/FinancialActivity";
import {
  InventoryBtn,
  InventoryEmpty,
  InventoryPageHeader,
  InventoryPanel,
  InventoryTable,
  InventoryTabs,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { Pager } from "@/components/commerce/CommerceUi";
import { BackLink } from "@/components/ui/BackLink";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/useConfirm";
import { checkoutApi, type SupplierBalance, type SupplierLedgerEntry } from "@/lib/api/checkoutApi";
import { financeApi, type Payment } from "@/lib/api/financeApi";
import {
  platformMoneyApi,
  type BuyerPaymentRow,
  type FinanceActivity,
  type MoneyMovement,
  type OrderMoneyStory,
  type PlatformMoneyOverview,
} from "@/lib/api/platformMoneyApi";
import {
  errorText,
  formatDateTime,
  formatMoney,
  formatRate,
  sumMoney,
  paymentMethodLabel,
} from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Section = "overview" | "payments" | "balances" | "earnings" | "activity";
type RangeKey = "7d" | "30d" | "90d" | "year";

const PAGE_SIZE = 20;

const POSITION_LABEL: Record<string, string> = {
  ready: "Ready for payout",
  partially_paid: "Partially paid",
  paid: "Paid",
  on_hold: "On hold",
};

const POSITION_TONE: Record<string, "ok" | "wait" | "info" | "off"> = {
  ready: "wait",
  partially_paid: "info",
  paid: "ok",
  on_hold: "off",
};

function axisLabel(label: string): string {
  const week = label.match(/W\d{2}/);
  if (week) return week[0];
  const parts = label.split("-");
  if (parts.length === 3) return `${Number(parts[1])}/${Number(parts[2])}`;
  return label;
}

function fundsTone(label: string): string {
  const value = label.toLowerCase();
  if (value.includes("held")) return "held";
  if (value.includes("release")) return "ready";
  if (value.includes("refund")) return "partial";
  return "paid";
}

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

function barHeight(amount: string, max: bigint): string {
  if (max <= BigInt(0)) return "0%";
  const height = (cents(amount) * BigInt(100)) / max;
  const clamped = height < BigInt(0) ? BigInt(0) : height;
  return `${clamped.toString()}%`;
}

function DeskSkeleton() {
  return (
    <div className="tb-fin-desk" aria-busy="true" aria-label="Loading finance">
      <div className="tb-fin-desk__cards">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="tb-fin-skel tb-fin-skel--card" />
        ))}
      </div>
      <div className="tb-fin-skel tb-fin-skel--flow" />
      <div className="tb-fin-skel tb-fin-skel--chart" />
    </div>
  );
}

function MoneyCard({
  label,
  amount,
  currency,
  meta,
  hint,
  tone,
}: {
  label: string;
  amount: string;
  currency: string;
  meta?: string;
  hint?: string;
  tone?: "hold" | "ready" | "paid" | "earn" | "owe";
}) {
  return (
    <article className="tb-fin-card" data-tone={tone}>
      <header className="tb-fin-card__top">
        <p className="tb-fin-card__label">{label}</p>
        {meta ? <span className="tb-fin-card__count">{meta}</span> : null}
      </header>
      <p className="tb-fin-card__amount">{formatMoney(amount, currency)}</p>
      {hint ? <p className="tb-fin-card__hint">{hint}</p> : null}
    </article>
  );
}

function SupplierMark({ name, logo }: { name: string; logo?: string | null }) {
  const src = mediaUrl(logo);
  if (src) {
    return <img className="tb-fin-avatar" src={src} alt="" />;
  }
  return <span className="tb-fin-avatar">{name.slice(0, 2).toUpperCase()}</span>;
}

function statementColumns(entry: SupplierLedgerEntry) {
  const amount = entry.amount;
  const blank = "—";
  if (entry.entry_type === "sale") {
    return { label: "Buyer payment received", gross: amount, commission: blank, credit: blank, payout: blank };
  }
  if (entry.entry_type === "platform_fee") {
    return { label: "TradeBay commission", gross: blank, commission: amount, credit: blank, payout: blank };
  }
  if (entry.entry_type === "funds_released" && entry.direction === "credit") {
    return { label: "Ready to pay supplier", gross: blank, commission: blank, credit: amount, payout: blank };
  }
  if (entry.entry_type === "payout") {
    return { label: "Supplier payout", gross: blank, commission: blank, credit: blank, payout: amount };
  }
  if (entry.entry_type === "adjustment") {
    return { label: "Adjustment", gross: blank, commission: blank, credit: blank, payout: amount };
  }
  return null;
}

function SupplierStatement({
  supplier,
  onClose,
}: {
  supplier: SupplierBalance;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<SupplierLedgerEntry[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const id = supplier.supplier_business_id ?? "";
  const currency = supplier.currency || "USD";

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    void checkoutApi
      .adminSupplierEntries(id, { page, page_size: PAGE_SIZE })
      .then((res) => {
        setRows(res.data);
        setTotal(res.meta.total);
        setError(null);
      })
      .catch((err) => setError(errorText(err, "Finance data couldn't be loaded. Try again.")))
      .finally(() => setLoading(false));
  }, [id, page]);

  const visible = rows.filter((row) => statementColumns(row));

  return (
    <Modal
      open
      onClose={onClose}
      title={supplier.supplier_name || "Supplier"}
      kicker="Supplier statement"
      className="tb-fin-statement"
    >
      <div className="tb-fin-statement-head">
        <SupplierMark name={supplier.supplier_name || "Supplier"} logo={supplier.logo_url} />
        <div>
          <strong>{supplier.supplier_name || "Supplier"}</strong>
          <p>{supplier.verification_status === "verified" ? "Verified supplier" : "Verification pending"}</p>
        </div>
        <dl>
          <div>
            <dt>Current balance</dt>
            <dd>{formatMoney(supplier.balance, currency)}</dd>
          </div>
          <div>
            <dt>Total sales</dt>
            <dd>{formatMoney(supplier.gross_sales, currency)}</dd>
          </div>
          <div>
            <dt>Commission</dt>
            <dd>{formatMoney(supplier.platform_fees, currency)}</dd>
          </div>
          <div>
            <dt>Payouts</dt>
            <dd>{formatMoney(supplier.paid_out, currency)}</dd>
          </div>
        </dl>
      </div>
      {error ? (
        <FeedbackBanner tone="error" title="Statement unavailable" className="mx-5 mb-4">
          {error}
        </FeedbackBanner>
      ) : loading && rows.length === 0 ? (
        <div className="tb-fin-skel tb-fin-skel--table" />
      ) : visible.length === 0 ? (
        <InventoryEmpty title="No supplier statement yet" body="Lines appear after a buyer pays this supplier's order." />
      ) : (
        <>
          <div className="tb-co-scroll">
            <InventoryTable columns={["Date", "Order", "Description", "Gross", "Commission", "Supplier credit", "Payout", "Balance"]}>
              {visible.map((row) => {
                const cols = statementColumns(row)!;
                return (
                  <tr key={row.id}>
                    <td>{formatDateTime(row.created_at)}</td>
                    <td>{row.order_number || "—"}</td>
                    <td>{cols.label}</td>
                    <td className="tb-co-num">{cols.gross === "—" ? "—" : formatMoney(cols.gross, currency)}</td>
                    <td className="tb-co-num">{cols.commission === "—" ? "—" : formatMoney(cols.commission, currency)}</td>
                    <td className="tb-co-num">{cols.credit === "—" ? "—" : formatMoney(cols.credit, currency)}</td>
                    <td className="tb-co-num">{cols.payout === "—" ? "—" : formatMoney(cols.payout, currency)}</td>
                    <td className="tb-co-num">
                      <strong>{formatMoney(row.running_balance, currency)}</strong>
                    </td>
                  </tr>
                );
              })}
            </InventoryTable>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </Modal>
  );
}

function OrderStoryModal({
  orderId,
  onClose,
}: {
  orderId: string | null;
  onClose: () => void;
}) {
  const [story, setStory] = useState<OrderMoneyStory | null>(null);
  const [orderNumber, setOrderNumber] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return;
    setStory(null);
    setError(null);
    void platformMoneyApi
      .orderSummary(orderId)
      .then((res) => {
        setStory(res.story ?? null);
        setOrderNumber(res.order_number ?? null);
      })
      .catch(() => setError("Finance data couldn't be loaded. Try again."));
  }, [orderId]);

  const currency = story?.currency || "USD";
  return (
    <Modal open={Boolean(orderId)} onClose={onClose} title={orderNumber || "Order payment"} kicker="Money trail">
      {error ? <p>{error}</p> : null}
      {!error && !story ? <div className="tb-fin-skel tb-fin-skel--table" /> : null}
      {story ? (
        <ol className="tb-fin-story">
          <li>
            <span>Buyer paid</span>
            <strong>{formatMoney(story.buyer_paid, currency)}</strong>
            <small>
              {paymentMethodLabel(story.payment_method)} · {story.payment_status}
            </small>
          </li>
          <li>
            <span>Currently held</span>
            <strong>{formatMoney(story.held_amount, currency)}</strong>
            <small>{story.hold_reason || "Nothing left in holding"}</small>
          </li>
          <li>
            <span>Released after fulfillment</span>
            <strong>{formatMoney(story.released_amount, currency)}</strong>
          </li>
          <li>
            <span>Supplier share</span>
            <strong>{formatMoney(story.supplier_payable, currency)}</strong>
            <small>
              Gross {formatMoney(story.supplier_gross, currency)} minus commission{" "}
              {formatMoney(story.commission_amount, currency)}
            </small>
          </li>
          <li>
            <span>Paid to supplier</span>
            <strong>{formatMoney(story.paid_to_supplier, currency)}</strong>
            <small>Remaining {formatMoney(story.remaining, currency)}</small>
          </li>
        </ol>
      ) : null}
    </Modal>
  );
}

function MovementChart({
  movement,
  currency,
  range,
  onRange,
}: {
  movement: MoneyMovement | null;
  currency: string;
  range: RangeKey;
  onRange: (range: RangeKey) => void;
}) {
  const max = useMemo(() => {
    let peak = BigInt(0);
    for (const bucket of movement?.buckets ?? []) {
      for (const key of ["buyer_payments", "released", "payouts", "commission"] as const) {
        const value = cents(bucket[key]);
        if (value > peak) peak = value;
      }
    }
    return peak;
  }, [movement]);
  const ranges: { id: RangeKey; label: string }[] = [
    { id: "7d", label: "7 days" },
    { id: "30d", label: "30 days" },
    { id: "90d", label: "90 days" },
    { id: "year", label: "This year" },
  ];

  const buckets = movement?.buckets ?? [];
  const dense = buckets.length > 10;
  const labelStep = buckets.length > 20 ? 5 : buckets.length > 10 ? 3 : 1;

  return (
    <section className="tb-fin-chart">
      <header>
        <h2>Money movement <span>{currency}</span></h2>
        <div className="tb-fin-chart__ranges">
          {ranges.map((item) => (
            <button key={item.id} type="button" data-active={item.id === range || undefined} onClick={() => onRange(item.id)}>
              {item.label}
            </button>
          ))}
        </div>
      </header>
      {buckets.length === 0 || buckets.every((bucket) => cents(bucket.buyer_payments) + cents(bucket.released) + cents(bucket.payouts) + cents(bucket.commission) === BigInt(0)) ? (
        <p className="tb-fin-empty">No money movement in this period.</p>
      ) : (
        <div className="tb-fin-chart__scroll" data-dense={dense || undefined}>
          {buckets.map((bucket, index) => {
            const series = [
              ["pay", bucket.buyer_payments],
              ["released", bucket.released],
              ["payout", bucket.payouts],
              ["fee", bucket.commission],
            ] as const;
            const showLabel = index === 0 || index === buckets.length - 1 || index % labelStep === 0;
            return (
              <div
                key={bucket.label}
                className="tb-fin-chart__col"
                title={`${bucket.label}: payments ${formatMoney(bucket.buyer_payments, currency)}, released ${formatMoney(bucket.released, currency)}, payouts ${formatMoney(bucket.payouts, currency)}, commission ${formatMoney(bucket.commission, currency)}`}
              >
                <div className="tb-fin-chart__bars">
                  {series.map(([id, amount]) =>
                    cents(amount) > BigInt(0) ? (
                      <i key={id} data-series={id} style={{ height: barHeight(amount, max) }} />
                    ) : null,
                  )}
                </div>
                <span>{showLabel ? axisLabel(bucket.label) : ""}</span>
              </div>
            );
          })}
        </div>
      )}
      <ul className="tb-fin-legend">
        <li data-series="pay">Buyer payments</li>
        <li data-series="released">Released</li>
        <li data-series="payout">Supplier payouts</li>
        <li data-series="fee">Commission</li>
      </ul>
    </section>
  );
}

export function AdminMoneyDesk() {
  const router = useRouter();
  const params = useSearchParams();
  const section = (params.get("section") as Section) || "overview";
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("settlements.approve");
  const { success, error: toastError } = useToast();
  const { prompt, dialog } = useConfirm();
  const [overview, setOverview] = useState<PlatformMoneyOverview | null>(null);
  const [balances, setBalances] = useState<SupplierBalance[]>([]);
  const [movement, setMovement] = useState<MoneyMovement | null>(null);
  const [range, setRange] = useState<RangeKey>("30d");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [payments, setPayments] = useState<BuyerPaymentRow[]>([]);
  const [paymentPage, setPaymentPage] = useState(1);
  const [paymentTotal, setPaymentTotal] = useState(0);
  const [paymentsLoading, setPaymentsLoading] = useState(false);
  const [paymentsError, setPaymentsError] = useState<string | null>(null);
  const [paymentsTry, setPaymentsTry] = useState(0);
  const [cashWaiting, setCashWaiting] = useState<Payment[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [storyOrder, setStoryOrder] = useState<string | null>(null);
  const [selected, setSelected] = useState<SupplierBalance | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [ov, bal, move] = await Promise.allSettled([
      platformMoneyApi.overview(),
      checkoutApi.adminBalances(),
      platformMoneyApi.movement(range),
    ]);
    if (ov.status === "fulfilled") {
      setOverview(ov.value);
      setError(null);
    } else {
      setError("Finance data couldn't be loaded. Try again.");
    }
    if (bal.status === "fulfilled") setBalances(bal.value);
    if (move.status === "fulfilled") setMovement(move.value);
    setLoading(false);
  }, [range]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (section !== "payments") return;
    setPaymentsLoading(true);
    setPaymentsError(null);
    void platformMoneyApi
      .listBuyerPayments({ page: paymentPage, page_size: PAGE_SIZE })
      .then((res) => {
        setPayments(Array.isArray(res.data) ? res.data : []);
        setPaymentTotal(res.meta.total);
        setPaymentsError(null);
      })
      .catch(() => setPaymentsError("Buyer payments couldn't be loaded."))
      .finally(() => setPaymentsLoading(false));
    void financeApi.listPayments({ page: 1, page_size: 50 }).then((res) => {
      setCashWaiting(res.data.filter((row) => row.payment_method === "cash" && row.status === "pending"));
    }).catch(() => setCashWaiting([]));
  }, [section, paymentPage, paymentsTry]);

  async function confirmCash(payment: Payment) {
    const note = await prompt({
      title: `Record cash for ${payment.payment_reference}?`,
      body: `Only confirm once ${formatMoney(payment.amount, payment.currency)} in cash has actually been received.`,
      confirmLabel: "Cash received",
      input: { label: "Note (optional)", placeholder: "Who collected it" },
    });
    if (note === null) return;
    setBusy(payment.id);
    try {
      await checkoutApi.confirmCash(payment.id, note);
      success("Cash recorded", "The buyer payment is now in holding.");
      await load();
      setCashWaiting((rows) => rows.filter((row) => row.id !== payment.id));
    } catch (err) {
      toastError("Couldn't record cash", errorText(err, "Try again."));
    } finally {
      setBusy(null);
    }
  }

  const currency = overview?.currency || "USD";
  const needle = query.trim().toLowerCase();
  const filteredBalances = balances.filter((row) =>
    !needle || (row.supplier_name || "").toLowerCase().includes(needle),
  );
  const filteredPayments = payments.filter((row) => {
    if (!needle) return true;
    return [row.payment_reference, row.order_number, row.buyer_name].some((value) =>
      (value || "").toLowerCase().includes(needle),
    );
  });
  const openBalances = balances.filter((row) => cents(row.balance) > BigInt(0)).slice(0, 5);

  function go(next: Section) {
    router.push(next === "overview" ? ROUTES.admin.finance : `${ROUTES.admin.finance}?section=${next}`);
  }

  return (
    <div className="tb-inv-page tb-cc tb-fin-desk">
      {dialog}
      <OrderStoryModal orderId={storyOrder} onClose={() => setStoryOrder(null)} />
      <InventoryPageHeader
        eyebrow="Admin · Finance"
        mark="Platform"
        title="Finance"
        description="Money received, money held, what suppliers are owed, what has been paid, and what TradeBay earned."
        actions={
          <>
            <Link className="tb-btn tb-btn--soft" href={ROUTES.admin.settlements}>
              Supplier payouts
            </Link>
            <BackLink href={ROUTES.admin.home}>Command center</BackLink>
          </>
        }
      />

      <InventoryTabs
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "payments", label: "Buyer payments" },
          { id: "balances", label: "Supplier balances" },
          { id: "earnings", label: "Platform earnings" },
          { id: "activity", label: "Activity" },
        ]}
        value={section}
        onChange={(id) => go(id as Section)}
      />

      {error ? (
        <FeedbackBanner tone="error" title="Finance data couldn't be loaded" onDismiss={() => setError(null)}>
          Try again in a moment.
          <button type="button" className="tb-btn tb-btn--soft mt-3" onClick={() => void load()}>
            Try again
          </button>
        </FeedbackBanner>
      ) : null}

      {loading && !overview ? <DeskSkeleton /> : null}

      {overview && section === "overview" ? (
        <>
          <PlatformStage overview={overview} currency={currency} onBalances={() => go("balances")} onPayments={() => go("payments")} onPayouts={() => router.push(ROUTES.admin.settlements)} onEarnings={() => go("earnings")} />

          <section className="tb-fin-flow" aria-label="Money flow">
            <FlowStep amount={overview.buyer_payments_amount} count={`${overview.buyer_payments_count} payments`} label="Buyer payments" currency={currency} onClick={() => go("payments")} />
            <FlowStep amount={overview.held_amount} count={`${overview.held_orders_count} orders`} label="Currently held" currency={currency} onClick={() => go("payments")} />
            <FlowStep amount={overview.released_amount} count={`${overview.released_orders_count} orders`} label="Released after fulfillment" currency={currency} onClick={() => router.push(ROUTES.admin.settlements)} />
            <FlowStep amount={overview.pending_payouts_net} count={`${overview.pending_payouts_count} payouts`} label="Ready for payout" currency={currency} onClick={() => router.push(ROUTES.admin.settlements)} />
            <FlowStep amount={overview.payouts_completed_amount} count={`${overview.completed_payouts_count} payouts`} label="Paid to suppliers" currency={currency} onClick={() => router.push(ROUTES.admin.settlements)} />
            <article className="tb-fin-flow__earn">
              <strong>{formatMoney(overview.fees_recognized_amount, currency)}</strong>
              <span>{overview.recognized_fees_count} orders</span>
              <button type="button" onClick={() => go("earnings")}>TradeBay commission</button>
            </article>
          </section>

          <div className="tb-fin-split">
            <MovementChart movement={movement} currency={currency} range={range} onRange={setRange} />
            <section className="tb-fin-side">
              <h2>Largest open balances</h2>
              {openBalances.length === 0 ? (
                <p className="tb-fin-empty">No outstanding supplier balances</p>
              ) : (
                <ul>
                  {openBalances.map((row) => (
                    <li key={row.supplier_business_id}>
                      <SupplierMark name={row.supplier_name || "Supplier"} logo={row.logo_url} />
                      <span>{row.supplier_name || "Supplier"}</span>
                      <strong>{formatMoney(row.balance, row.currency || currency)}</strong>
                    </li>
                  ))}
                </ul>
              )}
              <h2>Payment status</h2>
              <ul className="tb-fin-mix">
                <li><span>Paid</span><strong>{overview.buyer_payments_count}</strong></li>
                <li><span>Held</span><strong>{overview.held_orders_count}</strong></li>
                <li><span>Released</span><strong>{overview.released_orders_count}</strong></li>
                <li><span>Pending payout</span><strong>{overview.pending_payouts_count}</strong></li>
                <li><span>Refunded</span><strong>{overview.refunds_count}</strong></li>
              </ul>
            </section>
          </div>
          <ActivityList items={overview.activity} onOpen={setStoryOrder} />
        </>
      ) : null}

      {section === "payments" ? (
        <InventoryPanel flush title="Buyer payments" subtitle={`Each payment TradeBay received, and how it splits. Amounts in ${currency}.`}>
          <div className="tb-fin-tools">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search payment, order, or buyer" aria-label="Search payments" />
          </div>
          {canApprove && cashWaiting.length > 0 ? (
            <div className="tb-fin-cash">
              <p>Cash still waiting to be recorded</p>
              {cashWaiting.map((payment) => (
                <div key={payment.id}>
                  <span>{payment.payment_reference}</span>
                  <strong>{formatMoney(payment.amount, payment.currency)}</strong>
                  <InventoryBtn tone="soft" busy={busy === payment.id} onClick={() => void confirmCash(payment)}>
                    Record cash
                  </InventoryBtn>
                </div>
              ))}
            </div>
          ) : null}
          {paymentsError && payments.length === 0 ? (
            <FeedbackBanner tone="error" title="Buyer payments couldn't be loaded" className="mx-5 mb-4">
              Cash waiting above is still listed. The payment history did not load.
              <button type="button" className="tb-btn tb-btn--soft mt-3" onClick={() => setPaymentsTry((n) => n + 1)}>
                Try again
              </button>
            </FeedbackBanner>
          ) : paymentsLoading && payments.length === 0 ? (
            <div className="tb-fin-skel tb-fin-skel--table" />
          ) : filteredPayments.length === 0 ? (
            <InventoryEmpty title="No buyer payments yet" body="Card payments and recorded cash appear here." />
          ) : (
            <>
              <ul className="tb-pay-list">
                {filteredPayments.map((row) => (
                  <li key={row.id}>
                    <div className="tb-pay-list__who">
                      <strong>{row.payment_reference || "Payment"}</strong>
                      <span>{row.order_number || "Order"}</span>
                      <p>
                        {row.buyer_name || "Buyer"} · {paymentMethodLabel(row.payment_method)} · {formatDateTime(row.paid_at)}
                      </p>
                    </div>
                    <div className="tb-pay-list__money">
                      <strong>{formatMoney(row.amount)}</strong>
                      <span>
                        Commission {formatMoney(row.commission_amount)} · Supplier {formatMoney(row.supplier_amount)}
                      </span>
                    </div>
                    <span className="tb-sup-fin__state" data-state={fundsTone(row.funds_label)}>
                      {row.funds_label}
                    </span>
                    {row.order_id ? (
                      <button type="button" className="tb-co-link" onClick={() => setStoryOrder(row.order_id)}>
                        View
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
              <Pager page={paymentPage} pageSize={PAGE_SIZE} total={paymentTotal} onPage={setPaymentPage} />
            </>
          )}
        </InventoryPanel>
      ) : null}

      {section === "balances" ? (
        <div className="grid gap-4">
          <InventoryPanel flush title="Supplier balances" subtitle="Gross sales, TradeBay commission, what was paid, and what is still owed.">
            <div className="tb-fin-tools">
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search suppliers" aria-label="Search suppliers" />
            </div>
            {filteredBalances.length === 0 ? (
              <InventoryEmpty title="No outstanding supplier balances" body="Balances appear after the first paid order." />
            ) : (
              <div className="tb-co-scroll">
                <InventoryTable columns={["Supplier", "Gross sales", "Commission", "Supplier earnings", "Already paid", "Remaining", ""]}>
                  {filteredBalances.map((row) => {
                    const cur = row.currency || currency;
                    return (
                      <tr key={row.supplier_business_id}>
                        <td>
                          <div className="tb-fin-who">
                            <SupplierMark name={row.supplier_name || "Supplier"} logo={row.logo_url} />
                            <div>
                              <strong>{row.supplier_name || "Supplier"}</strong>
                              <span>{POSITION_LABEL[row.position || ""] || "Open"}</span>
                            </div>
                          </div>
                        </td>
                        <td className="tb-co-num">{formatMoney(row.gross_sales, cur)}</td>
                        <td className="tb-co-num">{formatMoney(row.platform_fees, cur)}</td>
                        <td className="tb-co-num">{formatMoney(row.net_earnings, cur)}</td>
                        <td className="tb-co-num">{formatMoney(row.paid_out, cur)}</td>
                        <td className="tb-co-num"><strong>{formatMoney(row.balance, cur)}</strong></td>
                        <td>
                          <InventoryBtn tone="ghost" onClick={() => setSelected(row)}>
                            View statement
                          </InventoryBtn>
                        </td>
                      </tr>
                    );
                  })}
                </InventoryTable>
              </div>
            )}
          </InventoryPanel>
          {selected ? (
            <SupplierStatement
              key={selected.supplier_business_id}
              supplier={selected}
              onClose={() => setSelected(null)}
            />
          ) : null}
        </div>
      ) : null}

      {overview && section === "earnings" ? (
        <section className="tb-fin-earn">
          <h2>What belongs to TradeBay</h2>
          <p>Buyer payments move through TradeBay. Only the commission is TradeBay revenue.</p>
          <div className="tb-fin-earn__grid">
            <MoneyCard label="Money flowing through" amount={overview.buyer_payments_amount} currency={currency} meta="Buyer payments" hint="Not TradeBay revenue" />
            <MoneyCard label="Refunds and credits" amount={overview.refunds_amount} currency={currency} meta={`${overview.refunds_count} refunds`} hint="Returned to buyers" />
            <MoneyCard label="Still owed to suppliers" amount={overview.outstanding_amount} currency={currency} meta="Supplier obligations" hint="Held and ready to pay" tone="owe" />
            <MoneyCard label="Already paid to suppliers" amount={overview.payouts_completed_amount} currency={currency} meta="Supplier money sent" hint="Completed payouts" tone="paid" />
            <MoneyCard label="TradeBay commission" amount={overview.fees_recognized_amount} currency={currency} meta={overview.commission_rate ? formatRate(overview.commission_rate) || "" : "Recognized"} hint="Platform earnings" tone="earn" />
          </div>
        </section>
      ) : null}

      {overview && section === "activity" ? <FinancialActivity overview={overview} /> : null}
    </div>
  );
}

function PlatformStage({
  overview,
  currency,
  onBalances,
  onPayments,
  onPayouts,
  onEarnings,
}: {
  overview: PlatformMoneyOverview;
  currency: string;
  onBalances: () => void;
  onPayments: () => void;
  onPayouts: () => void;
  onEarnings: () => void;
}) {
  const pool = sumMoney([overview.held_amount, overview.pending_payouts_net, overview.payouts_completed_amount]);
  return (
    <section className="tb-fin-stage">
      <button type="button" className="tb-fin-stage__owed" onClick={onBalances}>
        <span>Outstanding to suppliers</span>
        <strong>{formatMoney(overview.outstanding_amount, currency)}</strong>
        <em>
          {overview.outstanding_suppliers_count} supplier{overview.outstanding_suppliers_count === 1 ? "" : "s"} · open balances
        </em>
      </button>
      <ul className="tb-fin-stage__facts">
        <li>
          <button type="button" onClick={onPayments}>
            <span>Money received</span>
            <strong>{formatMoney(overview.buyer_payments_amount, currency)}</strong>
            <em>{overview.buyer_payments_count} payments</em>
          </button>
        </li>
        <li>
          <button type="button" onClick={onPayments}>
            <span>Currently held</span>
            <strong>{formatMoney(overview.held_amount, currency)}</strong>
            <em>{overview.held_orders_count} orders</em>
          </button>
        </li>
        <li>
          <button type="button" onClick={onPayouts}>
            <span>Paid to suppliers</span>
            <strong>{formatMoney(overview.payouts_completed_amount, currency)}</strong>
            <em>{overview.completed_payouts_count} payouts</em>
          </button>
        </li>
        <li>
          <button type="button" onClick={onEarnings}>
            <span>TradeBay earnings</span>
            <strong>{formatMoney(overview.fees_recognized_amount, currency)}</strong>
            <em>{overview.commission_rate ? formatRate(overview.commission_rate) : `${overview.recognized_fees_count} orders`}</em>
          </button>
        </li>
      </ul>
      <div className="tb-fin-stage__bar" role="img" aria-label="Supplier money split into held, ready, and paid">
        <i data-state="held" style={{ width: shareWidth(overview.held_amount, pool) }} />
        <i data-state="ready" style={{ width: shareWidth(overview.pending_payouts_net, pool) }} />
        <i data-state="paid" style={{ width: shareWidth(overview.payouts_completed_amount, pool) }} />
      </div>
      <ul className="tb-fin-stage__legend">
        <li data-state="held"><span>Held</span><strong>{formatMoney(overview.held_amount, currency)}</strong></li>
        <li data-state="ready"><span>Ready</span><strong>{formatMoney(overview.pending_payouts_net, currency)}</strong></li>
        <li data-state="paid"><span>Paid</span><strong>{formatMoney(overview.payouts_completed_amount, currency)}</strong></li>
      </ul>
    </section>
  );
}

function FlowStep({
  amount,
  count,
  label,
  currency,
  onClick,
}: {
  amount: string;
  count: string;
  label: string;
  currency: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className="tb-fin-flow__step" onClick={onClick}>
      <strong>{formatMoney(amount, currency)}</strong>
      <span>{count}</span>
      <em>{label}</em>
    </button>
  );
}

function ActivityList({ items, onOpen }: { items: FinanceActivity[]; onOpen: (orderId: string) => void }) {
  if (items.length === 0) return <p className="tb-fin-empty">No financial activity yet.</p>;
  return (
    <section className="tb-fin-activity">
      <h2>Recent activity</h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <time>{formatDateTime(item.posted_at)}</time>
            {item.order_id ? (
              <button type="button" onClick={() => onOpen(item.order_id!)}>{item.message}</button>
            ) : (
              <span>{item.message}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function PayoutMenu({
  open,
  onOpen,
  onClose,
  onStatement,
  onPayout,
  canPayout,
  payoutBusy,
  dropUp,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onStatement: () => void;
  onPayout: () => void;
  canPayout: boolean;
  payoutBusy: boolean;
  dropUp?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) onClose();
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open, onClose]);

  return (
    <div className="tb-fin-more" ref={ref}>
      <button type="button" className="tb-fin-more__btn" aria-label="Actions" aria-expanded={open} onClick={() => (open ? onClose() : onOpen())}>
        <span />
        <span />
        <span />
      </button>
      {open ? (
        <div className="tb-fin-more__menu" role="menu" data-place={dropUp ? "up" : "down"}>
          <button type="button" role="menuitem" onClick={onStatement}>
            View statement
          </button>
          {canPayout ? (
            <button type="button" role="menuitem" disabled={payoutBusy} onClick={onPayout}>
              {payoutBusy ? "Recording…" : "Record payout"}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function AdminPayoutDesk() {
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("settlements.approve");
  const { success, error: toastError } = useToast();
  const { confirm, dialog } = useConfirm();
  const [overview, setOverview] = useState<PlatformMoneyOverview | null>(null);
  const [balances, setBalances] = useState<SupplierBalance[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<SupplierBalance | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, bal] = await Promise.all([platformMoneyApi.overview(), checkoutApi.adminBalances()]);
      setOverview(ov);
      setBalances(bal);
      setError(null);
    } catch {
      setError("Finance data couldn't be loaded. Try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function recordPayout(row: SupplierBalance) {
    const id = row.pending_payout_id;
    if (!id) return;
    const name = row.supplier_name || "this supplier";
    const ok = await confirm({
      title: `Record payout to ${name}?`,
      body: `This marks ${formatMoney(row.available_balance, row.currency || "USD")} as sent to ${name}. The remaining balance updates after it is recorded.`,
      confirmLabel: "Record payout",
    });
    if (!ok) return;
    setBusy(id);
    void platformMoneyApi
      .processPayout(id)
      .then(() => {
        success("Payout recorded", `${name} has been marked paid.`);
        return load();
      })
      .catch((err) => toastError("Couldn't record payout", errorText(err, "Try again.")))
      .finally(() => setBusy(null));
  }

  const currency = overview?.currency || "USD";
  const needle = query.trim().toLowerCase();
  const rows = balances.filter((row) => !needle || (row.supplier_name || "").toLowerCase().includes(needle));

  return (
    <div className="tb-inv-page tb-cc tb-fin-desk">
      {dialog}
      <InventoryPageHeader
        eyebrow="Admin · Finance"
        mark="Platform"
        title="Supplier payouts"
        description="Who to pay, how much is ready, and what has already been sent."
        actions={<BackLink href={ROUTES.admin.finance}>Finance overview</BackLink>}
      />
      {error ? (
        <FeedbackBanner tone="error" title="Finance data couldn't be loaded">
          Try again.
          <button type="button" className="tb-btn tb-btn--soft mt-3" onClick={() => void load()}>
            Try again
          </button>
        </FeedbackBanner>
      ) : null}
      {loading && !overview ? <DeskSkeleton /> : null}
      {overview ? (
        <div className="tb-fin-desk__cards tb-fin-desk__cards--payouts">
          <MoneyCard label="Ready to pay" amount={overview.ready_payouts_net} currency={currency} meta={`${overview.ready_payouts_count}`} tone="ready" />
          <MoneyCard label="Paid this month" amount={overview.paid_this_month_amount} currency={currency} tone="paid" />
          <MoneyCard label="Total paid" amount={overview.payouts_completed_amount} currency={currency} meta={`${overview.completed_payouts_count}`} tone="paid" />
          <MoneyCard label="Still owed" amount={overview.outstanding_amount} currency={currency} meta={`${overview.outstanding_suppliers_count} suppliers`} tone="owe" />
        </div>
      ) : null}
      <InventoryPanel flush title="Who to pay" subtitle={`Amounts in ${currency}. Remaining is what TradeBay still owes after commission and payouts.`}>
        <div className="tb-fin-tools">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search suppliers" aria-label="Search suppliers" />
        </div>
        {!loading && rows.length === 0 ? (
          <InventoryEmpty title="No supplier payouts are ready" body="Payouts appear after an order is fulfilled and funds are released." />
        ) : (
          <div className="tb-fin-payouts">
            <table className="tb-inv-table">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th className="tb-num">Orders</th>
                  <th className="tb-num">Gross</th>
                  <th className="tb-num">Commission</th>
                  <th className="tb-num">Payable</th>
                  <th className="tb-num">Paid</th>
                  <th className="tb-num">Remaining</th>
                  <th>Status</th>
                  <th className="tb-act"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.supplier_business_id}>
                    <td>
                      <div className="tb-fin-who">
                        <SupplierMark name={row.supplier_name || "Supplier"} logo={row.logo_url} />
                        <strong>{row.supplier_name || "Supplier"}</strong>
                      </div>
                    </td>
                    <td className="tb-num">{row.orders_count ?? 0}</td>
                    <td className="tb-num">{formatMoney(row.gross_sales)}</td>
                    <td className="tb-num">{formatMoney(row.platform_fees)}</td>
                    <td className="tb-num">{formatMoney(row.net_earnings)}</td>
                    <td className="tb-num">{formatMoney(row.paid_out)}</td>
                    <td className="tb-num"><strong>{formatMoney(row.balance)}</strong></td>
                    <td>
                      <StatusBadge
                        status={row.position || "open"}
                        label={POSITION_LABEL[row.position || ""] || "Open"}
                        tone={POSITION_TONE[row.position || ""] || "off"}
                      />
                    </td>
                    <td className="tb-act">
                      <PayoutMenu
                        open={menuId === row.supplier_business_id}
                        onOpen={() => setMenuId(row.supplier_business_id ?? null)}
                        onClose={() => setMenuId(null)}
                        onStatement={() => {
                          setMenuId(null);
                          setSelected(row);
                        }}
                        canPayout={canApprove && Boolean(row.pending_payout_id)}
                        payoutBusy={busy === row.pending_payout_id}
                        dropUp={index === rows.length - 1}
                        onPayout={() => {
                          setMenuId(null);
                          recordPayout(row);
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </InventoryPanel>
      {selected ? (
        <SupplierStatement
          key={selected.supplier_business_id}
          supplier={selected}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}
