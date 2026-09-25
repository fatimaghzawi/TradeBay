import { ROUTES } from "@/lib/constants";

export type WorkspaceKind = "buyer" | "supplier" | "platform";

export type NavIconKey =
  | "home"
  | "building"
  | "cart"
  | "messages"
  | "orders"
  | "finance"
  | "chart"
  | "catalog"
  | "truck"
  | "shield"
  | "spark"
  | "planner"
  | "users"
  | "roles"
  | "mail"
  | "help"
  | "settings"
  | "disputes"
  | "settlements"
  | "suppliers"
  | "audit"
  | "bell"
  | "quote";

export type NavItem = {
  key: string;
  label: string;
  href: string;
  icon: NavIconKey;
  
  permissions?: string[];
  
  group?: string;
  
  children?: NavItem[];
  
  hint?: string;
};

export type WorkspaceNav = {
  kind: WorkspaceKind;
  label: string;
  tagline: string;
  primary: NavItem[];
  secondary: NavItem[];
  searchPlaceholder: string;
};

export const COMPANY_SPACE_NAV: NavItem[] = [
  {
    key: "overview",
    label: "Overview",
    href: ROUTES.businesses,
    icon: "building",
    group: "Company",
    hint: "Your company on TradeBay",
  },
  {
    key: "profile",
    label: "Company profile",
    href: `${ROUTES.businesses}?tab=settings`,
    icon: "building",
    group: "Company",
    hint: "Business details and verification",
  },
  {
    key: "team",
    label: "Members",
    href: ROUTES.members,
    icon: "users",
    permissions: ["users.read"],
    group: "Team",
    hint: "People behind your business",
  },
  {
    key: "invites",
    label: "Invitations",
    href: ROUTES.invitations,
    icon: "mail",
    permissions: ["users.invite"],
    group: "Team",
    hint: "Bring people into the company",
  },
  {
    key: "roles",
    label: "Roles",
    href: ROUTES.roles,
    icon: "roles",
    permissions: ["roles.read"],
    group: "Access",
    hint: "Business responsibilities",
  },
  {
    key: "permissions",
    label: "Permissions",
    href: ROUTES.permissions,
    icon: "shield",
    permissions: ["roles.read"],
    group: "Access",
    hint: "What each responsibility can do",
  },
  {
    key: "sessions",
    label: "Sessions",
    href: ROUTES.sessions,
    icon: "shield",
    group: "Security",
    hint: "Devices signed into your account",
  },
  {
    key: "audit",
    label: "Audit trail",
    href: ROUTES.audit,
    icon: "audit",
    permissions: ["audit_logs.read"],
    group: "Security",
    hint: "Who did what, and when",
  },
];

export const COMPANY_NAV_GROUPS = ["Company", "Team", "Access", "Security"] as const;

export const BUYER_INVENTORY_NAV: NavItem[] = [
  {
    key: "inv-overview",
    label: "Browse",
    href: ROUTES.inventory,
    icon: "chart",
    permissions: ["products.read"],
    group: "Marketplace",
    hint: "Wholesale products available to order",
  },
  {
    key: "inv-products",
    label: "Products",
    href: ROUTES.inventoryProducts,
    icon: "catalog",
    permissions: ["products.read"],
    group: "Marketplace",
    hint: "Search listings and open details",
  },
  {
    key: "inv-categories",
    label: "Categories",
    href: ROUTES.inventoryCategories,
    icon: "building",
    permissions: ["categories.read"],
    group: "Marketplace",
    hint: "Shop products by category",
  },
  {
    key: "inv-suppliers",
    label: "Suppliers",
    href: ROUTES.suppliersDirectory,
    icon: "suppliers",
    permissions: ["products.read"],
    group: "Marketplace",
    hint: "Explore verified TradeBay partners",
  },
];

export const SUPPLIER_INVENTORY_NAV: NavItem[] = [
  {
    key: "inv-overview",
    label: "My catalog",
    href: ROUTES.inventory,
    icon: "chart",
    permissions: ["products.read"],
    group: "Catalog",
    hint: "Snapshot of your listings and stock",
  },
  {
    key: "inv-products",
    label: "My products",
    href: ROUTES.inventoryProducts,
    icon: "catalog",
    permissions: ["products.read"],
    group: "Catalog",
    hint: "Add, edit, and activate your listings",
  },
  {
    key: "inv-categories",
    label: "Categories",
    href: ROUTES.inventoryCategories,
    icon: "building",
    permissions: ["categories.read"],
    group: "Catalog",
    hint: "How products are organized",
  },
  {
    key: "inv-stock",
    label: "My stock",
    href: ROUTES.inventoryStock,
    icon: "truck",
    permissions: ["inventory.read"],
    group: "Stock",
    hint: "Available and reserved quantities",
  },
  {
    key: "inv-movements",
    label: "My movements",
    href: ROUTES.inventoryMovements,
    icon: "orders",
    permissions: ["inventory.read"],
    group: "Stock",
    hint: "History of stock changes on your listings",
  },
];

