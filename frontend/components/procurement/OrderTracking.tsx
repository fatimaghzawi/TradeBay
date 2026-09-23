"use client";

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
import {
  JOURNEY_STAGES,
  autoJourneyEvents,
  journeyHeadline,
  journeyStageIndex,
  primaryShipment,
  remainingQty,
  trackingCardMeta,
  type JourneyStageId,
} from "@/lib/procurement/orderTracking";
import {
  ORDER_STATUS_LABEL,
  SHIPMENT_STATUS_LABEL,
  formatEta,
} from "@/lib/procurement/rfqLifecycle";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

/** Clean stroke icons — Shein-style, not illustrated scenes. */
function StageIcon({ id }: { id: JourneyStageId }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (id) {
    case "ordered":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M7 4h10v16H7z" {...common} />
          <path d="M9 8h6M9 12h6M9 16h4" {...common} />
        </svg>
      );
    case "packing":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5v-7Z" {...common} />
          <path d="M12 12v8M4 8.5 12 12l8-3.5" {...common} />
        </svg>
      );
    case "driving":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M3 13h11V8H3v5Z" {...common} />
          <path d="M14 13h3.5L20 16v3h-6v-6Z" {...common} />
          <circle cx="7" cy="19" r="1.6" {...common} />
          <circle cx="17" cy="19" r="1.6" {...common} />
        </svg>
      );
    case "nearby":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M12 21s6.5-5.2 6.5-10.2a6.5 6.5 0 1 0-13 0C5.5 15.8 12 21 12 21Z" {...common} />
          <circle cx="12" cy="10.8" r="2.2" {...common} />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="8" {...common} />
          <path d="m8.5 12.2 2.4 2.4 4.6-5" {...common} />
        </svg>
      );
  }
}

