export const APP_NAME = "TradeBay";

export const ROUTES = {
  home: "/",
  login: "/login",
  register: "/register",
  forgotPassword: "/forgot-password",
  verifyEmail: "/verify-email",
  resetPassword: "/reset-password",
  members: "/members",
  invitations: "/invitations",
  roles: "/roles",
  acceptInvitation: "/accept-invitation",
  dashboard: "/dashboard",
  catalog: "/catalog",
  marketplace: "/catalog",
  procurement: "/procurement",
  finance: "/finance",
  trust: "/trust",
  settings: "/settings",
  conversations: "/conversations",
  businessPlanner: "/business-planner",
  aiSourcing: "/ai-sourcing",
  admin: {
    businesses: "/admin/businesses",
    suppliers: "/admin/suppliers",
    disputes: "/admin/disputes",
    settlements: "/admin/settlements",
  },
} as const;

export const DOMAIN_NAV = [
  { href: ROUTES.dashboard, label: "Overview", key: "dashboard" },
  { href: ROUTES.catalog, label: "Marketplace", key: "marketplace" },
  { href: ROUTES.procurement, label: "Procurement", key: "procurement" },
  { href: ROUTES.conversations, label: "Conversations", key: "conversations" },
  { href: ROUTES.aiSourcing, label: "AI Sourcing", key: "ai-sourcing" },
  { href: ROUTES.businessPlanner, label: "Business Planner", key: "business-planner" },
  { href: ROUTES.finance, label: "Finance", key: "finance" },
  { href: ROUTES.trust, label: "Trust", key: "trust" },
  { href: ROUTES.settings, label: "Settings", key: "settings" },
  { href: ROUTES.members, label: "Members", key: "members" },
  { href: ROUTES.roles, label: "Roles", key: "roles" },
  { href: ROUTES.invitations, label: "Invitations", key: "invitations" },
] as const;

export const DASHBOARD_DOMAINS = [
  {
    key: "identity",
    title: "Identity",
    description: "Users, businesses, memberships, and permissions.",
    href: ROUTES.settings,
  },
  {
    key: "marketplace",
    title: "Marketplace",
    description: "Products, pricing, and supplier listings.",
    href: ROUTES.catalog,
  },
  {
    key: "procurement",
    title: "Procurement",
    description: "RFQs, quotations, orders, and fulfillment.",
    href: ROUTES.procurement,
  },
  {
    key: "communication",
    title: "Communication",
    description: "Conversations and messages between buyers and suppliers.",
    href: ROUTES.conversations,
  },
  {
    key: "negotiation",
    title: "Negotiation",
    description: "Offer / counter-offer workspace linked to conversations.",
    href: ROUTES.conversations,
  },
  {
    key: "ai-sourcing",
    title: "AI Sourcing",
    description: "Natural-language sourcing requests and recommendations.",
    href: ROUTES.aiSourcing,
  },
  {
    key: "business-planner",
    title: "Business Planner",
    description: "Plan opening inventory and estimated costs.",
    href: ROUTES.businessPlanner,
  },
] as const;
