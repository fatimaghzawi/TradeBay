import { ROUTES } from "@/lib/constants";

/** Login with post-auth redirect into a protected TradeBay surface. */
export function loginNext(path: string) {
  return `${ROUTES.login}?next=${encodeURIComponent(path)}`;
}

/** Register, optionally carrying a destination after signup. */
export function registerNext(path?: string) {
  if (!path) return ROUTES.register;
  return `${ROUTES.register}?next=${encodeURIComponent(path)}`;
}

/**
 * Landing CTAs — explore routes are guest-friendly;
 * transactional flows still go through auth with next=.
 */
export const LP = {
  home: ROUTES.home,
  login: ROUTES.login,
  register: ROUTES.register,
  /** Browse the product marketplace (guest OK) */
  marketplace: ROUTES.marketplace,
  /** Category directory (guest OK) */
  categories: ROUTES.inventoryCategories,
  /** Open marketplace after creating an account */
  marketplaceSignup: registerNext(ROUTES.marketplace),
  /** Supplier directory (guest OK) */
  suppliers: ROUTES.suppliersDirectory,
  /** Buyer RFQ / procurement desk */
  procurement: loginNext(ROUTES.procurementNew),
  /** AI business planner (guest OK) */
  planner: ROUTES.businessPlannerNew,
  /** AI sourcing assistant */
  aiSourcing: loginNext(ROUTES.aiSourcing),
  /** Create company (supplier onboarding path) — login then new business */
  createBusiness: loginNext(ROUTES.businessesNew),
  /** New accounts that intend to sell */
  becomeSupplier: registerNext(ROUTES.businessesNew),
  terms: ROUTES.terms,
  privacy: ROUTES.privacy,
  /** In-page story anchors */
  section: {
    categories: "#categories",
    paths: "#paths",
    buyers: "#paths",
    suppliers: "#paths",
    featured: "#featured",
    story: "#trade-story",
  },
} as const;

export function marketplaceSearch(query: string) {
  return `${ROUTES.marketplace}?q=${encodeURIComponent(query)}`;
}
