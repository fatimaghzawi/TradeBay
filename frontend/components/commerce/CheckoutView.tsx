"use client";

import {
  InventoryBtn,
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import {
  checkoutApi,
  newIdempotencyKey,
  type CheckoutPreview,
  type CheckoutPreviewGroup,
  type PaymentMethodId,
} from "@/lib/api/checkoutApi";
import { errorText, formatMoney, formatRate, initials, isPositive } from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

function SupplierGroup({ group }: { group: CheckoutPreviewGroup }) {
  const itemCount = group.lines.length;
  return (
    <InventoryPanel
      title={
        <span className="tb-co-group-head__who">
          <span className="tb-co-avatar" aria-hidden>
            {initials(group.supplier_name)}
          </span>
          <span className="min-w-0">
            <strong>{group.supplier_name}</strong>
            <span>
              {itemCount} {itemCount === 1 ? "item" : "items"} · separate order and invoice
            </span>
          </span>
        </span>
      }
      action={
        <div className="text-right">
          <p className="tb-co-note">Supplier subtotal</p>
          <p className="tb-co-line__amount">{formatMoney(group.subtotal, group.currency)}</p>
        </div>
      }
    >
      <ul className="tb-co-lines">
        {group.lines.map((line) => (
          <li key={`${line.product_id}-${line.unit_price}`} className="tb-co-line">
            {line.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={mediaUrl(line.image_url)} alt="" className="tb-co-thumb" />
            ) : (
              <span className="tb-co-thumb" aria-hidden>
                {initials(line.product_name)}
              </span>
            )}
            <div className="tb-co-line__name">
              <strong>{line.product_name}</strong>
              <span>
                {String(line.quantity)} {line.unit} × {formatMoney(line.unit_price, group.currency)}
                {line.sku ? ` · SKU ${line.sku}` : ""}
              </span>
            </div>
            <span className="tb-co-line__amount">{formatMoney(line.line_total, group.currency)}</span>
          </li>
        ))}
      </ul>
      {isPositive(group.tax_total) ? (
        <dl className="tb-co-money mt-3 border-t border-[var(--tb-line-soft)] pt-3">
          <div>
            <dt>
              {group.tax_name || "Tax"}
              {group.tax_rate ? ` (${formatRate(group.tax_rate)})` : ""}
            </dt>
            <dd>{formatMoney(group.tax_total, group.currency)}</dd>
          </div>
          <div>
            <dt>Total from {group.supplier_name}</dt>
            <dd>{formatMoney(group.total, group.currency)}</dd>
          </div>
        </dl>
      ) : null}
    </InventoryPanel>
  );
}

