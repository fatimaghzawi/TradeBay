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

export { statusTone } from "@/lib/status";
