import { ApiError } from "@/lib/api/client";
import type { StatusTone } from "@/lib/status";

export function formatMoney(amount: string | null | undefined, currency?: string | null): string {
  if (amount == null || amount === "") return "—";
  const raw = String(amount).trim();
  const negative = raw.startsWith("-");
  const unsigned = negative ? raw.slice(1) : raw;
  const [whole = "0", frac = ""] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const cents = (frac + "00").slice(0, 2);
  const body = `${grouped}.${cents}`;
  const prefix = currency ? `${currency} ` : "";
  return negative ? `−${prefix}${body}` : `${prefix}${body}`;
}

function toCents(amount: string | null | undefined): bigint {
  const raw = String(amount ?? "0").trim() || "0";
  const negative = raw.startsWith("-");
  const [whole = "0", frac = ""] = (negative ? raw.slice(1) : raw).split(".");
  const cents = BigInt(`${whole || "0"}${(frac + "00").slice(0, 2)}`);
  return negative ? -cents : cents;
}

export function sumMoney(amounts: (string | null | undefined)[]): string {
  const total = amounts.reduce((acc, a) => acc + toCents(a), BigInt(0));
  const negative = total < BigInt(0);
  const abs = (negative ? -total : total).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${abs.slice(0, -2)}.${abs.slice(-2)}`;
}

export function formatRate(rate: string | null | undefined): string | null {
  if (rate == null || rate === "") return null;
  const [whole = "0", frac = ""] = String(rate).split(".");
  const padded = frac.padEnd(2, "0");
  const intPart = String(Number(`${whole}${padded.slice(0, 2)}`));
  const rest = padded.slice(2).replace(/0+$/, "");
  return `${intPart}${rest ? `.${rest}` : ""}%`;
}

export function isPositive(amount: string | null | undefined): boolean {
  if (!amount) return false;
  return /[1-9]/.test(String(amount)) && !String(amount).trim().startsWith("-");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function paymentMethodLabel(method: string | null | undefined): string {
  if (method === "cash") return "Cash on delivery";
  if (method === "card") return "Card";
  if (method === "manual") return "Recorded payment";
  if (!method) return "—";
  return method.replaceAll("_", " ");
}

export function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export function initials(name: string | null | undefined): string {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "");
  return letters.join("") || "•";
}

type BadgeView = { label: string; tone: StatusTone };

export function paymentView(method: string | null | undefined, status: string | null | undefined): BadgeView {
  switch (status) {
    case "completed":
    case "paid":
      return { label: method === "cash" ? "Cash received" : "Paid", tone: "ok" };
    case "failed":
      return { label: "Payment failed", tone: "bad" };
    case "cancelled":
      return { label: "Cancelled", tone: "off" };
    case "refunded":
      return { label: "Refunded", tone: "off" };
    case "awaiting_cash":
      return { label: "Pay on delivery", tone: "wait" };
    default:
      return method === "cash"
        ? { label: "Pay on delivery", tone: "wait" }
        : { label: "Awaiting payment", tone: "wait" };
  }
}

export function checkoutView(status: string, method: string): BadgeView {
  if (status === "paid") return { label: method === "cash" ? "Paid in cash" : "Paid", tone: "ok" };
  if (status === "cancelled") return { label: "Cancelled", tone: "off" };
  return method === "cash" ? { label: "Pay on delivery", tone: "wait" } : { label: "Awaiting payment", tone: "wait" };
}

export const LEDGER_ENTRY_LABEL: Record<string, string> = {
  sale: "Buyer paid TradeBay",
  platform_fee: "TradeBay fee",
  funds_released: "Ready to pay you",
  payout: "Paid to you",
  adjustment: "Adjustment",
};
