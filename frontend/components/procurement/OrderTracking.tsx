"use client";

import { OrderTimeline, TimelineIcon, timelineHeadline } from "@/components/commerce/OrderTimeline";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { BusyText, LoadingEntity } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import {
  procurementApi,
  type PurchaseOrder,
  type PurchaseOrderSummary,
  type Shipment,
} from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { primaryShipment, recordedEvents, remainingQty } from "@/lib/procurement/orderTracking";
import { SHIPMENT_STATUS_LABEL, formatEta, orderArrivalHint } from "@/lib/procurement/rfqLifecycle";
import { statusLabel } from "@/lib/status";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

const UNTRACKABLE = new Set(["draft", "awaiting_payment"]);

function headlineCopy(key: string | undefined, isBuyer: boolean, isCash: boolean): string {
  switch (key) {
    case "paid":
      return isBuyer ? "Waiting for your payment to be confirmed." : "Waiting for the buyer's payment.";
    case "confirmed":
      return isBuyer ? "Waiting for the supplier to confirm your order." : "Confirm the order to start preparing it.";
    case "shipped":
      return isBuyer ? "The supplier is preparing your goods." : "Ship the goods and set a delivery date.";
    case "delivered":
      return isBuyer
        ? "Your goods are on the way. Confirm delivery when they arrive."
        : "On the way. The buyer confirms delivery on arrival.";
    case "completed":
      if (isBuyer) return isCash ? "Delivered. Have the cash ready for the supplier if you haven't paid yet." : "Delivered.";
      return "Delivered. The order closes once receipt is confirmed.";
    case "cancelled":
      return "This order was cancelled.";
    default:
      return isBuyer ? "Your order is complete." : "Order complete.";
  }
}

function MiniSteps({ order }: { order: PurchaseOrder }) {
  const steps = (order.timeline || []).filter((s) => s.state !== "cancelled");
  return (
    <div className="tb-shein-card__mini" aria-hidden>
      {steps.map((s) => (
        <span key={s.key} data-on={s.state === "done" || undefined} data-now={s.state === "current" || undefined}>
          <TimelineIcon step={s.key} />
        </span>
      ))}
    </div>
  );
}