function JourneyStepper({ stageIdx }: { stageIdx: number }) {
  const fillPct = (stageIdx / (JOURNEY_STAGES.length - 1)) * 100;
  return (
    <div className="tb-shein-stepper">
      <div className="tb-shein-stepper__line" aria-hidden>
        <span style={{ width: `${fillPct}%` }} />
      </div>
      <ol className="tb-shein-stepper__list">
        {JOURNEY_STAGES.map((stage, i) => (
          <li
            key={stage.id}
            data-done={i < stageIdx || undefined}
            data-current={i === stageIdx || undefined}
            data-todo={i > stageIdx || undefined}
          >
            <span className="tb-shein-stepper__icon">
              <StageIcon id={stage.id} />
            </span>
            <strong>{stage.label}</strong>
            <em>{stage.blurb}</em>
          </li>
        ))}
      </ol>
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
        const trackable = page.data.filter((o) => !["draft", "cancelled"].includes(o.status));
        const detailed = await Promise.all(
          trackable.slice(0, 24).map(async (summary: PurchaseOrderSummary) => {
            try {
              return await procurementApi.getOrder(summary.id);
            } catch {
              return {
                ...summary,
                subtotal: summary.total,
                discount_total: "0",
                charge_total: "0",
                tax_total: "0",
                payment_terms: null,
                delivery_terms: null,
                payment_status: null,
                shipping_address: null,
                rejection_reason: null,
                status_history: [],
                items: [],
                shipments: [],
              } satisfies PurchaseOrder;
            }
          }),
        );
        setOrders(detailed);
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
      <header className="tb-shein-hero">
        <p className="tb-shein-kicker">Tracking</p>
        <h1>{isBuyer ? "Track my orders" : "Track & ship"}</h1>
        <p>
          {isBuyer
            ? "See where each order is and when it should arrive."
            : "Dispatch once with an ETA — progress updates automatically."}
        </p>
      </header>

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
              ? "Issued purchase orders appear here once fulfilment starts."
              : "Acknowledge a PO and dispatch with an ETA to begin."}
          </p>
          <Link href={ROUTES.orders} className="tb-inv-btn tb-inv-btn-accent">
            Open purchase orders
          </Link>
        </div>
      ) : (
        <ul className="tb-shein-list">
          {orders.map((order) => {
            const meta = trackingCardMeta(order);
            const peer = isBuyer ? order.supplier_name || "Supplier" : order.buyer_name || "Buyer";
            return (
              <li key={order.id}>
                <Link href={ROUTES.trackingOrder(order.id)} className="tb-shein-card">
                  <div className="tb-shein-card__top">
                    <div>
                      <strong>{order.order_number}</strong>
                      <span>{peer}</span>
                    </div>
                    <em>{meta.stage?.label ?? "Tracking"}</em>
                  </div>
                  <div className="tb-shein-card__mini" aria-hidden>
                    {JOURNEY_STAGES.map((stage, i) => (
                      <span
                        key={stage.id}
                        data-on={i <= meta.stageIdx || undefined}
                        data-now={i === meta.stageIdx || undefined}
                      >
                        <StageIcon id={stage.id} />
                      </span>
                    ))}
                  </div>
                  <p className="tb-shein-card__eta">
                    {meta.etaLabel
                      ? `${meta.arrivalLabel} · ${meta.etaLabel}`
                      : isBuyer
                        ? "ETA pending dispatch"
                        : "Set ETA when you dispatch"}
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
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

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
  const shipLike = shipment
    ? {
        status: shipment.status,
        estimated_delivery_at: shipment.estimated_delivery_at,
        shipped_at: shipment.shipped_at,
        delivered_at: shipment.delivered_at,
        received_at: shipment.received_at,
      }
    : primary;
  const stageIdx = journeyStageIndex(order, shipLike, nowMs);
  const eta =
    formatEta(primary?.estimated_delivery_at) ||
    formatEta(shipment?.estimated_delivery_at) ||
    null;
  const headline = journeyHeadline(stageIdx, Boolean(isBuyer));
  const journeyLog = autoJourneyEvents(order, shipLike, stageIdx, nowMs);
  const stage = JOURNEY_STAGES[stageIdx] ?? JOURNEY_STAGES[0];
  if (!stage) return null;

  const canAcknowledge =
    isSupplier && order.status === "pending" && hasPermission("orders.confirm");
  const canCreateShipment =
    isSupplier &&
    ["confirmed", "processing", "shipped"].includes(order.status) &&
    shippableLines.length > 0 &&
    hasPermission("shipments.update");

  return (
    <div className="tb-shein tb-shein--detail">
      <div className="tb-shein-nav">
        <Link href={ROUTES.tracking}>← All orders</Link>
        <div className="tb-shein-nav__actions">
          <Link href={ROUTES.procurementOrder(order.id)} className="tb-inv-btn tb-inv-btn-soft">
            Purchase order
          </Link>
          {primary ? (
            <Link
              href={ROUTES.procurementShipment(primary.id)}
              className="tb-inv-btn tb-inv-btn-soft"
            >
              Shipment
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
          <StageIcon id={stage.id} />
        </div>
        <div className="tb-shein-status__copy">
          <p className="tb-shein-kicker">{order.order_number}</p>
          <h1>{stage.label}</h1>
          <p>{headline}</p>
        </div>
        <div className="tb-shein-status__eta">
          <span>{stageIdx >= 4 ? "Arrived" : "Estimated arrival"}</span>
          <strong>
            {stageIdx >= 4
              ? formatEta(primary?.delivered_at) || "Complete"
              : eta || "Awaiting dispatch"}
          </strong>
          <em>
            {ORDER_STATUS_LABEL[order.status] || order.status}
            {primary?.carrier_name ? ` · ${primary.carrier_name}` : ""}
          </em>
        </div>
      </section>

      <JourneyStepper stageIdx={stageIdx} />

      <div className="tb-shein-split">
        <section className="tb-shein-panel">
          <h2>Tracking history</h2>
          <ol className="tb-shein-timeline">
            {journeyLog.map((ev, i) => (
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

          {(order.shipments || []).length > 1 ? (
            <>
              <h3>Shipments</h3>
              <ul className="tb-shein-ships">
                {order.shipments.map((s) => (
                  <li key={s.id}>
                    <Link href={ROUTES.procurementShipment(s.id)}>
                      <strong>{s.shipment_number}</strong>
                      <span>{SHIPMENT_STATUS_LABEL[s.status] || s.status}</span>
                      <span>
                        {s.estimated_delivery_at
                          ? `ETA ${formatEta(s.estimated_delivery_at)}`
                          : "No ETA"}
                      </span>
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
                  {item.shipped_quantity ? ` · ${item.shipped_quantity} shipped` : ""}
                </span>
              </li>
            ))}
          </ul>

          {canAcknowledge ? (
            <div className="tb-shein-actions">
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
                disabled={busy}
                onClick={() =>
                  void run(() =>
                    procurementApi.acknowledgeOrder(orderId).then(() => undefined),
                  )
                }
              >
                <BusyText busy={busy}>Confirm purchase order</BusyText>
              </button>
            </div>
          ) : null}

          {canCreateShipment ? (
            <div className="tb-shein-actions">
              <h3>Dispatch</h3>
              <p className="tb-shein-hint">
                One step: ship and set ETA. Tracking then advances on its own.
              </p>
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
                <input
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  placeholder="Warehouse / city"
                />
              </label>
              <label>
                Estimated arrival
                <input
                  type="datetime-local"
                  value={etaLocal}
                  onChange={(e) => setEtaLocal(e.target.value)}
                />
              </label>
              <label>
                Notes
                <input value={shipNotes} onChange={(e) => setShipNotes(e.target.value)} />
              </label>
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
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
                <BusyText busy={busy}>Dispatch &amp; set ETA</BusyText>
              </button>
            </div>
          ) : null}

          {isSupplier && primary && !canCreateShipment ? (
            <p className="tb-shein-hint">
              Dispatched. Stages follow the ETA. Buyer confirms receipt on arrival.
            </p>
          ) : null}

          {isBuyer && stageIdx < 1 ? (
            <p className="tb-shein-hint">
              Waiting for the supplier to acknowledge and dispatch.
            </p>
          ) : null}

          {isBuyer && primary && stageIdx >= 3 && stageIdx < 4 ? (
            <p className="tb-shein-hint">
              Near delivery — open the shipment to confirm receipt when goods arrive.
            </p>
          ) : null}
        </section>
      </div>
    </div>
  );
}
