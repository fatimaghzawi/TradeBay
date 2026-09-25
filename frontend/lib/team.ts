export const ROLE_BLURBS: Record<string, string> = {
  "Business Admin": "Full access to manage the business.",
  "Sales Manager": "Manage products, quotations, and orders.",
  "Sales Representative": "Create RFQs, manage quotations, and orders.",
  Finance: "View invoices, payments, and financial reports.",
  Viewer: "Read-only access.",
};

export function roleBlurb(name: string | null | undefined): string {
  if (!name) return "Access comes from their role.";
  return ROLE_BLURBS[name] ?? "Permissions come from this role.";
}

export function memberDisplayName(member: {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
}): string {
  const full = `${member.first_name ?? ""} ${member.last_name ?? ""}`.trim();
  return full || member.email || "Member";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0] ?? "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  const second = parts[1] ?? "";
  return `${first[0] ?? ""}${second[0] ?? ""}`.toUpperCase() || "?";
}

export function formatJoined(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export { statusTone, type StatusTone } from "@/lib/status";
