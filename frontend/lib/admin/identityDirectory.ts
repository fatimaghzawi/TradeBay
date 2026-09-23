import type { Business, PlatformUser } from "@/lib/api/identityApi";

export function formatBusinessAddress(business: Business): string {
  const a = business.address;
  if (!a) return "—";
  return (
    [a.street, a.city, a.district, a.governorate, a.postal_code, a.country]
      .filter(Boolean)
      .join(", ") || "—"
  );
}

export function platformUserName(user: PlatformUser): string {
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || "Unknown user";
}

export function statusTone(
  status: string | null | undefined,
): "ok" | "wait" | "off" | "bad" {
  const s = (status || "").toLowerCase();
  if (s === "active" || s === "verified") return "ok";
  if (s === "pending" || s === "invited") return "wait";
  if (s === "suspended" || s === "rejected" || s === "revoked" || s === "deactivated")
    return "bad";
  return "off";
}
