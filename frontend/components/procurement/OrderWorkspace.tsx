"use client";

import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import { procurementApi, type Address, type PurchaseOrder } from "@/lib/api/procurementApi";
import { paymentMethodLabel, paymentView } from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { dealInitials } from "@/lib/procurement/dealRoom";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { BackLink } from "@/components/ui/BackLink";

export function DocLogo({ name, logoUrl }: { name: string; logoUrl?: string | null }) {
  const src = mediaUrl(logoUrl);
  return (
    <span className="tb-doc-logo" aria-hidden>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" />
      ) : (
        dealInitials(name)
      )}
    </span>
  );
}

function formatAddress(addr?: Address | null): string | null {
  if (!addr) return null;
  const line = [addr.street, addr.city, addr.district, addr.governorate, addr.postal_code, addr.country]
    .filter(Boolean)
    .join(", ");
  return line || null;
}

export function PartyBlock({
  label,
  name,
  legalName,
  logoUrl,
  address,
  email,
  phone,
  taxNumber,
}: {
  label: string;
  name: string;
  legalName?: string | null;
  logoUrl?: string | null;
  address?: Address | null;
  email?: string | null;
  phone?: string | null;
  taxNumber?: string | null;
}) {
  const lines = formatAddress(address);
  return (
    <div className="tb-doc-party">
      <p className="tb-doc-party__label">{label}</p>
      <div className="tb-doc-party__who">
        <DocLogo name={name} logoUrl={logoUrl} />
        <div>
          <strong>{name}</strong>
          {legalName && legalName !== name ? <span>{legalName}</span> : null}
        </div>
      </div>
      {lines ? <address>{lines}</address> : null}
      {(email || phone || taxNumber) && (
        <ul className="tb-doc-party__contacts">
          {taxNumber ? <li>Tax ID · {taxNumber}</li> : null}
          {email ? <li>{email}</li> : null}
          {phone ? <li>{phone}</li> : null}
        </ul>
      )}
    </div>
  );
}

type Props = { orderId: string };

export function OrderWorkspace({ orderId }: Props) {
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void procurementApi
      .getOrder(orderId)
      .then((data) => {
        setOrder(data);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load purchase order");
      });
  }, [orderId]);

  if (!order && !error) return <LoadingEntity entity="purchase order" />;
  if (!order) {
    return (
      <FeedbackBanner tone="error" title="Couldn't open order">
        {error}
      </FeedbackBanner>
    );
  }

  return (
    <div className="tb-docs tb-doc--po">
      <OrderDocToolbar order={order} />
      <OrderDocument order={order} />
    </div>
  );
}

export function OrderDocToolbar({ order, children }: { order: PurchaseOrder; children?: ReactNode }) {
  const canTrack = !["draft", "cancelled", "awaiting_payment"].includes(order.status);
  return (
    <div className="tb-docs__toolbar">
      <nav className="tb-docs__toolbar-nav">
        <BackLink href={ROUTES.orders}>Orders</BackLink>
        {order.checkout_id ? <Link href={ROUTES.checkoutDetail(order.checkout_id)}>Checkout {order.checkout_number}</Link> : null}
        {order.rfq_id ? <Link href={ROUTES.procurementRfq(order.rfq_id)}>Related RFQ</Link> : null}
      </nav>
      <div className="tb-docs__actions">
        {children}
        {canTrack ? (
          <Link href={ROUTES.trackingOrder(order.id)} className="tb-btn tb-btn--primary">
            Track package
          </Link>
        ) : null}
        {order.status !== "draft" ? (
          <a
            href={procurementApi.orderPdfUrl(order.id)}
            className="tb-btn tb-btn--secondary"
            target="_blank"
            rel="noreferrer"
          >
            Download PDF
          </a>
        ) : null}
      </div>
    </div>
  );
}

