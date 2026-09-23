import type { Conversation } from "@/lib/api/communicationApi";
import { ROUTES } from "@/lib/constants";

export function chatTitle(c: Conversation) {
  return c.counterparty_name || c.subject || "Conversation";
}

export function chatContextLabel(c: Conversation) {
  const ctx = (c.context_type || "").toLowerCase();
  if (ctx === "rfq") return "RFQ";
  if (ctx === "order") return "Order";
  if (ctx === "quotation") return "Quote";
  if (ctx === "negotiation") return "Bargain";
  if ((c.type || "").toUpperCase() === "DIRECT") return "Direct";
  return c.type || "Chat";
}

export function chatContextHref(c: Conversation): string | null {
  if (!c.context_id) return null;
  if (c.context_type === "rfq") return ROUTES.procurementRfq(c.context_id);
  if (c.context_type === "order") return ROUTES.procurementOrder(c.context_id);
  return null;
}

export function chatRelativeTime(iso: string | null) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "Now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function chatClock(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function chatActiveId(pathname: string) {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] !== "conversations") return null;
  const id = parts[1];
  return id && /^[a-f0-9]{24}$/i.test(id) ? id : null;
}
