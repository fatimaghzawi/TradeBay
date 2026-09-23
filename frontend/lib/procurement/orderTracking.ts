import type { PurchaseOrder, ShipmentSummary } from "@/lib/api/procurementApi";
import { formatEta, orderArrivalHint } from "@/lib/procurement/rfqLifecycle";

/** Shein-style package journey stages shown to the buyer. */
export const JOURNEY_STAGES = [
  {
    id: "ordered",
    label: "Ordered",
    blurb: "Deal confirmed",
  },
  {
    id: "packing",
    label: "Packaging",
    blurb: "Being prepared",
  },
  {
    id: "driving",
    label: "In transit",
    blurb: "On its way",
  },
  {
    id: "nearby",
    label: "Near you",
    blurb: "Delivery window",
  },
  {
    id: "arrived",
    label: "Delivered",
    blurb: "With you",
  },
] as const;

export type JourneyStageId = (typeof JOURNEY_STAGES)[number]["id"];

type ShipLike = Pick<
  ShipmentSummary,
  "status" | "estimated_delivery_at" | "shipped_at" | "delivered_at"
> & {
  created_at?: string | null;
  received_at?: string | null;
};

/**
 * Display stage is automatic — suppliers do not click each mile.
 * Uses shipment + ETA clock (Shein-style), not manual status taps.
 */
export function journeyStageIndex(
  order: PurchaseOrder,
  primary?: ShipLike | null,
  nowMs: number = Date.now(),
): number {
  if (
    order.status === "completed" ||
    order.status === "delivered" ||
    primary?.status === "delivered" ||
    primary?.received_at ||
    primary?.delivered_at
  ) {
    return 4;
  }

  if (!primary) {
    if (order.status === "confirmed" || order.status === "processing") return 1;
    return 0;
  }

  const shippedMs = parseTime(primary.shipped_at) ?? parseTime(primary.created_at) ?? nowMs;
  const etaMs = parseTime(primary.estimated_delivery_at);

  // Just left the warehouse — brief packing beat, then on the road.
  if (nowMs - shippedMs < 30 * 60 * 1000 && !etaMs) return 1;

  if (etaMs && etaMs > shippedMs) {
    const span = etaMs - shippedMs;
    const elapsed = Math.max(0, nowMs - shippedMs);
    const ratio = elapsed / span;
    if (ratio >= 0.85 || nowMs >= etaMs) return 3; // near you / ETA window
    if (ratio >= 0.08) return 2; // on the road
    return 1; // packing / leaving warehouse
  }

  // Shipped without a usable ETA — treat as in transit until buyer confirms.
  return 2;
}

function parseTime(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : t;
}

export function journeyHeadline(stageIdx: number, isBuyer: boolean): string {
  const copy = [
    isBuyer ? "Order confirmed — waiting for the supplier to prepare." : "Acknowledge the PO, then dispatch with an ETA.",
    isBuyer ? "Supplier is preparing your goods." : "Dispatch when ready and set the estimated arrival.",
    isBuyer ? "Shipment is in transit toward you." : "In transit — progress follows the ETA automatically.",
    isBuyer ? "Delivery window is open." : "ETA window — buyer should receive soon.",
    isBuyer ? "Delivered — fulfilment complete." : "Delivery complete.",
  ];
  return copy[Math.min(stageIdx, copy.length - 1)] ?? copy[0] ?? "";
}

/** Synthetic journey milestones for the log (auto, not supplier-tapped). */
export function autoJourneyEvents(
  order: PurchaseOrder,
  primary: ShipLike | null,
  stageIdx: number,
  nowMs: number = Date.now(),
): { label: string; description: string; at: string | null }[] {
  const events: { label: string; description: string; at: string | null }[] = [];
  const issued = order.confirmed_at || order.created_at;
  events.push({
    label: "Ordered",
    description: "Purchase order confirmed on TradeBay",
    at: issued,
  });

  if (stageIdx < 1 && !primary) return events;

  if (order.status === "confirmed" || order.status === "processing" || primary) {
    events.push({
      label: "Packaging",
      description: primary
        ? "Supplier prepared the package for dispatch"
        : "Supplier is preparing your goods",
      at: primary?.shipped_at || order.confirmed_at || issued,
    });
  }

  if (!primary || stageIdx < 2) return events;

  const shippedAt = primary.shipped_at || primary.created_at || null;
  events.push({
    label: "On the road",
    description: "Package left the warehouse",
    at: shippedAt,
  });

  const etaMs = parseTime(primary.estimated_delivery_at);
  const shippedMs = parseTime(shippedAt) ?? nowMs;

  if (stageIdx >= 3 && etaMs) {
    const nearMs = shippedMs + (etaMs - shippedMs) * 0.85;
    events.push({
      label: "Near you",
      description: "Approaching delivery — ETA window open",
      at: new Date(Math.min(nearMs, nowMs)).toISOString(),
    });
  }

  if (stageIdx >= 4) {
    events.push({
      label: "Delivered",
      description: "Package arrived",
      at: primary.delivered_at || primary.received_at || new Date(nowMs).toISOString(),
    });
  }

  return events.reverse();
}

export function primaryShipment(
  shipments: ShipmentSummary[],
): ShipmentSummary | null {
  if (!shipments.length) return null;
  const open = shipments.find((s) => s.status !== "delivered" && s.status !== "failed");
  return open || shipments[shipments.length - 1] || null;
}

export function trackingCardMeta(order: PurchaseOrder) {
  const primary = primaryShipment(order.shipments || []);
  const stageIdx = journeyStageIndex(order, primary);
  const stage = JOURNEY_STAGES[stageIdx] ?? JOURNEY_STAGES[0]!;
  const arrival = orderArrivalHint(order.shipments || []);
  return {
    primary,
    stageIdx,
    stage,
    etaLabel: formatEta(arrival.at),
    arrivalLabel: arrival.label,
  };
}

export function remainingQty(item: PurchaseOrder["items"][number]): number {
  const ordered = Number(item.quantity) || 0;
  const shipped = Number(item.shipped_quantity) || 0;
  return Math.max(ordered - shipped, 0);
}
