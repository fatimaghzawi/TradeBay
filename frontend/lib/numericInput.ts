/** Shared sanitizers so price / quantity fields never accept letters. */

export type NumericKind = "integer" | "decimal";

const NAV_KEYS = new Set([
  "Backspace",
  "Delete",
  "Tab",
  "Escape",
  "Enter",
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
]);

export function sanitizeNumericInput(
  raw: string,
  kind: NumericKind = "decimal",
  maxDecimals = 2,
): string {
  if (!raw) return "";
  const next = raw.replace(/,/g, "").replace(/[^\d.]/g, "");
  if (kind === "integer") return next.replace(/\./g, "");

  const dot = next.indexOf(".");
  if (dot === -1) return next;
  const whole = next.slice(0, dot);
  const frac = next.slice(dot + 1).replace(/\./g, "").slice(0, maxDecimals);
  if (frac.length === 0 && next.endsWith(".")) return `${whole}.`;
  return frac.length ? `${whole}.${frac}` : whole;
}

export function blockNonNumericKeys(
  event: { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; preventDefault: () => void; currentTarget: { value: string } },
  kind: NumericKind,
) {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (NAV_KEYS.has(event.key)) return;
  if (kind === "decimal" && event.key === ".") {
    if (event.currentTarget.value.includes(".")) event.preventDefault();
    return;
  }
  if (!/^\d$/.test(event.key)) event.preventDefault();
}

export function formatMoneyAmount(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "0.00";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
