export const queryKeys = {
  me: ["auth", "me"] as const,
  businesses: ["identity", "businesses"] as const,
  products: ["catalog", "products"] as const,
  rfqs: ["procurement", "rfqs"] as const,
  orders: ["procurement", "orders"] as const,
  invoices: ["finance", "invoices"] as const,
  conversations: ["communication", "conversations"] as const,
  negotiations: ["negotiation", "list"] as const,
  sourcingRequests: ["ai-sourcing", "requests"] as const,
  businessPlans: ["business-planner", "plans"] as const,
};
