"use client";

import { ApiError } from "@/lib/api/client";
import {
  businessPlannerApi,
  type BusinessPlan,
} from "@/lib/api/businessPlannerApi";
import { resolveNextActionSection } from "@/lib/businessPlanner";
import type { PlanSectionId } from "@/features/business-planner/constants";
import { useCallback, useEffect, useState } from "react";

export function useBusinessPlan(planId: string) {
  const [plan, setPlan] = useState<BusinessPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [section, setSection] = useState<PlanSectionId>("overview");

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await businessPlannerApi.getPlan(planId);
      setPlan(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load plan");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    setLoading(true);
    void load();
  }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  function handleNextAction(key: string) {
    const target = resolveNextActionSection(key);
    if (target === "sourcing") {
      setSection("products");
      return;
    }
    setSection(target);
  }

  async function markMilestone(order: number) {
    await run(async () => {
      const updated = await businessPlannerApi.patchPlan(planId, {
        milestone_updates: [{ order, status: "COMPLETE" }],
      });
      setPlan(updated);
      setInfo("Milestone marked complete.");
    });
  }

  return {
    plan,
    busy,
    loading,
    error,
    info,
    setInfo,
    section,
    setSection,
    handleNextAction,
    markMilestone,
    reload: load,
  };
}
