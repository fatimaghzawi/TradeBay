export const PLANNER_GOALS = [
  "Retail Store",
  "Online Store",
  "Wholesale Business",
  "Distribution Business",
  "Food & Beverage",
  "Fashion",
  "Electronics",
  "Beauty & Cosmetics",
  "Home & Furniture",
  "Construction Supplies",
  "Automotive",
  "Agriculture",
  "Other",
] as const;

export const BUDGET_OPTIONS = [
  { value: "under_1000", label: "< $1,000" },
  { value: "1000_3000", label: "$1,000–$3,000" },
  { value: "3000_5000", label: "$3,000–$5,000" },
  { value: "5000_10000", label: "$5,000–$10,000" },
  { value: "10000_25000", label: "$10,000–$25,000" },
  { value: "25000_plus", label: "$25,000+" },
  { value: "unknown", label: "I don't know yet" },
] as const;

export const PRODUCT_PREFS = [
  "Fast-moving products",
  "High-margin products",
  "Low-MOQ products",
  "Premium products",
  "Affordable products",
  "Seasonal products",
  "Essential products",
  "Trending products",
] as const;

export const BUSINESS_MODELS = [
  "Online",
  "Physical store",
  "Both",
  "Wholesale",
  "Distribution",
  "Service + products",
] as const;

export const CUSTOMER_TYPES = [
  "Retail shoppers",
  "Restaurants / HORECA",
  "Other businesses (B2B)",
  "Distributors",
  "Mixed",
] as const;

export const CATEGORY_HINTS = [
  "Food & beverages",
  "Household",
  "Personal care",
  "Electronics",
  "Fashion",
  "Construction",
  "Automotive",
  "Agriculture",
  "Office supplies",
] as const;

export const DISCOVERY_STEPS = [
  "goal",
  "location",
  "budget",
  "preferences",
  "adaptive",
  "generating",
] as const;

export type DiscoveryStep = (typeof DISCOVERY_STEPS)[number];

export const PLAN_SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "products", label: "Products" },
  { id: "budget", label: "Budget" },
  { id: "suppliers", label: "Suppliers" },
  { id: "launch", label: "Launch" },
  { id: "finance", label: "Financials" },
  { id: "risks", label: "Risks" },
] as const;

export type PlanSectionId = (typeof PLAN_SECTIONS)[number]["id"];

export const BUDGET_KEYS = [
  "inventory",
  "equipment",
  "rent",
  "marketing",
  "logistics",
  "operations",
  "reserve",
  "working_capital",
] as const;