export const INVENTORY_SPACE_NAV = SUPPLIER_INVENTORY_NAV;

export const BUYER_INVENTORY_NAV_GROUPS = ["Marketplace"] as const;
export const SUPPLIER_INVENTORY_NAV_GROUPS = ["Catalog", "Stock"] as const;
export const INVENTORY_NAV_GROUPS = SUPPLIER_INVENTORY_NAV_GROUPS;

export const BUYER_COMMERCE_NAV: NavItem[] = [
  {
    key: "com-hub",
    label: "Overview",
    href: ROUTES.procurement,
    icon: "cart",
    permissions: ["rfqs.read"],
    group: "Buying",
    hint: "RFQs, awards, and next actions",
  },
  {
    key: "com-new-rfq",
    label: "Create RFQ",
    href: ROUTES.procurementNew,
    icon: "quote",
    permissions: ["rfqs.create"],
    group: "Buying",
    hint: "Select products and send requests to matched suppliers",
  },
  {
    key: "com-quotations",
    label: "Quotations",
    href: ROUTES.quotations,
    icon: "quote",
    permissions: ["rfqs.read"],
    group: "Buying",
    hint: "Compare and track supplier offers",
  },
  {
    key: "com-orders",
    label: "Orders",
    href: ROUTES.orders,
    icon: "orders",
    permissions: ["orders.read"],
    group: "Fulfilment",
    hint: "Checkouts and supplier orders",
  },
  {
    key: "com-tracking",
    label: "Track orders",
    href: ROUTES.tracking,
    icon: "truck",
    permissions: ["orders.read", "shipments.read"],
    group: "Fulfilment",
    hint: "Where each supplier order is",
  },
  {
    key: "com-finance",
    label: "Finance",
    href: ROUTES.finance,
    icon: "finance",
    permissions: ["invoices.read"],
    group: "Money",
    hint: "Invoices, payments and balance",
  },
];

export const SUPPLIER_COMMERCE_NAV: NavItem[] = [
  {
    key: "com-hub",
    label: "Overview",
    href: ROUTES.procurement,
    icon: "truck",
    permissions: ["rfqs.read", "orders.read"],
    group: "Pipeline",
    hint: "Invitations, quotes, and POs",
  },
  {
    key: "com-quotations",
    label: "Quotations",
    href: ROUTES.quotations,
    icon: "quote",
    permissions: ["rfqs.read"],
    group: "Pipeline",
    hint: "Draft and submit offers",
  },
  {
    key: "com-orders",
    label: "Orders",
    href: ROUTES.orders,
    icon: "orders",
    permissions: ["orders.read"],
    group: "Fulfilment",
    hint: "Checkouts and supplier orders",
  },
  {
    key: "com-tracking",
    label: "Track & ship",
    href: ROUTES.tracking,
    icon: "truck",
    permissions: ["orders.read", "shipments.read"],
    group: "Fulfilment",
    hint: "Where each supplier order is",
  },
  {
    key: "com-finance",
    label: "Finance",
    href: ROUTES.finance,
    icon: "finance",
    permissions: ["invoices.read"],
    group: "Money",
    hint: "Invoices, payments and balance",
  },
];

export const BUYER_COMMERCE_NAV_GROUPS = ["Buying", "Fulfilment", "Money"] as const;
export const SUPPLIER_COMMERCE_NAV_GROUPS = ["Pipeline", "Fulfilment", "Money"] as const;

export const BUYER_NAV: WorkspaceNav = {
  kind: "buyer",
  label: "Buyer workspace",
  tagline: "Company · Marketplace · Sourcing",
  searchPlaceholder: "Search products or team…",
  primary: [
    { key: "home", label: "Dashboard", href: ROUTES.dashboard, icon: "home" },
    {
      key: "business",
      label: "Company",
      href: ROUTES.businesses,
      icon: "building",
      children: COMPANY_SPACE_NAV,
    },
    {
      key: "inventory",
      label: "Marketplace",
      href: ROUTES.inventory,
      icon: "catalog",
      permissions: ["products.read"],
      children: BUYER_INVENTORY_NAV,
    },
    {
      key: "procurement",
      label: "Procurement",
      href: ROUTES.procurement,
      icon: "cart",
      permissions: ["rfqs.read"],
      children: BUYER_COMMERCE_NAV,
      hint: "RFQs, quotations, purchase orders, and receiving",
    },
  ],
  secondary: [],
};

