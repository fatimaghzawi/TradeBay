

export const GUEST_ALLOWED_PREFIXES = [
  "/suppliers",
  "/business-planner",
  "/inventory/products",
  "/inventory/categories",
  "/catalog",
] as const;

export function isGuestAllowedPath(pathname: string): boolean {
  return GUEST_ALLOWED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
