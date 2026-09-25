"use client";

import { InventoryBtn, InventoryLinkBtn, InventoryPanel, StatusBadge } from "@/components/catalog/InventoryUi";
import { OrderTimeline } from "@/components/commerce/OrderTimeline";
import { OrderDocToolbar, OrderDocument } from "@/components/procurement/OrderWorkspace";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/useConfirm";
import { checkoutApi } from "@/lib/api/checkoutApi";
import { procurementApi, type PurchaseOrder } from "@/lib/api/procurementApi";
import {
  errorText,
  formatDateTime,
  formatMoney,
  paymentMethodLabel,
  paymentView,
} from "@/lib/commerce/format";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import { useCallback, useEffect, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

const COMMISSION_NOTE: Record<string, string> = {
  pending: "Commission is recorded once the buyer's payment is received.",
  recognized: "Commission recorded against this order.",
  reversed: "Commission reversed after cancellation.",
};

function EarningsPanel({ order }: { order: PurchaseOrder }) {
  const f = order.financials;
  if (!f) return null;
  const cur = f.currency || order.currency;
  return (
    <InventoryPanel title="Your earnings" subtitle="What this order is worth to you after the platform commission.">
      <dl className="tb-co-money">
        <div>
          <dt>Order amount</dt>
          <dd>{formatMoney(f.order_amount, cur)}</dd>
        </div>
        <div data-tone="minus">
          <dt>Platform commission{f.platform_fee_percent ? ` (${f.platform_fee_percent})` : ""}</dt>
          <dd>{f.platform_fee ? `−${formatMoney(f.platform_fee, cur)}` : "—"}</dd>
        </div>
        <div data-total="true">
          <dt>Your earnings</dt>
          <dd>{formatMoney(f.supplier_earnings, cur)}</dd>
        </div>
      </dl>
      {f.commission_status ? (
        <p className="tb-co-note mt-3">{COMMISSION_NOTE[f.commission_status] ?? ""}</p>
      ) : null}
    </InventoryPanel>
  );
}

export function OrderDetail({ orderId }: { orderId: string }) {
  const { business, hasPermission } = useAuth();
  const type = business?.type;
  const { success, error: toastError } = useToast();
  const { confirm, prompt, dialog } = useConfirm();
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setOrder(await procurementApi.getOrder(orderId));
      setError(null);
    } catch (err) {
      setError(errorText(err, "Couldn't load this order"));
    }
  }, [orderId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(key: string, action: () => Promise<unknown>, done: string) {
    setBusy(key);
    try {
      await action();
      await load();
      success(done);
    } catch (err) {
      toastError("That didn't go through", errorText(err, "Try again."));
    } finally {
      setBusy(null);
    }
  }

  async function acceptOrder() {
    const ok = await confirm({
      title: "Confirm this order?",
      body: "You're committing to fulfil it. The buyer is notified and can track progress.",
      confirmLabel: "Confirm order",
    });
    if (ok) await run("confirm", () => procurementApi.acknowledgeOrder(orderId), "Order confirmed");
  }

  async function cancelOrder(asSupplier: boolean) {
    const reason = await prompt({
      title: asSupplier ? "Decline this order?" : "Cancel this order?",
      body: asSupplier
        ? "The buyer is told the order was declined. Reserved stock goes back to your inventory."
        : "The supplier is notified and any reserved stock is released. This can't be undone.",
      confirmLabel: asSupplier ? "Decline order" : "Cancel order",
      cancelLabel: "Keep it",
      destructive: true,
      input: { label: "Reason (optional)", placeholder: asSupplier ? "e.g. Out of stock" : "Let the supplier know why" },
    });
    if (reason === null) return;
    await run("cancel", () => checkoutApi.cancelOrder(orderId, reason), asSupplier ? "Order declined" : "Order cancelled");
  }

  if (!order && !error) return <LoadingEntity entity="order" className="py-8" />;
  if (!order) {
    return (
      <div className="tb-docs">
        <FeedbackBanner tone="error" title="Couldn't open order">
          {error}
        </FeedbackBanner>
        <div>
          <BackLink href={ROUTES.orders}>Orders</BackLink>
        </div>
      </div>
    );
  }

  const pay = order.payment;
  const payBadge = paymentView(pay?.method ?? order.payment_method, order.payment_status);
  const isSupplier = type === "supplier";
  const isBuyer = type === "buyer";
  const pending = order.status === "pending";
  const canConfirm = isSupplier && pending && hasPermission("orders.confirm");
  const canDecline = isSupplier && pending && hasPermission("orders.cancel");
  const canBuyerCancel = isBuyer && pending && hasPermission("orders.cancel");
  const canShip =
    isSupplier && ["confirmed", "processing", "shipped"].includes(order.status) && hasPermission("shipments.update");
  const openShipment = order.shipments.find((s) => !["delivered", "failed"].includes(s.status)) ?? order.shipments[0];

  return (
    <div className="tb-docs tb-doc--po">
      {dialog}
      <OrderDocToolbar order={order} />

      {order.status === "cancelled" && order.rejection_reason ? (
        <FeedbackBanner tone="warning" title="This order was cancelled">
          {order.rejection_reason}
        </FeedbackBanner>
      ) : null}

      {isSupplier && pending ? (
        <FeedbackBanner tone="info" title="New order">
          {order.payment_method === "cash"
            ? "The buyer pays in cash on delivery. Confirm the order to start preparing it."
            : "The buyer has paid. Confirm the order to start preparing it."}
        </FeedbackBanner>
      ) : null}

      {order.timeline?.length ? (
        <InventoryPanel title="Progress" action={<StatusBadge status={order.status} />}>
          <OrderTimeline steps={order.timeline} />
        </InventoryPanel>
      ) : null}

      <div className="tb-docs-split">
        <OrderDocument order={order} />

        <aside className="grid gap-4">
          {canConfirm || canDecline || canBuyerCancel || canShip || (isBuyer && openShipment) ? (
            <InventoryPanel title="Next step">
              <div className="grid gap-2">
                {canConfirm ? (
                  <InventoryBtn busy={busy === "confirm"} onClick={() => void acceptOrder()} className="w-full">
                    Confirm order
                  </InventoryBtn>
                ) : null}
                {canShip ? (
                  <InventoryLinkBtn href={ROUTES.trackingOrder(order.id)} className="w-full">
                    Ship &amp; set delivery date
                  </InventoryLinkBtn>
                ) : null}
                {isBuyer && openShipment && openShipment.status !== "delivered" ? (
                  <InventoryLinkBtn href={ROUTES.procurementShipment(openShipment.id)} tone="soft" className="w-full">
                    Confirm delivery
                  </InventoryLinkBtn>
                ) : null}
                {canDecline ? (
                  <InventoryBtn tone="ghost" busy={busy === "cancel"} onClick={() => void cancelOrder(true)} className="w-full">
                    Decline order
                  </InventoryBtn>
                ) : null}
                {canBuyerCancel ? (
                  <InventoryBtn tone="ghost" busy={busy === "cancel"} onClick={() => void cancelOrder(false)} className="w-full">
                    Cancel order
                  </InventoryBtn>
                ) : null}
              </div>
            </InventoryPanel>
          ) : null}

          <EarningsPanel order={order} />

          <InventoryPanel title="Payment" action={<StatusBadge status={order.payment_status} label={payBadge.label} tone={payBadge.tone} />}>
            <dl className="tb-co-facts">
              <div>
                <dt>Method</dt>
                <dd>{paymentMethodLabel(pay?.method ?? order.payment_method)}</dd>
              </div>
              {pay?.amount_for_this_order ? (
                <div>
                  <dt>For this order</dt>
                  <dd>{formatMoney(pay.amount_for_this_order, order.currency)}</dd>
                </div>
              ) : null}
              {pay?.reference ? (
                <div>
                  <dt>Reference</dt>
                  <dd>{pay.reference}</dd>
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
            {!pay ? <p className="tb-co-note mt-2">No payment has been recorded for this order yet.</p> : null}
          </InventoryPanel>

          {order.invoice ? (
            <InventoryPanel title="Invoice" action={<StatusBadge status={order.invoice.status} />}>
              <dl className="tb-co-facts">
                <div>
                  <dt>Number</dt>
                  <dd>{order.invoice.invoice_number}</dd>
                </div>
                <div>
                  <dt>Total</dt>
                  <dd>{formatMoney(order.invoice.total, order.currency)}</dd>
                </div>
                {order.invoice.balance_due ? (
                  <div>
                    <dt>Still due</dt>
                    <dd>{formatMoney(order.invoice.balance_due, order.currency)}</dd>
                  </div>
                ) : null}
              </dl>
              <InventoryLinkBtn href={ROUTES.financeInvoice(order.invoice.id)} tone="soft" className="mt-3 w-full">
                View invoice
              </InventoryLinkBtn>
            </InventoryPanel>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
