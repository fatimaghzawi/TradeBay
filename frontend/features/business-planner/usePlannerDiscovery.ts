"use client";

import { ApiError } from "@/lib/api/client";
import {
  businessPlannerApi,
  type AdaptiveQuestion,
  type PlannerSession,
} from "@/lib/api/businessPlannerApi";
import { ROUTES } from "@/lib/constants";
import {
  canContinueGoal,
  SESSION_STORAGE_KEY,
} from "@/lib/businessPlanner";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  DISCOVERY_STEPS,
  type DiscoveryStep,
} from "@/features/business-planner/constants";

function stepIndex(step: DiscoveryStep) {
  return DISCOVERY_STEPS.indexOf(step);
}

function hydrateFromSession(session: PlannerSession) {
  const prefs = session.preferences || {};
  const answers = session.answers || {};
  return {
    goal: (prefs.business_goal as string | null) ?? null,
    unsure: Boolean(prefs.unsure_goal),
    location: (prefs.location as string) || "Beirut",
    budgetRange: (prefs.budget_range as string) || "5000_10000",
    inventoryBudget: (prefs.inventory_budget as string) || "",
    operatingCash: (prefs.operating_cash as string) || "",
    businessModel: Array.isArray(prefs.business_model) ? prefs.business_model : [],
    experience: (prefs.experience as string) || "Beginner",
    timeCommitment: (prefs.time_commitment as string) || "Part-time",
    risk: (prefs.risk_preference as string) || "Balanced",
    monthlyIncome: (prefs.desired_monthly_income as string) || "",
    margin: (prefs.desired_margin as string) || "20-30%",
    productPrefs: Array.isArray(prefs.product_preferences)
      ? prefs.product_preferences
      : ["Essential products", "Low-MOQ products"],
    customerType: (prefs.customer_type as string) || "",
    categoryHints: Array.isArray(prefs.category_hints) ? prefs.category_hints : [],
    adaptiveAnswers: (answers.adaptive as Record<string, string | string[]>) || {},
    step: (["goal", "location", "budget", "preferences", "adaptive"].includes(
      session.current_step,
    )
      ? session.current_step
      : "goal") as DiscoveryStep,
  };
}

