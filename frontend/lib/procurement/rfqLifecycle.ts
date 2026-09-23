import type { RFQItem, SupplierRequest } from "@/lib/api/procurementApi";

export const RFQ_STAGE_LABEL: Record<string, string> = {
  matched: "Will receive this RFQ",
  received: "RFQ received",
  awaiting_quotation: "Waiting for quotation",
  quoted: "Quotation submitted",
  negotiating: "Negotiation active",
  accepted: "Accepted — order created",
  rejected: "Quotation rejected",
  declined: "Declined the request",
  withdrawn: "Quotation withdrawn",
};

export const RFQ_STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  published: "Sent",
  responding: "Suppliers responding",
  negotiating: "Negotiating",
  awarded: "Deal confirmed",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const ORDER_STATUS_LABEL: Record<string, string> = {
  draft: "Draft PO",
  pending: "Issued",
  confirmed: "Confirmed",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  completed: "Completed",
  cancelled: "Cancelled",
  disputed: "Disputed",
};

/** Buyer-facing fulfilment stages (excludes draft / terminal branches). */
export const ORDER_TRACK_STAGES = [
  "pending",
  "confirmed",
  "processing",
  "shipped",
  "delivered",
  "completed",
] as const;

export const SHIPMENT_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  preparing: "Preparing",
  shipped: "Shipped",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  failed: "Failed",
};

export function formatEta(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Soonest open shipment ETA, else latest delivery timestamp. */
export function orderArrivalHint(
  shipments: {
    status: string;
    estimated_delivery_at?: string | null;
    delivered_at?: string | null;
  }[],
): { label: string; at: string | null } {
  const open = shipments.filter((s) => s.status !== "delivered" && s.status !== "failed");
  const withEta = open
    .filter((s) => s.estimated_delivery_at)
    .sort(
      (a, b) =>
        new Date(a.estimated_delivery_at!).getTime() -
        new Date(b.estimated_delivery_at!).getTime(),
    );
  if (withEta[0]?.estimated_delivery_at) {
    return { label: "Estimated arrival", at: withEta[0].estimated_delivery_at };
  }
  const delivered = shipments
    .filter((s) => s.delivered_at)
    .sort(
      (a, b) =>
        new Date(b.delivered_at!).getTime() - new Date(a.delivered_at!).getTime(),
    );
  if (delivered[0]?.delivered_at) {
    return { label: "Arrived", at: delivered[0].delivered_at };
  }
  return { label: "Estimated arrival", at: null };
}

export function groupItemsBySupplier(items: RFQItem[]) {
  const map = new Map<
    string,
    { supplier_business_id: string | null; supplier_name: string; items: RFQItem[] }
  >();
  for (const item of items) {
    const key = item.supplier_business_id || "unassigned";
    const existing = map.get(key);
    if (existing) {
      existing.items.push(item);
      continue;
    }
    map.set(key, {
      supplier_business_id: item.supplier_business_id ?? null,
      supplier_name: item.supplier_name || "Supplier to confirm",
      items: [item],
    });
  }
  return [...map.values()];
}

export function stageLabel(stage: string | null | undefined) {
  if (!stage) return "Pending";
  return RFQ_STAGE_LABEL[stage] || stage.replaceAll("_", " ");
}

export function statusLabel(status: string | null | undefined) {
  if (!status) return "—";
  return RFQ_STATUS_LABEL[status] || status;
}

export function unmatchedRequestsFromItems(items: RFQItem[]): SupplierRequest[] {
  return groupItemsBySupplier(items).map((group) => ({
    supplier_business_id: group.supplier_business_id,
    supplier_name: group.supplier_name,
    invite_status: null,
    quotation_id: null,
    quotation_status: null,
    stage: group.supplier_business_id ? "matched" : "matched",
    products: group.items.map((item) => ({
      id: item.id,
      product_name: item.product_name,
      quantity: item.quantity,
      unit: item.unit,
      primary_image_url: item.primary_image_url,
    })),
  }));
}
