

import type { PlanSectionId } from "@/features/business-planner/constants";

export const PLANNER_STEPS = [
  "goal",
  "location",
  "budget",
  "preferences",
  "adaptive",
  "generating",
] as const;

export function canContinueGoal(goal: string | null, unsure: boolean) {
  return Boolean(goal) || unsure;
}

export function formatPlanMoney(
  value: string | number | null | undefined,
  currency = "USD",
): string {
  if (value == null || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return `${currency === "USD" ? "$" : ""}${value}`;
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `$${n.toFixed(2)}`;
  }
}

export function sourceBadge(source: string | null | undefined) {
  if (source === "MARKETPLACE") return "TradeBay data";
  if (source === "AI_ESTIMATE") return "AI estimate";
  return source || "Estimate";
}

export function resolveNextActionSection(key: string): PlanSectionId | "sourcing" {
  switch (key) {
    case "suppliers":
      return "suppliers";
    case "products":
      return "products";
    case "budget":
      return "budget";
    case "sourcing":
      return "sourcing";
    case "launch":
      return "launch";
    case "finance":
      return "finance";
    case "risks":
      return "risks";
    default:
      return "overview";
  }
}

export function toggleListValue(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
}

export const SESSION_STORAGE_KEY = "tb.businessPlanner.sessionId";
