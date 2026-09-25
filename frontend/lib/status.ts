
export type StatusTone = "ok" | "wait" | "bad" | "info" | "off";

const TONES: Record<string, StatusTone> = {};

function assign(tone: StatusTone, keys: string[]) {
  for (const key of keys) TONES[key] = tone;
}

assign("ok", [
  "active",
  "ok",
  "published",
  "submitted",
  "confirmed",
  "accepted",
  "approved",
  "paid",
  "received",
  "completed",
  "delivered",
  "awarded",
  "shipped",
  "settled",
  "closed",
  "verified",
  "in_stock",
  "operational",
  "recognized",
  "released",
  "processed",
  "posted",
  "credit",
]);

assign("wait", [
  "draft",
  "pending",
  "pending_verification",
  "low",
  "low_stock",
  "invited",
  "viewed",
  "open",
  "sent",
  "under_review",
  "in_review",
  "processing",
  "in_transit",
  "negotiating",
  "countered",
  "partially_shipped",
  "partially_received",
  "awaiting_payment",
  "awaiting_cash",
  "issued",
  "unpaid",
  "partially_paid",
  "held",
  "requires_attention",
]);

assign("bad", [
  "rejected",
  "out",
  "out_of_stock",
  "cancelled",
  "canceled",
  "declined",
  "failed",
  "disputed",
  "overdue",
  "suspended",
  "revoked",
  "deactivated",
  "blocked",
]);

assign("off", ["inactive", "removed", "expired", "archived", "unverified", "neutral", "void", "reversed"]);

const LABELS: Record<string, string> = {
  awaiting_payment: "Awaiting payment",
  awaiting_cash: "Cash on delivery",
  partially_paid: "Partly paid",
  void: "Voided",
  requires_attention: "Needs review",
};

export function statusKey(status: string | null | undefined): string {
  return (status ?? "").trim().toLowerCase().replaceAll(" ", "_").replaceAll("-", "_");
}

export function statusTone(status: string | null | undefined): StatusTone {
  return TONES[statusKey(status)] ?? "off";
}

export function statusLabel(status: string | null | undefined): string {
  const key = statusKey(status);
  if (!key) return "—";
  if (LABELS[key]) return LABELS[key];
  return key
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
