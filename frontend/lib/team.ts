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

export type StatusTone = "active" | "pending" | "removed" | "suspended" | "expired" | "neutral";

export function statusTone(status: string): StatusTone {
  const key = status.toLowerCase();
  if (key === "active" || key === "accepted") return "active";
  if (key === "pending" || key === "invited") return "pending";
  if (key === "removed" || key === "revoked" || key === "declined") return "removed";
  if (key === "suspended") return "suspended";
  if (key === "expired") return "expired";
  return "neutral";
}

export const STATUS_BADGE_CLASS: Record<StatusTone, string> = {
  active: "bg-[#e8f6ef] text-[#1a6b4f]",
  pending: "bg-[#e8ebe6] text-[#8a4b2a]",
  removed: "bg-[#f4f6f5] text-[#5a6a62]",
  suspended: "bg-[#fef3f2] text-[#b42318]",
  expired: "bg-[#f4f6f5] text-[#5a6a62]",
  neutral: "bg-[#f4f6f5] text-[#5a6a62]",
};