export const SUPPLIER_NAV: WorkspaceNav = {
  kind: "supplier",
  label: "Supplier workspace",
  tagline: "Company · Inventory · Verification",
  searchPlaceholder: "Search team or inventory…",
  primary: [
    { key: "home", label: "Dashboard", href: ROUTES.dashboard, icon: "home" },
    {
      key: "business",
      label: "Company",
      href: ROUTES.businesses,
      icon: "building",
      children: COMPANY_SPACE_NAV,
    },
    {
      key: "inventory",
      label: "Inventory",
      href: ROUTES.inventory,
      icon: "catalog",
      permissions: ["products.read"],
      children: SUPPLIER_INVENTORY_NAV,
    },
    {
      key: "procurement",
      label: "Fulfilment",
      href: ROUTES.procurement,
      icon: "truck",
      permissions: ["rfqs.read", "orders.read"],
      children: SUPPLIER_COMMERCE_NAV,
      hint: "RFQ invitations, quotations, POs, and shipments",
    },
  ],
  secondary: [],
};

export const PLATFORM_NAV: WorkspaceNav = {
  kind: "platform",
  label: "Platform",
  tagline: "Admin Console",
  searchPlaceholder: "Search anything… (users, suppliers, orders, RFQs…)",
  primary: [
    {
      key: "home",
      label: "Overview",
      href: ROUTES.admin.home,
      icon: "home",
    },
    {
      key: "users",
      label: "Users",
      href: ROUTES.admin.users,
      icon: "users",
      permissions: ["users.read"],
      group: "Identity",
      hint: "Accounts, suspend, memberships",
    },
    {
      key: "buyers",
      label: "Buyers",
      href: ROUTES.admin.buyers,
      icon: "cart",
      permissions: ["businesses.read"],
      group: "Identity",
      hint: "Buyer companies",
    },
    {
      key: "supplier-companies",
      label: "Suppliers",
      href: `${ROUTES.admin.businesses}?type=supplier`,
      icon: "building",
      permissions: ["businesses.read"],
      group: "Identity",
      hint: "Supplier companies & domains",
    },
    {
      key: "suppliers",
      label: "Verifications",
      href: ROUTES.admin.suppliers,
      icon: "suppliers",
      permissions: ["suppliers.read", "suppliers.verify"],
      group: "Identity",
      hint: "Approve or reject selling rights",
    },
    {
      key: "roles",
      label: "Roles",
      href: ROUTES.admin.roles,
      icon: "roles",
      permissions: ["roles.read"],
      group: "Identity",
      hint: "Platform staff roles & permissions",
    },
    {
      key: "permissions",
      label: "Permissions",
      href: ROUTES.admin.permissions,
      icon: "roles",
      permissions: ["roles.read"],
      group: "Identity",
      hint: "Full permission catalog",
    },
    {
      key: "categories",
      label: "Categories",
      href: ROUTES.admin.categories,
      icon: "catalog",
      permissions: ["categories.manage", "categories.read"],
      group: "Catalog",
      hint: "Marketplace taxonomy & images",
    },
    {
      key: "products",
      label: "Products",
      href: ROUTES.admin.products,
      icon: "orders",
      permissions: ["products.read"],
      group: "Catalog",
      hint: "All supplier listings",
    },
    {
      key: "finance",
      label: "Overview",
      href: ROUTES.admin.finance,
      icon: "finance",
      permissions: ["settlements.read", "payables.read", "commissions.read"],
      group: "Finance",
      hint: "Where the platform's money is",
    },
    {
      key: "finance-payments",
      label: "Buyer payments",
      href: `${ROUTES.admin.finance}?section=payments`,
      icon: "finance",
      permissions: ["settlements.read", "payables.read"],
      group: "Finance",
    },
    {
      key: "finance-balances",
      label: "Supplier balances",
      href: `${ROUTES.admin.finance}?section=balances`,
      icon: "finance",
      permissions: ["payables.read", "settlements.read"],
      group: "Finance",
    },
    {
      key: "settlements",
      label: "Supplier payouts",
      href: ROUTES.admin.settlements,
      icon: "settlements",
      permissions: ["settlements.read", "settlements.approve", "payables.read"],
      group: "Finance",
    },
    {
      key: "finance-earnings",
      label: "Platform earnings",
      href: `${ROUTES.admin.finance}?section=earnings`,
      icon: "finance",
      permissions: ["commissions.read", "settlements.read"],
      group: "Finance",
    },
    {
      key: "finance-activity",
      label: "Financial activity",
      href: `${ROUTES.admin.finance}?section=activity`,
      icon: "audit",
      permissions: ["settlements.read"],
      group: "Finance",
    },
    {
      key: "audit",
      label: "System",
      href: ROUTES.admin.audit,
      icon: "audit",
      permissions: ["audit_logs.read"],
    },
    {
      key: "settings",
      label: "Settings",
      href: ROUTES.admin.settings,
      icon: "settings",
      permissions: ["settings.manage"],
    },
  ],
  secondary: [
    {
      key: "invites",
      label: "Invitations",
      href: ROUTES.invitations,
      icon: "mail",
      permissions: ["users.invite"],
    },
    { key: "account", label: "Account", href: ROUTES.settings, icon: "settings" },
  ],
};

