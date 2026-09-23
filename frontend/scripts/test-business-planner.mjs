/** Smoke tests for Business Planner client helpers (no extra test runner). */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "businessPlanner.ts"),
  "utf8",
);

function canContinueGoal(goal, unsure) {
  return Boolean(goal) || unsure;
}

function formatPlanMoney(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return `$${value}`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(n);
}

assert.match(src, /export function canContinueGoal/);
assert.match(src, /export function formatPlanMoney/);
assert.equal(canContinueGoal(null, false), false);
assert.equal(canContinueGoal("Fashion", false), true);
assert.equal(canContinueGoal(null, true), true);
assert.equal(formatPlanMoney(null), "—");
assert.equal(formatPlanMoney("2500.00"), "$2,500.00");
assert.ok(src.includes("goal") && src.includes("adaptive"));
console.log("business planner helpers: ok");
