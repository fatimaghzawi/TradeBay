import type { Permission } from "@/lib/api/identityApi";

export const MODULE_LABELS: Record<string, string> = {
  users: "Team",
  roles: "Roles",
  permissions: "Permissions",
  invitations: "Invitations",
  businesses: "Company",
  audit_logs: "Audit",
  sessions: "Sessions",
  suppliers: "Suppliers",
  products: "Products",
  catalog: "Catalog",
  rfqs: "RFQs",
  quotations: "Quotations",
  orders: "Orders",
  finance: "Finance",
  messages: "Messages",
  negotiations: "Negotiations",
};

export const MODULE_QUESTIONS: Record<string, string> = {
  users: "Who can manage people?",
  roles: "Who can define responsibilities?",
  permissions: "Who can view access rules?",
  invitations: "Who can invite teammates?",
  businesses: "Who can edit the company?",
  audit_logs: "Who can review security activity?",
  sessions: "Who can manage sign-in sessions?",
  suppliers: "Who can review suppliers?",
  products: "Who can manage products?",
  catalog: "Who can manage the catalog?",
  rfqs: "Who can manage sourcing requests?",
  quotations: "Who can manage quotations?",
  orders: "Who can manage orders?",
  finance: "Who can access financial information?",
  messages: "Who can message counterparties?",
  negotiations: "Who can negotiate deals?",
};

const ACTION_VERBS: Record<string, string> = {
  read: "View",
  create: "Create",
  update: "Update",
  delete: "Delete",
  invite: "Invite",
  remove: "Remove",
  manage: "Manage",
  verify: "Verify",
  suspend: "Suspend",
};

export function moduleLabel(resource: string): string {
  return MODULE_LABELS[resource] ?? resource.replace(/_/g, " ");
}

export function moduleQuestion(resource: string): string {
  return MODULE_QUESTIONS[resource] ?? `Who can work with ${moduleLabel(resource).toLowerCase()}?`;
}

export function permissionTitle(permission: Permission): string {
  const verb = ACTION_VERBS[permission.action] ?? permission.action;
  const subject = moduleLabel(permission.resource);
  return `${verb} ${subject.toLowerCase()}`;
}

export function groupPermissionsByModule(
  catalog: Permission[],
): [string, Permission[]][] {
  const map = new Map<string, Permission[]>();
  for (const permission of catalog) {
    const list = map.get(permission.resource) ?? [];
    list.push(permission);
    map.set(permission.resource, list);
  }
  return [...map.entries()].sort(([a], [b]) =>
    moduleLabel(a).localeCompare(moduleLabel(b)),
  );
}

export function accessModulesFromCodes(codes: string[]): {
  label: string;
  allowed: boolean;
}[] {
  const modules = ["rfqs", "quotations", "products", "orders", "finance", "users"];
  const set = new Set(codes.map((c) => c.split(".")[0]));
  return modules.map((mod) => ({
    label: moduleLabel(mod),
    allowed: set.has(mod),
  }));
}
