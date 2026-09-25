import { ROUTES } from "@/lib/constants";

export function loginNext(path: string) {
  return `${ROUTES.login}?next=${encodeURIComponent(path)}`;
}

export function registerNext(path?: string) {
  if (!path) return ROUTES.register;
  return `${ROUTES.register}?next=${encodeURIComponent(path)}`;
}

export const LP = {
  home: ROUTES.home,
  login: ROUTES.login,
  register: ROUTES.register,
  
  marketplace: ROUTES.marketplace,
  
  categories: ROUTES.inventoryCategories,
  
  marketplaceSignup: registerNext(ROUTES.marketplace),
  
  suppliers: ROUTES.suppliersDirectory,
  
  procurement: loginNext(ROUTES.procurementNew),
  
  planner: ROUTES.businessPlannerNew,
  
  aiSourcing: loginNext(ROUTES.aiSourcing),
  
  createBusiness: loginNext(ROUTES.businessesNew),
  
  becomeSupplier: registerNext(ROUTES.businessesNew),
  terms: ROUTES.terms,
  privacy: ROUTES.privacy,
  
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