export function TrackingHub() {
  const { business } = useAuth();
  const isBuyer = business?.type === "buyer";
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const page = await procurementApi.listOrders({ page_size: 50 });
        const trackable = page.data.filter((o) => !UNTRACKABLE.has(o.status) && o.status !== "cancelled");
        const detailed = await Promise.all(
          trackable.slice(0, 24).map(async (summary: PurchaseOrderSummary) => {
            try {
              return await procurementApi.getOrder(summary.id);
            } catch {
              return null;
            }
          }),
        );
        setOrders(detailed.filter((o): o is PurchaseOrder => o !== null));
        setError(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't load tracking");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="tb-shein">
      <DirectoryMast
        title={isBuyer ? "Track my orders" : "Track & ship"}
        size="page"
        mark="Tracking"
        lede={
          isBuyer
            ? "Each supplier ships separately, so every order has its own progress."
            : "Confirm, ship and follow each order until the buyer receives it."
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <LoadingEntity entity="orders" className="py-8" />
      ) : orders.length === 0 ? (
        <div className="tb-shein-empty">
          <h2>No orders to track</h2>
          <p>
            {isBuyer
              ? "Orders appear here once they're placed with a supplier."
              : "New orders appear here as soon as buyers place them."}
          </p>
          <Link href={ROUTES.orders} className="tb-btn tb-btn--primary">
            Open orders
          </Link>
        </div>
      ) : (
        <ul className="tb-shein-list">
          {orders.map((order) => {
            const head = timelineHeadline(order.timeline);
            const arrival = orderArrivalHint(order.shipments || []);
            const eta = formatEta(arrival.at);
            const peer = isBuyer ? order.supplier_name || "Supplier" : order.buyer_name || "Buyer";
            return (
              <li key={order.id}>
                <Link href={ROUTES.trackingOrder(order.id)} className="tb-shein-card">
                  <div className="tb-shein-card__top">
                    <div>
                      <strong>{order.order_number}</strong>
                      <span>{peer}</span>
                    </div>
                    <em>{head?.state === "current" ? `Next: ${head.label}` : head?.label ?? statusLabel(order.status)}</em>
                  </div>
                  <MiniSteps order={order} />
                  <p className="tb-shein-card__eta">
                    {eta ? `${arrival.label} · ${eta}` : isBuyer ? "Delivery date set when shipped" : "Set a delivery date when you ship"}
                  </p>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

type JourneyProps = { orderId: string };

export function TrackingJourney({ orderId }: JourneyProps) {
  const { business, hasPermission } = useAuth();
  const isBuyer = business?.type === "buyer";
  const isSupplier = business?.type === "supplier";

  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [carrierName, setCarrierName] = useState("");
  const [origin, setOrigin] = useState("");
  const [etaLocal, setEtaLocal] = useState("");
  const [shipNotes, setShipNotes] = useState("");

  async function load() {
    try {
      const data = await procurementApi.getOrder(orderId);
      setOrder(data);
      const primary = primaryShipment(data.shipments || []);
      if (primary) {
        try {
          setShipment(await procurementApi.getShipment(primary.id));
        } catch {
          setShipment(null);
        }
      } else {
        setShipment(null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load tracking");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  const shippableLines = useMemo(() => {
    if (!order) return [];
    return order.items
      .map((item) => ({ item, remaining: remainingQty(item) }))
      .filter((row) => row.remaining > 0);
  }, [order]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That step didn't complete. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!order && !error) return <LoadingEntity entity="tracking" />;
  if (!order) {
    return (
      <FeedbackBanner tone="error" title="Tracking unavailable">
        {error}
      </FeedbackBanner>
    );
  }

  const primary = primaryShipment(order.shipments || []);
  const head = timelineHeadline(order.timeline);
  const arrived = ["delivered", "completed"].includes(order.status);
  const cancelled = order.status === "cancelled";
  const eta = formatEta(shipment?.estimated_delivery_at) || formatEta(primary?.estimated_delivery_at) || null;
  const isCash = order.payment_method === "cash";
  const events = recordedEvents(order, shipment);
  const headKey = cancelled ? "cancelled" : head?.state === "current" ? head.key : undefined;
  const title = cancelled
    ? "Cancelled"
    : head?.state === "current"
      ? `Next: ${head.label}`
      : head?.label ?? statusLabel(order.status);

  const canAcknowledge = isSupplier && order.status === "pending" && hasPermission("orders.confirm");
  const canCreateShipment =
    isSupplier &&
    ["confirmed", "processing", "shipped"].includes(order.status) &&
    shippableLines.length > 0 &&
    hasPermission("shipments.update");

  return (
    <div className="tb-shein tb-shein--detail">
      <div className="tb-shein-nav">
        <BackLink href={ROUTES.tracking}>All orders</BackLink>
        <div className="tb-shein-nav__actions">
          <Link href={ROUTES.procurementOrder(order.id)} className="tb-btn tb-btn--secondary">
            Order details
          </Link>
          {primary ? (
            <Link href={ROUTES.procurementShipment(primary.id)} className="tb-btn tb-btn--secondary">
              {isBuyer && !arrived ? "Confirm delivery" : "Shipment"}
            </Link>
          ) : null}
        </div>
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}

      <section className="tb-shein-status">
        <div className="tb-shein-status__badge" aria-hidden>
          <TimelineIcon step={head?.key ?? "placed"} />
        </div>
        <div className="tb-shein-status__copy">
          <p className="tb-shein-kicker">
            {order.order_number} · {isBuyer ? order.supplier_name : order.buyer_name}
          </p>
          <h1>{title}</h1>
          <p>{headlineCopy(headKey, Boolean(isBuyer), isCash)}</p>
        </div>
        <div className="tb-shein-status__eta">
          <span>{arrived ? "Delivered" : "Estimated arrival"}</span>
          <strong>
            {arrived
              ? formatEta(primary?.delivered_at) || "Complete"
              : cancelled
                ? "—"
                : eta || "Set when shipped"}
          </strong>
          <em>
            {statusLabel(order.status)}
            {primary?.carrier_name ? ` · ${primary.carrier_name}` : ""}
          </em>
        </div>
      </section>

      <OrderTimeline steps={order.timeline} />

      <div className="tb-shein-split">
        <section className="tb-shein-panel">
          <h2>Tracking history</h2>
          {events.length === 0 ? (
            <p className="tb-shein-hint">Updates appear here as the order moves.</p>
          ) : (
            <ol className="tb-shein-timeline">
              {events.map((ev, i) => (
                <li key={`${ev.label}-${ev.at}-${i}`} data-first={i === 0 || undefined}>
                  <span className="tb-shein-timeline__dot" />
                  <div>
                    <strong>{ev.label}</strong>
                    <p>{ev.description}</p>
                    <time>{ev.at ? new Date(ev.at).toLocaleString() : ""}</time>
                  </div>
                </li>
              ))}
            </ol>
          )}

          {(order.shipments || []).length > 1 ? (
            <>
              <h3>Shipments</h3>
              <ul className="tb-shein-ships">
                {order.shipments.map((s) => (
                  <li key={s.id}>
                    <Link href={ROUTES.procurementShipment(s.id)}>
                      <strong>{s.shipment_number}</strong>
                      <span>{SHIPMENT_STATUS_LABEL[s.status] || s.status}</span>
                      <span>{s.estimated_delivery_at ? `ETA ${formatEta(s.estimated_delivery_at)}` : "No ETA"}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>

        <section className="tb-shein-panel">
          <h2>Items</h2>
          <ul className="tb-shein-items">
            {order.items.map((item) => (
              <li key={item.id}>
                <strong>{item.product_name_snapshot}</strong>
                <span>
                  {item.quantity} {item.unit}
                  {item.shipped_quantity && Number(item.shipped_quantity) > 0 ? ` · ${item.shipped_quantity} shipped` : ""}
                </span>
              </li>
            ))}
          </ul>

          {canAcknowledge ? (
            <div className="tb-shein-actions">
              <button
                type="button"
                className="tb-btn tb-btn--primary"
                disabled={busy}
                onClick={() => void run(() => procurementApi.acknowledgeOrder(orderId).then(() => undefined))}
              >
                <BusyText busy={busy}>Confirm order</BusyText>
              </button>
            </div>
          ) : null}

          {canCreateShipment ? (
            <div className="tb-shein-actions">
              <h3>Ship</h3>
              <p className="tb-shein-hint">Enter the delivery date so the buyer knows when to expect it.</p>
              <label>
                Carrier
                <input
                  value={carrierName}
                  onChange={(e) => setCarrierName(e.target.value)}
                  placeholder="Aramex, local courier…"
                />
              </label>
              <label>
                Origin
                <input value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="Warehouse / city" />
              </label>
              <label>
                Estimated arrival
                <input type="datetime-local" value={etaLocal} onChange={(e) => setEtaLocal(e.target.value)} />
              </label>
              <label>
                Notes
                <input value={shipNotes} onChange={(e) => setShipNotes(e.target.value)} />
              </label>
              <button
                type="button"
                className="tb-btn tb-btn--primary"
                disabled={busy || !etaLocal}
                onClick={() =>
                  void run(async () => {
                    await procurementApi.createShipment(orderId, {
                      carrier_name: carrierName.trim() || undefined,
                      origin: origin.trim() || undefined,
                      estimated_delivery_at: new Date(etaLocal).toISOString(),
                      shipping_notes: shipNotes.trim() || undefined,
                      lines: shippableLines.map(({ item, remaining }) => ({
                        order_item_id: item.id,
                        quantity: String(remaining),
                      })),
                    });
                    setCarrierName("");
                    setOrigin("");
                    setEtaLocal("");
                    setShipNotes("");
                  })
                }
              >
                <BusyText busy={busy}>Mark as shipped</BusyText>
              </button>
            </div>
          ) : null}

          {isSupplier && primary && !canCreateShipment && !arrived ? (
            <p className="tb-shein-hint">Shipped. Add carrier updates from the shipment page. The buyer confirms delivery.</p>
          ) : null}

          {isBuyer && order.status === "pending" ? (
            <p className="tb-shein-hint">Waiting for the supplier to confirm your order.</p>
          ) : null}

          {isBuyer && primary && !arrived ? (
            <p className="tb-shein-hint">When the goods arrive, open the shipment to confirm delivery.</p>
          ) : null}
        </section>
      </div>
    </div>
  );
}
