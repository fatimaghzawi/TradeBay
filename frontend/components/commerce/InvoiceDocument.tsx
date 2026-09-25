"use client";

import { StatusBadge } from "@/components/catalog/InventoryUi";
import { DocLogo, PartyBlock } from "@/components/procurement/OrderWorkspace";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { financeApi, type Invoice } from "@/lib/api/financeApi";
import { procurementApi, type PurchaseOrder } from "@/lib/api/procurementApi";
import {
  errorText,
  formatDate,
  formatDateTime,
  formatMoney,
  formatRate,
  isPositive,
  paymentMethodLabel,
  paymentView,
} from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

export function InvoiceDocument({ invoiceId }: { invoiceId: string }) {
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void financeApi
      .getInvoice(invoiceId)
      .then((inv) => {
        setInvoice(inv);
        setError(null);
        if (inv.order_id) {
          void procurementApi
            .getOrder(inv.order_id)
            .then(setOrder)
            .catch(() => setOrder(null));
        }
      })
      .catch((err) => setError(errorText(err, "Couldn't load this invoice")));
  }, [invoiceId]);

  if (!invoice && !error) return <LoadingEntity entity="invoice" className="py-8" />;
  if (!invoice) {
    return (
      <div className="tb-docs">
        <FeedbackBanner tone="error" title="Invoice unavailable">
          {error}
        </FeedbackBanner>
        <nav className="tb-docs__toolbar-nav">
          <BackLink href={ROUTES.finance}>Invoices</BackLink>
        </nav>
      </div>
    );
  }

  const cur = invoice.currency;
  const supplierName = invoice.supplier_name || order?.supplier_name || "Supplier";
  const buyerName = invoice.buyer_name || order?.buyer_name || "Buyer";
  const pay = invoice.payment;
  const payBadge = paymentView(pay?.method, pay?.status);
  const taxLabel = `${invoice.tax_name || "Tax"}${invoice.tax_rate ? ` (${formatRate(invoice.tax_rate)})` : ""}`;

  return (
    <div className="tb-docs tb-doc--po">
      <div className="tb-docs__toolbar">
        <nav className="tb-docs__toolbar-nav">
          <BackLink href={ROUTES.finance}>Invoices</BackLink>
          {invoice.order_id ? (
            <Link href={ROUTES.procurementOrder(invoice.order_id)}>Order {invoice.order_number}</Link>
          ) : null}
          {invoice.checkout_id ? <Link href={ROUTES.checkoutDetail(invoice.checkout_id)}>Checkout</Link> : null}
        </nav>
        <div className="tb-docs__actions">
          <button type="button" className="tb-btn tb-btn--secondary" onClick={() => window.print()}>
            Print
          </button>
        </div>
      </div>

      <article className="tb-doc-paper--po tb-doc-paper--po-wide">
        <header className="tb-doc-band">
          <div className="tb-doc-band__brand">
            <DocLogo name={supplierName} logoUrl={order?.supplier_logo_url} />
            <div>
              <h1>{supplierName}</h1>
              <p>
                {[order?.supplier_contact_email, order?.supplier_contact_phone].filter(Boolean).join(" · ") ||
                  "Invoice issued through TradeBay"}
              </p>
            </div>
          </div>
          <div className="tb-doc-meta">
            <div className="tb-doc-meta__title">INVOICE</div>
            <strong>{invoice.invoice_number}</strong>
            <div>Date · {formatDate(invoice.issued_at || invoice.created_at)}</div>
            {invoice.order_number ? <div>Order · {invoice.order_number}</div> : null}
            <div className="mt-1.5">
              <StatusBadge status={invoice.status} />
            </div>
          </div>
        </header>

        <div className="tb-doc-body">
          <div className="tb-doc-parties">
            <PartyBlock
              label="From"
              name={supplierName}
              legalName={order?.supplier_legal_name}
              logoUrl={order?.supplier_logo_url}
              address={order?.supplier_address}
              email={order?.supplier_contact_email}
              phone={order?.supplier_contact_phone}
              taxNumber={order?.supplier_tax_number}
            />
            <PartyBlock
              label="Bill to"
              name={buyerName}
              legalName={order?.buyer_legal_name}
              logoUrl={order?.buyer_logo_url}
              address={order?.buyer_address}
              email={order?.buyer_contact_email}
              phone={order?.buyer_contact_phone}
              taxNumber={order?.buyer_tax_number}
            />
            <div className="tb-doc-party">
              <p className="tb-doc-party__label">Payment</p>
              <p className="tb-doc-party__ship">
                <StatusBadge status={pay?.status} label={payBadge.label} tone={payBadge.tone} />
              </p>
            </div>
          </div>

          <dl className="tb-doc-terms">
            <div>
              <dt>Currency</dt>
              <dd>{cur}</dd>
            </div>
            <div>
              <dt>Payment method</dt>
              <dd>{paymentMethodLabel(pay?.method ?? order?.payment_method)}</dd>
            </div>
            <div>
              <dt>Payment reference</dt>
              <dd>{pay?.payment_reference || "—"}</dd>
            </div>
            <div>
              <dt>Receipt</dt>
              <dd>{pay?.receipt_number || "—"}</dd>
            </div>
            <div>
              <dt>Paid on</dt>
              <dd>{pay?.paid_at ? formatDateTime(pay.paid_at) : "—"}</dd>
            </div>
            <div>
              <dt>Due</dt>
              <dd>{formatDate(invoice.due_at)}</dd>
            </div>
          </dl>

          <table className="tb-doc-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(invoice.lines || []).map((line, idx) => (
                <tr key={`${line.product_id ?? line.description}-${idx}`}>
                  <td>{idx + 1}</td>
                  <td>
                    <strong>{line.description}</strong>
                  </td>
                  <td>
                    {line.quantity ?? "—"} {line.unit ?? ""}
                  </td>
                  <td>{formatMoney(line.unit_price, cur)}</td>
                  <td>{formatMoney(line.line_total, cur)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="tb-doc-foot">
            <div className="tb-doc-notes">
              <p>
                {invoice.checkout_id
                  ? "Part of a checkout with one invoice per supplier. This invoice covers only this supplier's order."
                  : "Issued against the order above."}
              </p>
            </div>
            <dl className="tb-doc-totals">
              <div>
                <dt>Subtotal</dt>
                <dd>{formatMoney(invoice.subtotal ?? invoice.total, cur)}</dd>
              </div>
              {isPositive(invoice.discount_total) ? (
                <div>
                  <dt>Discount</dt>
                  <dd>−{formatMoney(invoice.discount_total, cur)}</dd>
                </div>
              ) : null}
              {isPositive(invoice.charge_total) ? (
                <div>
                  <dt>Charges</dt>
                  <dd>{formatMoney(invoice.charge_total, cur)}</dd>
                </div>
              ) : null}
              {isPositive(invoice.tax_total) ? (
                <div>
                  <dt>{taxLabel}</dt>
                  <dd>{formatMoney(invoice.tax_total, cur)}</dd>
                </div>
              ) : null}
              <div data-grand="true">
                <dt>Total</dt>
                <dd>{formatMoney(invoice.total, cur)}</dd>
              </div>
              <div>
                <dt>Paid</dt>
                <dd>{formatMoney(invoice.amount_paid, cur)}</dd>
              </div>
              {isPositive(invoice.amount_credited) ? (
                <div>
                  <dt>Credited</dt>
                  <dd>−{formatMoney(invoice.amount_credited, cur)}</dd>
                </div>
              ) : null}
              <div>
                <dt>Balance due</dt>
                <dd>{formatMoney(invoice.outstanding, cur)}</dd>
              </div>
            </dl>
          </div>
        </div>
      </article>
    </div>
  );
}
