"use client";

import {
  InventoryBtn,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { CardPaymentForm } from "@/components/commerce/CardPaymentForm";
import { OrderTimeline } from "@/components/commerce/OrderTimeline";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/useConfirm";
import { checkoutApi, type Checkout, type CheckoutOrder } from "@/lib/api/checkoutApi";
import { procurementApi, type OrderTimelineStep } from "@/lib/api/procurementApi";
import {
  checkoutView,
  errorText,
  formatDateTime,
  formatMoney,
  initials,
  isPositive,
  paymentMethodLabel,
  paymentView,
} from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

function SupplierOrderCard({
  order,
  currency,
  timeline,
  canCancel,
  onCancel,
  busy,
}: {
  order: CheckoutOrder;
  currency: string;
  timeline: OrderTimelineStep[] | undefined;
  canCancel: boolean;
  onCancel: () => void;
  busy: boolean;
}) {
  const hidden = order.order_status === "awaiting_payment";
  return (
    <article className="tb-co-order-card">
      <div className="tb-co-group-head">
        <div className="tb-co-group-head__who">
          <span className="tb-co-avatar" aria-hidden>
            {initials(order.supplier_name)}
          </span>
          <div className="min-w-0">
            <strong>{order.supplier_name}</strong>
            <span>
              Order {order.order_number} · {order.line_count} {order.line_count === 1 ? "item" : "items"}
            </span>
          </div>
        </div>
        <StatusBadge status={order.order_status} />
      </div>

      {timeline?.length ? <OrderTimeline steps={timeline} compact /> : null}

      {order.lines?.length ? (
        <ul className="tb-co-lines">
          {order.lines.map((line, i) => (
            <li key={`${line.product_id}-${i}`} className="tb-co-line !grid-cols-[minmax(0,1fr)_auto]">
              <div className="tb-co-line__name">
                <strong>{line.product_name}</strong>
                <span>
                  {String(line.quantity)} {line.unit} × {formatMoney(line.unit_price, currency)}
                </span>
              </div>
              <span className="tb-co-line__amount">{formatMoney(line.line_total, currency)}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="tb-co-money">
        <div>
          <dt>Subtotal</dt>
          <dd>{formatMoney(order.subtotal, currency)}</dd>
        </div>
        {isPositive(order.tax_total) ? (
          <div>
            <dt>Tax</dt>
            <dd>{formatMoney(order.tax_total, currency)}</dd>
          </div>
        ) : null}
        <div data-total="true">
          <dt>Order total</dt>
          <dd>{formatMoney(order.total, currency)}</dd>
        </div>
      </dl>

      <div className="tb-co-order-card__actions">
        {!hidden ? (
          <InventoryLinkBtn href={ROUTES.procurementOrder(order.order_id)} tone="soft">
            View order
          </InventoryLinkBtn>
        ) : null}
        {!hidden && order.order_status !== "cancelled" && order.order_status !== "pending" ? (
          <InventoryLinkBtn href={ROUTES.trackingOrder(order.order_id)} tone="ghost">
            Track
          </InventoryLinkBtn>
        ) : null}
        {order.invoice && order.invoice.status !== "draft" ? (
          <InventoryLinkBtn href={ROUTES.financeInvoice(order.invoice.id)} tone="ghost">
            Invoice {order.invoice.invoice_number}
          </InventoryLinkBtn>
        ) : null}
        {canCancel ? (
          <InventoryBtn tone="ghost" busy={busy} onClick={onCancel}>
            Cancel this order
          </InventoryBtn>
        ) : null}
      </div>
    </article>
  );
}

export function CheckoutDetail({ checkoutId }: { checkoutId: string }) {
  const params = useSearchParams();
  const justPlaced = params.get("placed") === "1";
  const wantsPay = params.get("pay") === "1";
  const returnedFromProcessor = params.has("payment_intent");
  const { business, hasPermission } = useAuth();
  const isBuyer = business?.type === "buyer";
  const { success, error: toastError } = useToast();
  const { confirm, prompt, dialog } = useConfirm();

  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [timelines, setTimelines] = useState<Record<string, OrderTimelineStep[] | undefined>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [card, setCard] = useState<{ clientSecret: string; publishableKey: string } | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const autoStarted = useRef(false);

  const loadTimelines = useCallback(async (data: Checkout) => {
    const visible = data.orders.filter((o) => o.order_status !== "awaiting_payment");
    const entries = await Promise.all(
      visible.map(async (o) => {
        try {
          const detail = await procurementApi.getOrder(o.order_id);
          return [o.order_id, detail.timeline] as const;
        } catch {
          return [o.order_id, undefined] as const;
        }
      }),
    );
    setTimelines(Object.fromEntries(entries));
  }, []);

  const apply = useCallback(
    (data: Checkout) => {
      setCheckout(data);
      setError(null);
      void loadTimelines(data);
    },
    [loadTimelines],
  );

  const load = useCallback(async () => {
    try {
      const data =
        returnedFromProcessor ? await checkoutApi.refreshPayment(checkoutId) : await checkoutApi.get(checkoutId);
      apply(data);
    } catch (err) {
      setError(errorText(err, "Couldn't load this checkout"));
    }
  }, [apply, checkoutId, returnedFromProcessor]);

  useEffect(() => {
    void load();
  }, [load]);

  const awaitingCard = checkout?.payment_method === "card" && checkout.status === "awaiting_payment";

  const startCard = useCallback(async () => {
    setCardError(null);
    setBusy("card");
    try {
      const res = await checkoutApi.startCardPayment(checkoutId);
      if (!res.publishable_key) throw new Error("Card payments aren't available right now.");
      setCard({ clientSecret: res.client_secret, publishableKey: res.publishable_key });
      apply(res.checkout);
    } catch (err) {
      setCardError(err instanceof Error ? errorText(err, err.message) : "Couldn't start the card payment.");
    } finally {
      setBusy(null);
    }
  }, [apply, checkoutId]);

  useEffect(() => {
    if (wantsPay && awaitingCard && isBuyer && !card && !autoStarted.current) {
      autoStarted.current = true;
      void startCard();
    }
  }, [wantsPay, awaitingCard, isBuyer, card, startCard]);

  
  async function verifyPayment() {
    setVerifying(true);
    try {
      for (let attempt = 0; attempt < 5; attempt += 1) {
        const data = await checkoutApi.refreshPayment(checkoutId);
        apply(data);
        if (data.status !== "awaiting_payment" || data.payment?.status === "failed") {
          if (data.status === "paid") {
            setCard(null);
            success("Payment received", "Your suppliers have been notified.");
          }
          return;
        }
        await new Promise((r) => window.setTimeout(r, 1500));
      }
    } catch (err) {
      toastError("Couldn't confirm payment", errorText(err, "Refresh the page in a moment."));
    } finally {
      setVerifying(false);
    }
  }

  async function cancelCheckout() {
    const ok = await confirm({
      title: "Cancel this checkout?",
      body: "All supplier orders in this checkout will be cancelled and reserved stock released. This can't be undone.",
      confirmLabel: "Cancel checkout",
      cancelLabel: "Keep it",
      destructive: true,
    });
    if (!ok) return;
    setBusy("cancel");
    try {
      apply(await checkoutApi.cancel(checkoutId));
      setCard(null);
      success("Checkout cancelled");
    } catch (err) {
      toastError("Couldn't cancel", errorText(err, "Try again."));
    } finally {
      setBusy(null);
    }
  }

  async function cancelOne(order: CheckoutOrder) {
    const reason = await prompt({
      title: `Cancel order ${order.order_number}?`,
      body: `Only the order from ${order.supplier_name} is cancelled. Other suppliers' orders continue as normal.`,
      confirmLabel: "Cancel order",
      cancelLabel: "Keep it",
      destructive: true,
      input: { label: "Reason (optional)", placeholder: "Let the supplier know why" },
    });
    if (reason === null) return;
    setBusy(order.order_id);
    try {
      await checkoutApi.cancelOrder(order.order_id, reason);
      await load();
      success("Order cancelled");
    } catch (err) {
      toastError("Couldn't cancel", errorText(err, "Try again."));
    } finally {
      setBusy(null);
    }
  }

  if (!checkout && !error) {
    return (
      <div className="tb-inv-page tb-co-page">
        <LoadingEntity entity="checkout" className="py-8" />
      </div>
    );
  }

  if (!checkout) {
    return (
      <div className="tb-inv-page tb-co-page">
        <FeedbackBanner tone="error" title="Checkout unavailable">
          {error}
        </FeedbackBanner>
        <div>
          <BackLink href={ROUTES.orders}>Orders</BackLink>
        </div>
      </div>
    );
  }

  const cur = checkout.currency;
  const status = checkoutView(checkout.status, checkout.payment_method);
  const pay = checkout.payment;
  const payBadge = paymentView(checkout.payment_method, pay?.status);
  const canCancelAll =
    isBuyer &&
    hasPermission("orders.cancel") &&
    checkout.status === "awaiting_payment" &&
    checkout.orders.every((o) => ["awaiting_payment", "pending", "cancelled"].includes(o.order_status));
  const canCancelOne = (o: CheckoutOrder) =>
    isBuyer && hasPermission("orders.cancel") && o.order_status === "pending" && checkout.orders.length > 1;
  const activeTotalDiffers = checkout.active_total !== checkout.total;

  return (
    <div className="tb-inv-page tb-co-page">
      {dialog}
      <InventoryPageHeader
        eyebrow="Orders"
        mark="Checkout"
        title={`Checkout ${checkout.checkout_number}`}
        description={`Placed ${formatDateTime(checkout.created_at)} · ${checkout.supplier_count} ${
          checkout.supplier_count === 1 ? "supplier" : "suppliers"
        }`}
        actions={
          <>
            <BackLink href={ROUTES.orders}>Orders</BackLink>
            {canCancelAll ? (
              <InventoryBtn tone="ghost" busy={busy === "cancel"} onClick={() => void cancelCheckout()}>
                Cancel checkout
              </InventoryBtn>
            ) : null}
          </>
        }
      />

      {justPlaced && checkout.status !== "cancelled" ? (
        <FeedbackBanner tone="success" title="Order placed">
          {checkout.payment_method === "cash"
            ? "Your suppliers have your order. Each one confirms and ships on its own, and you pay in cash on delivery."
            : "Thanks — your order is confirmed."}
        </FeedbackBanner>
      ) : null}

      {checkout.status === "paid" && !justPlaced && checkout.payment_method === "card" && returnedFromProcessor ? (
        <FeedbackBanner tone="success" title="Payment received">
          Your suppliers have been notified and will start preparing your order.
        </FeedbackBanner>
      ) : null}

      {checkout.split_notice ? (
        <FeedbackBanner tone="info" title="One order per supplier">
          {checkout.split_notice}
        </FeedbackBanner>
      ) : null}

      <div className="tb-co-layout">
        <div className="tb-co-stack">
          {awaitingCard ? (
            <FeedbackBanner tone="warning" title="Payment needed">
              Your suppliers will see this order once your card payment is confirmed.
            </FeedbackBanner>
          ) : null}
          <div className="tb-co-orders">
            {checkout.orders.map((order) => (
              <SupplierOrderCard
                key={order.order_id}
                order={order}
                currency={cur}
                timeline={timelines[order.order_id]}
                canCancel={canCancelOne(order)}
                busy={busy === order.order_id}
                onCancel={() => void cancelOne(order)}
              />
            ))}
          </div>
        </div>

        <aside aria-label="Payment">
          <InventoryPanel title="Summary" action={<StatusBadge status={checkout.status} label={status.label} tone={status.tone} />}>
            <dl className="tb-co-money">
              <div>
                <dt>Subtotal</dt>
                <dd>{formatMoney(checkout.subtotal, cur)}</dd>
              </div>
              {isPositive(checkout.tax_total) ? (
                <div>
                  <dt>Tax</dt>
                  <dd>{formatMoney(checkout.tax_total, cur)}</dd>
                </div>
              ) : null}
              <div data-total="true">
                <dt>Total</dt>
                <dd>{formatMoney(checkout.total, cur)}</dd>
              </div>
              {activeTotalDiffers && checkout.status !== "cancelled" ? (
                <div>
                  <dt>After cancellations</dt>
                  <dd>{formatMoney(checkout.active_total, cur)}</dd>
                </div>
              ) : null}
            </dl>
          </InventoryPanel>

          <InventoryPanel
            title="Payment"
            action={pay ? <StatusBadge status={pay.status} label={payBadge.label} tone={payBadge.tone} /> : null}
          >
            <dl className="tb-co-facts">
              <div>
                <dt>Method</dt>
                <dd>{paymentMethodLabel(checkout.payment_method)}</dd>
              </div>
              {pay ? (
                <div>
                  <dt>Reference</dt>
                  <dd>{pay.payment_reference}</dd>
                </div>
              ) : null}
              {pay?.receipt_number ? (
                <div>
                  <dt>Receipt</dt>
                  <dd>{pay.receipt_number}</dd>
                </div>
              ) : null}
              {pay?.paid_at ? (
                <div>
                  <dt>Paid</dt>
                  <dd>{formatDateTime(pay.paid_at)}</dd>
                </div>
              ) : null}
            </dl>

            {pay && pay.allocations.length > 1 ? (
              <dl className="tb-co-money mt-4 border-t border-[var(--tb-line-soft)] pt-3">
                {pay.allocations.map((a) => (
                  <div key={a.invoice_id}>
                    <dt>{a.supplier_name || a.invoice_number}</dt>
                    <dd>{formatMoney(a.amount, cur)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}

            {checkout.payment_method === "cash" && checkout.status === "awaiting_payment" ? (
              <p className="tb-co-note mt-3">
                Pay in cash when your goods arrive. Your invoice is marked paid once TradeBay records the cash.
              </p>
            ) : null}

            {pay?.status === "failed" && pay.failure_message ? (
              <FeedbackBanner tone="error" title="Last attempt didn't go through" className="mt-3">
                {pay.failure_message}
              </FeedbackBanner>
            ) : null}

            {awaitingCard && isBuyer ? (
              <div className="mt-4 grid gap-3">
                {cardError ? (
                  <FeedbackBanner tone="error" title="Card payment unavailable">
                    {cardError}
                  </FeedbackBanner>
                ) : null}
                {verifying ? <LoadingEntity entity="payment confirmation" compact /> : null}
                {card && !verifying ? (
                  <CardPaymentForm
                    clientSecret={card.clientSecret}
                    publishableKey={card.publishableKey}
                    amountLabel={formatMoney(checkout.active_total, cur)}
                    returnUrl={`${window.location.origin}${ROUTES.checkoutDetail(checkout.id)}`}
                    onSubmitted={verifyPayment}
                  />
                ) : null}
                {!card && !verifying ? (
                  <InventoryBtn busy={busy === "card"} onClick={() => void startCard()} className="w-full">
                    {pay?.status === "failed" ? "Try another card" : `Pay ${formatMoney(checkout.active_total, cur)} by card`}
                  </InventoryBtn>
                ) : null}
                {!card && !verifying ? (
                  <InventoryBtn tone="ghost" onClick={() => void verifyPayment()} className="w-full">
                    Already paid? Check status
                  </InventoryBtn>
                ) : null}
              </div>
            ) : null}
          </InventoryPanel>

          {checkout.notes ? (
            <InventoryPanel title="Your note">
              <p className="tb-co-note">{checkout.notes}</p>
            </InventoryPanel>
          ) : null}

          <p className="tb-co-note">
            Each supplier sends its own invoice.{" "}
            <Link className="tb-co-link" href={ROUTES.finance}>
              See all invoices
            </Link>
          </p>
        </aside>
      </div>
    </div>
  );
}
