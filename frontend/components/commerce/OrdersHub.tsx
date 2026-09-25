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
import { checkoutApi, type Checkout } from "@/lib/api/checkoutApi";
import { procurementApi, type PurchaseOrderSummary } from "@/lib/api/procurementApi";
import { checkoutView, errorText, formatDate, formatMoney, paymentMethodLabel } from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useState } from "react";

const PAGE_SIZE = 20;

const ORDER_FILTERS = [
  { id: "", label: "All" },
  { id: "pending", label: "New" },
  { id: "confirmed", label: "Confirmed" },
  { id: "shipped", label: "Shipped" },
  { id: "delivered", label: "Delivered" },
  { id: "completed", label: "Completed" },
  { id: "cancelled", label: "Cancelled" },
];

function CheckoutsTable() {
  const [rows, setRows] = useState<Checkout[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    void checkoutApi
      .list({ page, page_size: PAGE_SIZE })
      .then((res) => {
        setRows(res.data);
        setTotal(res.meta.total);
        setError(null);
      })
      .catch((err) => setError(errorText(err, "Couldn't load your checkouts")))
      .finally(() => setLoading(false));
  }, [page]);

  if (error) return <FeedbackBanner tone="error" title="Checkouts unavailable">{error}</FeedbackBanner>;

  return (
    <InventoryPanel flush title="Your checkouts" subtitle="Each checkout can include orders from several suppliers.">
      {loading && rows.length === 0 ? (
        <LoadingEntity entity="checkouts" className="px-5 py-4" />
      ) : rows.length === 0 ? (
        <InventoryEmpty
          title="No checkouts yet"
          body="Add products to your cart and check out. Your purchases will show up here."
          action={<InventoryLinkBtn href={ROUTES.inventoryProducts}>Browse products</InventoryLinkBtn>}
        />
      ) : (
        <>
          <div className="tb-co-scroll">
            <InventoryTable columns={["Checkout", "Placed", "Suppliers", "Payment", "Total", "Status"]}>
              {rows.map((c) => {
                const view = checkoutView(c.status, c.payment_method);
                return (
                  <tr key={c.id}>
                    <td>
                      <Link className="tb-co-link" href={ROUTES.checkoutDetail(c.id)}>
                        {c.checkout_number}
                      </Link>
                    </td>
                    <td>{formatDate(c.created_at)}</td>
                    <td>{c.orders.map((o) => o.supplier_name).join(", ")}</td>
                    <td>{paymentMethodLabel(c.payment_method)}</td>
                    <td className="tb-co-num">{formatMoney(c.total, c.currency)}</td>
                    <td>
                      <StatusBadge status={c.status} label={view.label} tone={view.tone} />
                    </td>
                  </tr>
                );
              })}
            </InventoryTable>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </InventoryPanel>
  );
}

export function OrdersTable({ perspective }: { perspective: "buyer" | "supplier" | "platform" }) {
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<PurchaseOrderSummary[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    void procurementApi
      .listOrders({ page, page_size: PAGE_SIZE, status: status || undefined })
      .then((res) => {
        setRows(res.data);
        setTotal(res.meta.total);
        setError(null);
      })
      .catch((err) => setError(errorText(err, "Couldn't load orders")))
      .finally(() => setLoading(false));
  }, [page, status]);

  const peerLabel = perspective === "supplier" ? "Buyer" : "Supplier";
  const columns =
    perspective === "platform"
      ? ["Order", "Buyer", "Supplier", "Placed", "Payment", "Total", "Status"]
      : ["Order", peerLabel, "Placed", "Payment", "Total", "Status"];

  return (
    <InventoryPanel
      flush
      title={perspective === "supplier" ? "Orders received" : "Supplier orders"}
      subtitle={
        perspective === "supplier"
          ? "Confirm new orders, then ship them from the order page."
          : "One order per supplier. Each moves forward on its own."
      }
      action={
        <InventoryTabs
          tabs={ORDER_FILTERS}
          value={status}
          onChange={(id) => {
            setStatus(id);
            setPage(1);
          }}
        />
      }
    >
      {error ? (
        <FeedbackBanner tone="error" title="Orders unavailable" className="mx-5 mb-4">
          {error}
        </FeedbackBanner>
      ) : loading && rows.length === 0 ? (
        <LoadingEntity entity="orders" className="px-5 py-4" />
      ) : rows.length === 0 ? (
        <InventoryEmpty
          title={status ? "Nothing here" : "No orders yet"}
          body={
            perspective === "supplier"
              ? "When a buyer checks out with your products, the order appears here."
              : "Orders appear here after checkout or when you accept a quote."
          }
        />
      ) : (
        <>
          <div className="tb-co-scroll">
            <InventoryTable columns={columns}>
              {rows.map((o) => (
                <tr key={o.id}>
                  <td>
                    <Link className="tb-co-link" href={ROUTES.procurementOrder(o.id)}>
                      {o.order_number}
                    </Link>
                    {o.checkout_number && perspective !== "supplier" ? (
                      <span className="tb-inv-entity-sub">{o.checkout_number}</span>
                    ) : null}
                  </td>
                  {perspective === "platform" ? (
                    <>
                      <td>{o.buyer_name || "—"}</td>
                      <td>{o.supplier_name || "—"}</td>
                    </>
                  ) : (
                    <td>{(perspective === "supplier" ? o.buyer_name : o.supplier_name) || "—"}</td>
                  )}
                  <td>{formatDate(o.created_at)}</td>
                  <td>{o.payment_method ? paymentMethodLabel(o.payment_method) : o.source === "checkout" ? "—" : "Per quote"}</td>
                  <td className="tb-co-num">{formatMoney(o.total, o.currency)}</td>
                  <td>
                    <StatusBadge status={o.status} label={o.status === "pending" && perspective === "supplier" ? "New" : undefined} />
                  </td>
                </tr>
              ))}
            </InventoryTable>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </InventoryPanel>
  );
}

export function OrdersHub() {
  const { business } = useAuth();
  const type = business?.type;
  const [tab, setTab] = useState("checkouts");

  if (type === "supplier") {
    return (
      <div className="tb-inv-page tb-co-page">
        <InventoryPageHeader
          eyebrow="Orders"
          mark="Sales"
          title="Orders"
          description="Orders placed with your company. Confirm, ship and track each one."
          actions={
            <>
              <InventoryLinkBtn href={ROUTES.tracking} tone="soft">
                Tracking
              </InventoryLinkBtn>
              <InventoryLinkBtn href={ROUTES.finance} tone="ghost">
                Balance &amp; invoices
              </InventoryLinkBtn>
            </>
          }
        />
        <OrdersTable perspective="supplier" />
      </div>
    );
  }

  if (type === "platform") {
    return (
      <div className="tb-inv-page tb-co-page">
        <InventoryPageHeader eyebrow="Orders" mark="Platform" title="Orders" description="Every supplier order on TradeBay." />
        <OrdersTable perspective="platform" />
      </div>
    );
  }

  return (
    <div className="tb-inv-page tb-co-page">
      <InventoryPageHeader
        eyebrow="Orders"
        mark="Purchases"
        title="Orders"
        description="Your checkouts and the orders each supplier is fulfilling."
        actions={
          <>
            <InventoryLinkBtn href={ROUTES.tracking} tone="soft">
              Track orders
            </InventoryLinkBtn>
            <InventoryLinkBtn href={ROUTES.finance} tone="ghost">
              Invoices
            </InventoryLinkBtn>
          </>
        }
      />
      <InventoryTabs
        tabs={[
          { id: "checkouts", label: "Checkouts" },
          { id: "orders", label: "Supplier orders" },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "checkouts" ? <CheckoutsTable /> : <OrdersTable perspective="buyer" />}
    </div>
  );
}