function MethodPicker({
  methods,
  value,
  onChange,
}: {
  methods: CheckoutPreview["methods"];
  value: PaymentMethodId | null;
  onChange: (id: PaymentMethodId) => void;
}) {
  return (
    <div className="tb-co-methods" role="radiogroup" aria-label="Payment method">
      {methods.map((m) => {
        const active = value === m.id;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={active}
            aria-disabled={!m.available || undefined}
            disabled={!m.available}
            className={cn("tb-form-role-card", active && "is-active")}
            onClick={() => m.available && onChange(m.id)}
          >
            <span className="tb-form-role-check" aria-hidden>
              {active ? "✓" : ""}
            </span>
            <span className="tb-form-role-name">{m.id === "card" ? "Visa / Card" : "Cash"}</span>
            <span className="tb-form-role-blurb">{m.description}</span>
            {m.id === "cash" ? (
              <span className="tb-form-role-meta">Pay when your goods arrive</span>
            ) : (
              <span className="tb-form-role-meta">{m.available ? "Pay now, securely" : "Not available yet"}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function CheckoutView() {
  const router = useRouter();
  const [preview, setPreview] = useState<CheckoutPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emptyCart, setEmptyCart] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [method, setMethod] = useState<PaymentMethodId | null>(null);
  const [notes, setNotes] = useState("");
  const [placing, setPlacing] = useState(false);
  const [placeError, setPlaceError] = useState<string | null>(null);
  
  const keyRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await checkoutApi.preview();
      setPreview(data);
      setError(null);
      setEmptyCart(false);
      setMethod((current) =>
        current && data.methods.some((m) => m.id === current && m.available) ? current : null,
      );
    } catch (err) {
      const reason =
        err instanceof ApiError && err.details && typeof err.details === "object"
          ? (err.details as { reason?: string }).reason
          : undefined;
      setPreview(null);
      setEmptyCart(reason === "cart_empty");
      setError(reason === "cart_empty" ? null : errorText(err, "Couldn't load checkout"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function place() {
    if (!preview || !method) return;
    keyRef.current ??= newIdempotencyKey();
    setPlacing(true);
    setPlaceError(null);
    try {
      const checkout = await checkoutApi.place(keyRef.current, {
        payment_method: method,
        expected_total: preview.total,
        notes: notes.trim() || undefined,
      });
      keyRef.current = null;
      const next = ROUTES.checkoutDetail(checkout.id);
      router.push(checkout.payment_method === "card" && checkout.status === "awaiting_payment" ? `${next}?pay=1` : `${next}?placed=1`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "CHECKOUT_TOTAL_CHANGED") {
        keyRef.current = null;
        setNotice("Prices or stock changed while you were checking out. Review the updated total before placing your order.");
        await load();
      } else {
        setPlaceError(errorText(err, "We couldn't place your order. Try again."));
      }
    } finally {
      setPlacing(false);
    }
  }

  const header = (
    <InventoryPageHeader
      eyebrow="Orders"
      mark="Checkout"
      title="Checkout"
      description="Review your items by supplier, choose how to pay, and place your order."
      actions={
        <BackLink href={ROUTES.inventoryProducts}>Continue shopping</BackLink>
      }
    />
  );

  if (loading && !preview) {
    return (
      <div className="tb-inv-page tb-co-page">
        {header}
        <LoadingEntity entity="checkout" className="py-8" />
      </div>
    );
  }

  if (emptyCart) {
    return (
      <div className="tb-inv-page tb-co-page">
        {header}
        <InventoryPanel>
          <InventoryEmpty
            title="Your cart is empty"
            body="Add products from the marketplace, then come back here to check out."
            action={<InventoryLinkBtn href={ROUTES.inventoryProducts}>Browse products</InventoryLinkBtn>}
          />
        </InventoryPanel>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="tb-inv-page tb-co-page">
        {header}
        <FeedbackBanner tone="error" title="Checkout needs attention">
          {error}
        </FeedbackBanner>
        <div className="flex flex-wrap gap-2">
          <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="soft">
            Review your cart
          </InventoryLinkBtn>
          <InventoryBtn tone="ghost" onClick={() => void load()}>
            Try again
          </InventoryBtn>
        </div>
      </div>
    );
  }

  const cur = preview.currency;
  const count = preview.supplier_count;
  const hasTax = isPositive(preview.tax_total);

  return (
    <div className="tb-inv-page tb-co-page">
      {header}

      {notice ? (
        <FeedbackBanner tone="warning" title="Your total was updated" onDismiss={() => setNotice(null)}>
          {notice}
        </FeedbackBanner>
      ) : null}

      {preview.price_changes.length > 0 ? (
        <FeedbackBanner tone="warning" title="Some prices changed since you added them">
          <ul className="mt-1 grid gap-0.5">
            {preview.price_changes.map((c) => (
              <li key={c.product_id}>
                {c.product_name}: {c.previous_unit_price ? `${formatMoney(c.previous_unit_price, cur)} → ` : ""}
                <strong>{formatMoney(c.unit_price, cur)}</strong>
              </li>
            ))}
          </ul>
        </FeedbackBanner>
      ) : null}

      {preview.split_notice ? (
        <FeedbackBanner tone="info" title={`${count} suppliers in this order`}>
          {preview.split_notice}
        </FeedbackBanner>
      ) : null}

      <div className="tb-co-layout">
        <div className="tb-co-stack">
          {preview.groups.map((group) => (
            <SupplierGroup key={group.supplier_business_id} group={group} />
          ))}
        </div>

        <aside aria-label="Order summary">
          <InventoryPanel title="Order summary">
            <dl className="tb-co-money">
              {preview.groups.length > 1
                ? preview.groups.map((g) => (
                    <div key={g.supplier_business_id}>
                      <dt>{g.supplier_name}</dt>
                      <dd>{formatMoney(g.subtotal, cur)}</dd>
                    </div>
                  ))
                : null}
              <div>
                <dt>Subtotal</dt>
                <dd>{formatMoney(preview.subtotal, cur)}</dd>
              </div>
              {hasTax ? (
                <div>
                  <dt>Tax</dt>
                  <dd>{formatMoney(preview.tax_total, cur)}</dd>
                </div>
              ) : null}
              <div data-total="true">
                <dt>Total</dt>
                <dd>{formatMoney(preview.total, cur)}</dd>
              </div>
            </dl>
          </InventoryPanel>

          <InventoryPanel title="Payment method" subtitle="Choose how you'd like to pay.">
            <MethodPicker methods={preview.methods} value={method} onChange={setMethod} />
            {method === "cash" ? (
              <p className="tb-co-note mt-3">
                You&apos;ll pay in cash on delivery. Each supplier confirms your order first, and your invoice is
                marked paid once the cash is received.
              </p>
            ) : null}

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="tb-field-label">Note for suppliers (optional)</span>
              <textarea
                value={notes}
                maxLength={1000}
                rows={2}
                placeholder="Delivery instructions, contact person…"
                onChange={(e) => setNotes(e.target.value)}
              />
            </label>

            {placeError ? (
              <FeedbackBanner tone="error" title="Order not placed" className="mt-3">
                {placeError}
              </FeedbackBanner>
            ) : null}

            <InventoryBtn
              className="mt-4 w-full"
              busy={placing}
              disabled={!method || loading}
              onClick={() => void place()}
            >
              {method === "card" ? `Continue to payment · ${formatMoney(preview.total, cur)}` : `Place order · ${formatMoney(preview.total, cur)}`}
            </InventoryBtn>
            {!method ? <p className="tb-co-note mt-2 text-center">Choose a payment method to continue.</p> : null}
          </InventoryPanel>
        </aside>
      </div>
    </div>
  );
}
