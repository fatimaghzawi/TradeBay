/** Query keys for identity/auth and Domain 2 catalog. */
export const queryKeys = {
  me: ["auth", "me"] as const,
  businesses: ["identity", "businesses"] as const,
  products: ["catalog", "products"] as const,
  categories: ["catalog", "categories"] as const,
  inventory: ["catalog", "inventory"] as const,
  rfqs: ["procurement", "rfqs"] as const,
  orders: ["procurement", "orders"] as const,
  invoices: ["finance", "invoices"] as const,
  conversations: ["communication", "conversations"] as const,
  conversation: (id: string) => ["communication", "conversation", id] as const,
  conversationMessages: (id: string) =>
    ["communication", "messages", id] as const,
  negotiations: ["negotiation", "list"] as const,
  negotiation: (id: string) => ["negotiation", id] as const,
  reviewByOrder: (orderId: string) => ["trust", "review", orderId] as const,
  sourcingRequests: ["ai-sourcing", "requests"] as const,
  businessPlans: ["business-planner", "plans"] as const,
};
