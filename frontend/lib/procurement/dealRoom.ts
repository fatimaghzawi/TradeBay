export type DealBeat = "brief" | "quote" | "table" | "close";

export function dealMoney(currency: string, value?: string | null) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return `${currency} ${value}`;
  return `${currency} ${n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function dealInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean).slice(0, 2);
  const letters = parts.map((part) => part[0]?.toUpperCase() || "").join("");
  return letters || "?";
}

export function dealBeat(status: string, hasQuote: boolean, negotiating: boolean): DealBeat {
  if (status === "awarded") return "close";
  if (negotiating || status === "negotiating") return "table";
  if (hasQuote || status === "responding") return "quote";
  return "brief";
}

export function priceDelta(quoted?: string | null, target?: string | null) {
  const a = Number(quoted);
  const b = Number(target);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return null;
  const diff = a - b;
  const pct = (diff / b) * 100;
  return { diff, pct, under: diff < 0, even: Math.abs(diff) < 0.005 };
}
