export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const APP_NAME = "TradeBay";

export const DOMAIN_NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/catalog", label: "Catalog" },
  { href: "/procurement", label: "Procurement" },
  { href: "/finance", label: "Finance" },
  { href: "/trust", label: "Trust" },
  { href: "/settings", label: "Settings" },
] as const;
