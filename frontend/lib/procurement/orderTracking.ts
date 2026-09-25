import type { PurchaseOrder, Shipment, ShipmentSummary } from "@/lib/api/procurementApi";
import { SHIPMENT_STATUS_LABEL } from "@/lib/procurement/rfqLifecycle";

export function primaryShipment(
  shipments: ShipmentSummary[],
): ShipmentSummary | null {
  if (!shipments.length) return null;
  const open = shipments.find((s) => s.status !== "delivered" && s.status !== "failed");
  return open || shipments[shipments.length - 1] || null;
}

export function remainingQty(item: PurchaseOrder["items"][number]): number {
  const ordered = Number(item.quantity) || 0;
  const shipped = Number(item.shipped_quantity) || 0;
  return Math.max(ordered - shipped, 0);
}

export type TrackingEvent = { label: string; description: string; at: string | null };

const ORDER_EVENT: Record<string, { label: string; description: string }> = {
  awaiting_payment: { label: "Order placed", description: "Waiting for your card payment" },
  pending: { label: "Order placed", description: "Sent to the supplier for confirmation" },
  confirmed: { label: "Supplier confirmed", description: "The supplier accepted the order" },
  processing: { label: "Preparing", description: "The supplier is preparing your goods" },
  shipped: { label: "Shipped", description: "Your goods left the supplier" },
  delivered: { label: "Delivered", description: "Delivery was confirmed" },
  completed: { label: "Completed", description: "The order is complete" },
  cancelled: { label: "Cancelled", description: "The order was cancelled" },
};

export function recordedEvents(order: PurchaseOrder, shipment: Shipment | null): TrackingEvent[] {
  const events: TrackingEvent[] = [];
  for (const h of order.status_history || []) {
    const copy = ORDER_EVENT[h.status];
    if (!copy) continue;
    events.push({ label: copy.label, description: h.note || copy.description, at: h.changed_at });
  }
  for (const ev of shipment?.tracking_events || []) {
    events.push({
      label: SHIPMENT_STATUS_LABEL[ev.status] || ev.status.replaceAll("_", " "),
      description: [ev.description, ev.location].filter(Boolean).join(" · ") || "Shipment update",
      at: ev.occurred_at,
    });
  }
  return events.sort((a, b) => new Date(b.at || 0).getTime() - new Date(a.at || 0).getTime());
}
