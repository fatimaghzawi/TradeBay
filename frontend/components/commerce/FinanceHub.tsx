"use client";

import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventoryTable,
  InventoryTabs,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { Pager } from "@/components/commerce/CommerceUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { checkoutApi, type SupplierBalance, type SupplierLedgerEntry } from "@/lib/api/checkoutApi";
import { financeApi, type Invoice, type Payment } from "@/lib/api/financeApi";
import {
  LEDGER_ENTRY_LABEL,
  errorText,
  formatDate,
  formatMoney,
  formatRate,
  paymentMethodLabel,
  paymentView,
} from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

const PAGE_SIZE = 20;

function usePaged<T>(fetcher: (page: number) => Promise<{ data: T[]; meta: { total: number } }>, deps: unknown[] = []) {
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    void fetcher(page)
      .then((res) => {
        setRows(res.data);
        setTotal(res.meta.total);
        setError(null);
      })
      .catch((err) => setError(errorText(err, "Couldn't load this list")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, ...deps]);

  return { page, setPage, rows, total, loading, error };
}

export function InvoicesPanel({ perspective }: { perspective: "buyer" | "supplier" | "platform" }) {
  const list = usePaged((page) => financeApi.listInvoices({ page, page_size: PAGE_SIZE }));
  const columns =
    perspective === "platform"
      ? ["Invoice", "Buyer", "Supplier", "Order", "Date", "Total", "Status"]
      : ["Invoice", perspective === "buyer" ? "Supplier" : "Buyer", "Order", "Date", "Total", "Status"];

  return (
    <InventoryPanel
      flush
      title="Invoices"
      subtitle={
        perspective === "buyer"
          ? "One invoice for each supplier on your order."
          : perspective === "supplier"
            ? "Paid here means the buyer paid TradeBay. It is not a payout to you."
            : undefined
      }
    >
      {list.error ? (
        <FeedbackBanner tone="error" title="Invoices unavailable" className="mx-5 mb-4">
          {list.error}
        </FeedbackBanner>
      ) : list.loading && list.rows.length === 0 ? (
        <LoadingEntity entity="invoices" className="px-5 py-4" />
      ) : list.rows.length === 0 ? (
        <InventoryEmpty
          title="No invoices yet"
          body={
            perspective === "supplier"
              ? "An invoice is created for every order a buyer places with you."
              : "Invoices appear here after you place an order."
          }
        />
      ) : (
        <>
          <div className="tb-co-scroll">
            <InventoryTable columns={columns}>
              {list.rows.map((inv: Invoice) => (
                <tr key={inv.id}>
                  <td>
                    <Link className="tb-co-link" href={ROUTES.financeInvoice(inv.id)}>
                      {inv.invoice_number}
                    </Link>
                  </td>
                  {perspective === "platform" ? (
                    <>
                      <td>{inv.buyer_name || "—"}</td>
                      <td>{inv.supplier_name || "—"}</td>
                    </>
                  ) : (
                    <td>{(perspective === "buyer" ? inv.supplier_name : inv.buyer_name) || "—"}</td>
                  )}
                  <td>
                    {inv.order_id ? (
                      <Link className="tb-co-link" href={ROUTES.procurementOrder(inv.order_id)}>
                        {inv.order_number || "Order"}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{formatDate(inv.issued_at || inv.created_at)}</td>
                  <td className="tb-co-num">{formatMoney(inv.total, inv.currency)}</td>
                  <td>
                    <StatusBadge status={inv.status} />
                  </td>
                </tr>
              ))}
            </InventoryTable>
          </div>
          <Pager page={list.page} pageSize={PAGE_SIZE} total={list.total} onPage={list.setPage} />
        </>
      )}
    </InventoryPanel>
  );
}

export function PaymentsPanel({
  perspective,
  renderAction,
  refreshKey = 0,
}: {
  perspective: "buyer" | "supplier" | "platform";
  renderAction?: (payment: Payment) => ReactNode;
  refreshKey?: number;
}) {
  const list = usePaged((page) => financeApi.listPayments({ page, page_size: PAGE_SIZE }), [refreshKey]);
  const columns = ["Reference", "Date", "Method", "Amount", "Status"];
  if (renderAction) columns.push("");

  return (
    <InventoryPanel
      flush
      title="Payments"
      subtitle={
        perspective === "supplier"
          ? "Buyer payments collected by TradeBay. Your own payout is listed in balance activity."
          : undefined
      }
    >
      {list.error ? (
        <FeedbackBanner tone="error" title="Payments unavailable" className="mx-5 mb-4">
          {list.error}
        </FeedbackBanner>
      ) : list.loading && list.rows.length === 0 ? (
        <LoadingEntity entity="payments" className="px-5 py-4" />
      ) : list.rows.length === 0 ? (
        <InventoryEmpty title="No payments yet" body="Card payments and recorded cash payments appear here." />
      ) : (
        <>
          <div className="tb-co-scroll">
            <InventoryTable columns={columns}>
              {list.rows.map((p) => {
                const view = paymentView(p.payment_method, p.status);
                return (
                  <tr key={p.id}>
                    <td>
                      {p.checkout_id && perspective !== "supplier" ? (
                        <Link className="tb-co-link" href={ROUTES.checkoutDetail(p.checkout_id)}>
                          {p.payment_reference}
                        </Link>
                      ) : (
                        <strong>{p.payment_reference}</strong>
                      )}
                      {p.receipt_number ? <span className="tb-inv-entity-sub">Receipt {p.receipt_number}</span> : null}
                    </td>
                    <td>{formatDate(p.paid_at || p.created_at)}</td>
                    <td>{paymentMethodLabel(p.payment_method)}</td>
                    <td className="tb-co-num">{formatMoney(p.amount, p.currency)}</td>
                    <td>
                      <StatusBadge status={p.status} label={view.label} tone={view.tone} />
                    </td>
                    {renderAction ? <td className="text-right">{renderAction(p)}</td> : null}
                  </tr>
                );
              })}
            </InventoryTable>
          </div>
          <Pager page={list.page} pageSize={PAGE_SIZE} total={list.total} onPage={list.setPage} />
        </>
      )}
    </InventoryPanel>
  );
}

function moneyPlace(entry: SupplierLedgerEntry): { label: string; tone: "ok" | "wait" } {
  if (entry.entry_type === "payout") return { label: "Sent to you", tone: "ok" };
  if (entry.bucket === "available") return { label: "Ready for payout", tone: "ok" };
  return { label: "Held until delivery", tone: "wait" };
}

export function LedgerTable({ entries, currency }: { entries: SupplierLedgerEntry[]; currency: string }) {
  return (
    <ul className="tb-fin-feed">
      {entries.map((e) => {
        const credit = e.direction === "credit";
        const place = moneyPlace(e);
        return (
          <li key={e.id} data-tone={place.tone}>
            <span className="tb-fin-feed__mark" data-direction={e.direction} aria-hidden>
              {credit ? "+" : "−"}
            </span>
            <div className="tb-fin-feed__copy">
              <strong>{LEDGER_ENTRY_LABEL[e.entry_type] ?? e.entry_type.replaceAll("_", " ")}</strong>
              <span>
                {formatDate(e.created_at)}
                {e.order_id ? (
                  <>
                    {" · "}
                    <Link className="tb-co-link" href={ROUTES.procurementOrder(e.order_id)}>
                      {e.order_number || "Order"}
                    </Link>
                  </>
                ) : null}
                {e.entry_type === "platform_fee" && e.commission_rate ? ` · ${formatRate(e.commission_rate)}` : ""}
              </span>
            </div>
            <em className="tb-fin-feed__amount" data-direction={e.direction}>
              {credit ? "+" : "−"}
              {formatMoney(e.amount, e.currency || currency)}
            </em>
            <StatusBadge status={e.bucket} label={place.label} tone={place.tone} />
          </li>
        );
      })}
    </ul>
  );
}

export function BalanceKpis({ balance }: { balance: SupplierBalance | null }) {
  const cur = balance?.currency || "USD";
  const steps = [
    {
      n: "1",
      label: "Buyer paid TradeBay",
      value: balance ? formatMoney(balance.gross_sales, cur) : "—",
      hint: balance ? `Fee ${formatMoney(balance.platform_fees, cur)}` : "Collected by the platform",
    },
    {
      n: "2",
      label: "Held until delivery",
      value: balance ? formatMoney(balance.pending_balance, cur) : "—",
      hint: "Released when the buyer confirms",
    },
    {
      n: "3",
      label: "Ready to pay you",
      value: balance ? formatMoney(balance.available_balance, cur) : "—",
      hint: balance ? `${formatMoney(balance.paid_out, cur)} already sent` : "After delivery",
    },
  ];
  return (
    <ol className="tb-fin-flow">
      {steps.map((step) => (
        <li key={step.n}>
          <span>{step.n}</span>
          <div>
            <p>{step.label}</p>
            <strong>{step.value}</strong>
            <em>{step.hint}</em>
          </div>
        </li>
      ))}
    </ol>
  );
}

function SupplierFinance() {
  const [tab, setTab] = useState("activity");
  const [balance, setBalance] = useState<SupplierBalance | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const ledger = usePaged((page) => checkoutApi.supplierEntries({ page, page_size: PAGE_SIZE }));

  useEffect(() => {
    void checkoutApi
      .supplierBalance()
      .then(setBalance)
      .catch((err) => setBalanceError(errorText(err, "Couldn't load your balance")));
  }, []);

  const cur = balance?.currency || "USD";

  return (
    <div className="tb-inv-page tb-co-page">
      <InventoryPageHeader
        eyebrow="Finance"
        mark="Balance"
        title="Your earnings"
        description="Buyers pay TradeBay. Your share stays held until delivery, then TradeBay can pay you."
        actions={
          <InventoryLinkBtn href={ROUTES.orders} tone="ghost">
            Orders
          </InventoryLinkBtn>
        }
      />
      {balanceError ? (
        <FeedbackBanner tone="error" title="Balance unavailable">
          {balanceError}
        </FeedbackBanner>
      ) : null}
      <BalanceKpis balance={balance} />

      <InventoryTabs
        tabs={[
          { id: "activity", label: "Your money" },
          { id: "invoices", label: "Invoices" },
          { id: "payments", label: "Payments" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "activity" ? (
        <InventoryPanel flush title="What happened to your money" subtitle="Each row is one step: the buyer paid, the fee, or a payout to you.">
          {ledger.error ? (
            <FeedbackBanner tone="error" title="Activity unavailable" className="mx-5 mb-4">
              {ledger.error}
            </FeedbackBanner>
          ) : ledger.loading && ledger.rows.length === 0 ? (
            <LoadingEntity entity="balance activity" className="px-5 py-4" />
          ) : ledger.rows.length === 0 ? (
            <InventoryEmpty title="No earnings yet" body="When a buyer pays TradeBay for one of your orders, your share shows up here as held until delivery." />
          ) : (
            <>
              <LedgerTable entries={ledger.rows} currency={cur} />
              <Pager page={ledger.page} pageSize={PAGE_SIZE} total={ledger.total} onPage={ledger.setPage} />
            </>
          )}
        </InventoryPanel>
      ) : null}
      {tab === "invoices" ? <InvoicesPanel perspective="supplier" /> : null}
      {tab === "payments" ? <PaymentsPanel perspective="supplier" /> : null}
    </div>
  );
}

function BuyerFinance() {
  const [tab, setTab] = useState("invoices");
  return (
    <div className="tb-inv-page tb-co-page">
      <InventoryPageHeader
        eyebrow="Finance"
        mark="Billing"
        title="Invoices & payments"
        description="Invoices from each supplier and the payments you've made."
        actions={
          <InventoryLinkBtn href={ROUTES.orders} tone="ghost">
            Orders
          </InventoryLinkBtn>
        }
      />
      <InventoryTabs
        tabs={[
          { id: "invoices", label: "Invoices" },
          { id: "payments", label: "Payments" },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "invoices" ? <InvoicesPanel perspective="buyer" /> : <PaymentsPanel perspective="buyer" />}
    </div>
  );
}

export function FinanceHub() {
  const { business } = useAuth();
  if (business?.type === "supplier") return <SupplierFinance />;
  if (business?.type === "platform") {
    return (
      <div className="tb-inv-page tb-co-page">
        <InventoryPageHeader eyebrow="Finance" mark="Platform" title="Finance" />
        <InventoryPanel>
          <InventoryEmpty
            title="Platform finance lives in the admin console"
            body="Payments, invoices, commission and supplier balances for all companies."
            action={<InventoryLinkBtn href={ROUTES.admin.finance}>Open finance desk</InventoryLinkBtn>}
          />
        </InventoryPanel>
      </div>
    );
  }
  return <BuyerFinance />;
}