export function usePlannerDiscovery() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<DiscoveryStep>("goal");
  const [session, setSession] = useState<PlannerSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingSession, setLoadingSession] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [goal, setGoal] = useState<string | null>(null);
  const [unsure, setUnsure] = useState(false);
  const [location, setLocation] = useState("Beirut");
  const [customLocation, setCustomLocation] = useState("");
  const [budgetRange, setBudgetRange] = useState("5000_10000");
  const [inventoryBudget, setInventoryBudget] = useState("");
  const [operatingCash, setOperatingCash] = useState("");
  const [businessModel, setBusinessModel] = useState<string[]>([]);
  const [experience, setExperience] = useState("Beginner");
  const [timeCommitment, setTimeCommitment] = useState("Part-time");
  const [risk, setRisk] = useState("Balanced");
  const [monthlyIncome, setMonthlyIncome] = useState("");
  const [margin, setMargin] = useState("20-30%");
  const [productPrefs, setProductPrefs] = useState<string[]>([
    "Essential products",
    "Low-MOQ products",
  ]);
  const [customerType, setCustomerType] = useState("");
  const [categoryHints, setCategoryHints] = useState<string[]>([]);
  const [questions, setQuestions] = useState<AdaptiveQuestion[]>([]);
  const [adaptiveAnswers, setAdaptiveAnswers] = useState<
    Record<string, string | string[]>
  >({});

  const applyHydration = useCallback((s: PlannerSession) => {
    const h = hydrateFromSession(s);
    setSession(s);
    setGoal(h.goal);
    setUnsure(h.unsure);
    setLocation(h.location === "Other" ? "Other" : h.location);
    setBudgetRange(h.budgetRange);
    setInventoryBudget(h.inventoryBudget);
    setOperatingCash(h.operatingCash);
    setBusinessModel(h.businessModel);
    setExperience(h.experience);
    setTimeCommitment(h.timeCommitment);
    setRisk(h.risk);
    setMonthlyIncome(h.monthlyIncome);
    setMargin(h.margin);
    setProductPrefs(h.productPrefs);
    setCustomerType(h.customerType);
    setCategoryHints(h.categoryHints);
    setAdaptiveAnswers(h.adaptiveAnswers);
    setQuestions(s.adaptive_questions || []);
    if (s.plan_id) {
      router.replace(ROUTES.businessPlannerPlan(s.plan_id));
      return;
    }
    setStep(h.step === "generating" ? "preferences" : h.step);
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    async function resume() {
      setLoadingSession(true);
      const fromQuery = searchParams.get("session");
      const fromStorage =
        typeof window !== "undefined"
          ? window.sessionStorage.getItem(SESSION_STORAGE_KEY)
          : null;
      const id = fromQuery || fromStorage;
      if (!id) {
        setLoadingSession(false);
        return;
      }
      try {
        const s = await businessPlannerApi.getSession(id);
        if (cancelled) return;
        applyHydration(s);
        if (typeof window !== "undefined") {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, s.id);
        }
      } catch {
        if (typeof window !== "undefined") {
          window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
        }
      } finally {
        if (!cancelled) setLoadingSession(false);
      }
    }
    void resume();
    return () => {
      cancelled = true;
    };
  }, [applyHydration, searchParams]);

  async function ensureSession() {
    if (session) return session;
    const created = await businessPlannerApi.createSession();
    setSession(created);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, created.id);
    }
    router.replace(`${ROUTES.businessPlannerNew}?session=${created.id}`);
    return created;
  }

  async function run(action: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function generatePlan(sessionId: string) {
    setStep("generating");
    setBusy(true);
    setError(null);
    try {
      const plan = await businessPlannerApi.generate(sessionId);
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      }
      router.push(ROUTES.businessPlannerPlan(plan.id));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not generate a business plan right now. Please try again.",
      );
      setStep(questions.length ? "adaptive" : "preferences");
    } finally {
      setBusy(false);
    }
  }

  async function submitGoal() {
    await run(async () => {
      const s = await ensureSession();
      const updated = await businessPlannerApi.submitAnswers(s.id, "goal", {
        business_goal: unsure ? null : goal,
        unsure_goal: unsure || goal === "I'm not sure yet",
      });
      setSession(updated);
      setStep("location");
    });
  }

  async function submitLocation() {
    await run(async () => {
      const s = await ensureSession();
      const loc = location === "Other" ? customLocation.trim() || "Lebanon" : location;
      const updated = await businessPlannerApi.submitAnswers(s.id, "location", {
        location: loc,
      });
      setSession(updated);
      setStep("budget");
    });
  }

  async function submitBudget() {
    await run(async () => {
      const s = await ensureSession();
      const updated = await businessPlannerApi.submitAnswers(s.id, "budget", {
        budget_range: budgetRange,
        inventory_budget: inventoryBudget || null,
        operating_cash: operatingCash || null,
      });
      setSession(updated);
      setStep("preferences");
    });
  }

  async function submitPreferences() {
    await run(async () => {
      const s = await ensureSession();
      const updated = await businessPlannerApi.submitAnswers(s.id, "preferences", {
        business_model: businessModel,
        experience,
        time_commitment: timeCommitment,
        risk_preference: risk,
        desired_monthly_income: monthlyIncome || null,
        desired_margin: margin,
        product_preferences: productPrefs,
        customer_type: customerType || null,
        category_hints: categoryHints,
      });
      setSession(updated);
      const next = await businessPlannerApi.nextQuestions(s.id);
      setSession(next.session);
      setQuestions(next.questions);
      if (next.questions.length === 0) {
        await generatePlan(s.id);
      } else {
        setStep("adaptive");
      }
    });
  }

  async function submitAdaptive() {
    await run(async () => {
      const s = await ensureSession();
      await businessPlannerApi.submitAnswers(s.id, "adaptive", adaptiveAnswers);
      await generatePlan(s.id);
    });
  }

  const progressPct = Math.round(((stepIndex(step) + 1) / DISCOVERY_STEPS.length) * 100);
  const canContinue = canContinueGoal(goal, unsure);

  return {
    step,
    setStep,
    session,
    busy,
    loadingSession,
    error,
    progressPct,
    stepNumber: stepIndex(step) + 1,
    stepCount: DISCOVERY_STEPS.length,
    goal,
    setGoal,
    unsure,
    setUnsure,
    location,
    setLocation,
    customLocation,
    setCustomLocation,
    budgetRange,
    setBudgetRange,
    inventoryBudget,
    setInventoryBudget,
    operatingCash,
    setOperatingCash,
    businessModel,
    setBusinessModel,
    experience,
    setExperience,
    timeCommitment,
    setTimeCommitment,
    risk,
    setRisk,
    monthlyIncome,
    setMonthlyIncome,
    margin,
    setMargin,
    productPrefs,
    setProductPrefs,
    customerType,
    setCustomerType,
    categoryHints,
    setCategoryHints,
    questions,
    adaptiveAnswers,
    setAdaptiveAnswers,
    canContinue,
    submitGoal,
    submitLocation,
    submitBudget,
    submitPreferences,
    submitAdaptive,
  };
}