export function OrderDocument({ order }: { order: PurchaseOrder }) {
  const buyerName = order.buyer_name || "Buyer";
  const supplierName = order.supplier_name || "Supplier";
  const shipTo = formatAddress(order.shipping_address);
  const buyerAddr = formatAddress(order.buyer_address);
  const issued =
    order.created_at != null
      ? new Date(order.created_at).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "—";
  const payment = paymentView(order.payment_method, order.payment_status);

  return (
      <article className="tb-doc-paper--po tb-doc-paper--po-wide">
        <header className="tb-doc-band">
          <div className="tb-doc-band__brand">
            <DocLogo name={buyerName} logoUrl={order.buyer_logo_url} />
            <div>
              <h1>{buyerName}</h1>
              <p>
                {[buyerAddr, order.buyer_contact_email, order.buyer_contact_phone]
                  .filter(Boolean)
                  .join(" · ") || "Purchase order"}
              </p>
            </div>
          </div>
          <div className="tb-doc-meta">
            <div className="tb-doc-meta__title">PURCHASE ORDER</div>
            <strong>{order.order_number}</strong>
            <div>Date · {issued}</div>
            {order.quotation_number ? <div>Ref · {order.quotation_number}</div> : null}
          </div>
        </header>

        <div className="tb-doc-body">
          <div className="tb-doc-parties">
            <PartyBlock
              label="Vendor"
              name={supplierName}
              legalName={order.supplier_legal_name}
              logoUrl={order.supplier_logo_url}
              address={order.supplier_address}
              email={order.supplier_contact_email}
              phone={order.supplier_contact_phone}
              taxNumber={order.supplier_tax_number}
            />
            <PartyBlock
              label="Bill to"
              name={buyerName}
              legalName={order.buyer_legal_name}
              logoUrl={order.buyer_logo_url}
              address={order.buyer_address}
              email={order.buyer_contact_email}
              phone={order.buyer_contact_phone}
              taxNumber={order.buyer_tax_number}
            />
            <div className="tb-doc-party">
              <p className="tb-doc-party__label">Ship to</p>
              {shipTo ? (
                <p className="tb-doc-party__ship">{shipTo}</p>
              ) : (
                <p className="tb-doc-party__ship tb-doc-party__ship--empty">Same as bill to</p>
              )}
            </div>
          </div>

          <dl className="tb-doc-terms">
            <div>
              <dt>Currency</dt>
              <dd>{order.currency}</dd>
            </div>
            <div>
              <dt>Payment terms</dt>
              <dd>{order.payment_terms || "—"}</dd>
            </div>
            <div>
              <dt>Payment method</dt>
              <dd>{paymentMethodLabel(order.payment_method)}</dd>
            </div>
            <div>
              <dt>Delivery terms</dt>
              <dd>{order.delivery_terms || "—"}</dd>
            </div>
            <div>
              <dt>Payment status</dt>
              <dd>{payment.label}</dd>
            </div>
            <div>
              <dt>{order.tax_name_snapshot || "VAT"}</dt>
              <dd>
                {order.tax_rate_percent
                  ? order.tax_rate_percent
                  : order.tax_rate_snapshot
                    ? `${(Number(order.tax_rate_snapshot) * 100).toFixed(2).replace(/\.?0+$/, "")}%`
                    : "—"}
              </dd>
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
              {order.items.map((item, idx) => (
                <tr key={item.id}>
                  <td>{idx + 1}</td>
                  <td>
                    <strong>{item.product_name_snapshot}</strong>
                    {item.sku_snapshot ? <em>SKU {item.sku_snapshot}</em> : null}
                  </td>
                  <td>
                    {item.quantity} {item.unit}
                  </td>
                  <td>
                    {order.currency} {item.unit_price}
                  </td>
                  <td>
                    {order.currency} {item.line_total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="tb-doc-foot">
            <div className="tb-doc-notes">
              {order.quotation_number ? (
                <p>Issued against quotation {order.quotation_number}.</p>
              ) : null}
              <p className="tb-doc-sign">
                Authorized by
                <span />
              </p>
            </div>
            <dl className="tb-doc-totals">
              <div>
                <dt>Subtotal</dt>
                <dd>
                  {order.currency} {order.subtotal}
                </dd>
              </div>
              {Number(order.discount_total) > 0 ? (
                <div>
                  <dt>Discount</dt>
                  <dd>
                    −{order.currency} {order.discount_total}
                  </dd>
                </div>
              ) : null}
              {Number(order.charge_total) > 0 ? (
                <div>
                  <dt>Charges</dt>
                  <dd>
                    {order.currency} {order.charge_total}
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>
                  {order.tax_name_snapshot || "VAT"}
                  {order.tax_rate_percent ? ` (${order.tax_rate_percent})` : ""}
                </dt>
                <dd>
                  {order.currency} {order.tax_total || "0.00"}
                </dd>
              </div>
              <div data-grand="true">
                <dt>Total</dt>
                <dd>
                  {order.currency} {order.total}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </article>
  );
}