export function isNavActive(pathname: string, href: string, search = "") {
  const [path, query] = href.split("?");
  if (query) {
    return pathname === path && search.includes(query);
  }
  
  if (path === ROUTES.businesses) {
    return (
      pathname === path &&
      (!search.includes("tab=") || search.includes("tab=overview"))
    );
  }
  
  if (path === ROUTES.inventory) {
    return pathname === path;
  }
  
  if (path === ROUTES.admin.businesses && !query) {
    return pathname === path && !search.includes("type=");
  }
  
  if (path === ROUTES.procurement) {
    return pathname === path;
  }
  if (path === "/dashboard" || path === "/admin") {
    return pathname === path;
  }
  if (path === ROUTES.admin.finance && !query) {
    return pathname === path && (!search.includes("section=") || search.includes("section=overview"));
  }
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function isNavItemActive(pathname: string, item: NavItem, search = ""): boolean {
  if (item.children?.length) {
    return (
      isNavActive(pathname, item.href, search) ||
      item.children.some((child) => isNavItemActive(pathname, child, search))
    );
  }
  return isNavActive(pathname, item.href, search);
}

export function isCompanySpacePath(pathname: string) {
  return COMPANY_SPACE_NAV.some((item) => isNavActive(pathname, item.href));
}

export function isInventorySpacePath(pathname: string) {
  if (pathname === ROUTES.inventory || pathname.startsWith(`${ROUTES.inventory}/`)) {
    return true;
  }
  if (pathname === ROUTES.catalog || pathname.startsWith(`${ROUTES.catalog}/`)) {
    return true;
  }
  
  if (
    pathname === ROUTES.suppliersDirectory ||
    pathname.startsWith(`${ROUTES.suppliersDirectory}/`)
  ) {
    return true;
  }
  return false;
}

export function isCommerceSpacePath(pathname: string) {
  const prefixes = [
    ROUTES.procurement,
    ROUTES.orders,
    ROUTES.checkout,
    ROUTES.tracking,
    ROUTES.quotations,
    ROUTES.finance,
  ];
  return prefixes.some(
    (href) => pathname === href || pathname.startsWith(`${href}/`),
  );
}

export function filterNavItems(
  items: NavItem[],
  hasPermission: (code: string) => boolean,
): NavItem[] {
  return items
    .map((item) => ({
      ...item,
      children: item.children
        ? filterNavItems(item.children, hasPermission)
        : undefined,
    }))
    .filter((item) => {
      if (item.children && item.children.length > 0) return true;
      if (!item.permissions?.length) return true;
      return item.permissions.some((code) => hasPermission(code));
    });
}

export function resolveWorkspaceKind(
  businessType: string | null | undefined,
  pathname: string,
): WorkspaceKind {
  if (pathname.startsWith("/admin")) return "platform";
  if (businessType === "platform") return "platform";
  if (businessType === "supplier") return "supplier";
  return "buyer";
}

export function getWorkspaceNav(kind: WorkspaceKind): WorkspaceNav {
  if (kind === "platform") return PLATFORM_NAV;
  if (kind === "supplier") return SUPPLIER_NAV;
  return BUYER_NAV;
}

export function canEditRolePermissions(
  role: {
    name: string;
    is_system_role: boolean;
  },
  options?: { fullControl?: boolean },
): boolean {
  if (options?.fullControl) return true;
  return role.name !== "Business Admin";
}
