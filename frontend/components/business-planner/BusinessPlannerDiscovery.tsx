"use client";

import {
  InventoryBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
} from "@/components/catalog/InventoryUi";
import { BackLink } from "@/components/ui/BackLink";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Spinner } from "@/components/ui/LoadingState";
import {
  BUDGET_OPTIONS,
  BUSINESS_MODELS,
  CATEGORY_HINTS,
  CUSTOMER_TYPES,
  PLANNER_GOALS,
  PRODUCT_PREFS,
} from "@/features/business-planner/constants";
import { usePlannerDiscovery } from "@/features/business-planner/usePlannerDiscovery";
import { LEBANON_REGIONS } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { toggleListValue } from "@/lib/businessPlanner";
import { plannerBudgetSchema, plannerLocationSchema, plannerPrefsSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { Suspense } from "react";

function ChoiceGrid({
  options,
  active,
  onSelect,
  multi = false,
}: {
  options: readonly string[] | string[];
  active: string | string[] | null;
  onSelect: (value: string) => void;
  multi?: boolean;
}) {
  return (
    <div className="bp-choice-grid">
      {options.map((opt) => {
        const isActive = multi
          ? Array.isArray(active) && active.includes(opt)
          : active === opt;
        return (
          <button
            key={opt}
            type="button"
            className={`bp-choice ${isActive ? "is-active" : ""}`}
            onClick={() => onSelect(opt)}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function DiscoveryInner() {
  const d = usePlannerDiscovery();
  const locationLive = useLiveFields(plannerLocationSchema, {
    customLocation: d.customLocation,
  });
  const budgetLive = useLiveFields(plannerBudgetSchema, {
    inventoryBudget: d.inventoryBudget,
    operatingCash: d.operatingCash,
  });
  const prefsLive = useLiveFields(plannerPrefsSchema, {
    monthlyIncome: d.monthlyIncome,
  });

  if (d.loadingSession) {
    return (
      <div className="tb-inv-page">
        <InventoryPageHeader
          eyebrow="Business Planner"
          title="Build your business"
          description="Resuming your session…"
        />
        <InventorySkeleton entity="plans" />
      </div>
    );
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow="Business Planner"
        title="Build your business step by step"
        description="Answer a few questions to build your plan."
        actions={
          <BackLink href={ROUTES.businessPlanner}>Back to plans</BackLink>
        }
        meta={
          <div className="bp-progress-wrap">
            <div className="bp-progress" aria-label="Progress">
              <div className="bp-progress__bar" style={{ width: `${d.progressPct}%` }} />
            </div>
            <p className="bp-progress__label">
              Step {d.stepNumber} of {d.stepCount}
            </p>
          </div>
        }
      />

      {d.error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {d.error}
        </FeedbackBanner>
      ) : null}

      {d.step === "goal" ? (
        <InventoryPanel title="What are you hoping to build?">
          <ChoiceGrid
            options={[...PLANNER_GOALS]}
            active={d.unsure ? null : d.goal}
            onSelect={(g) => {
              d.setGoal(g);
              d.setUnsure(false);
            }}
          />
          <button
            type="button"
            className={`bp-choice bp-choice--wide mt-2 ${d.unsure ? "is-active" : ""}`}
            onClick={() => {
              d.setUnsure(true);
              d.setGoal(null);
            }}
          >
            I&apos;m not sure yet
          </button>
          <div className="tb-inv-form-actions">
            <InventoryBtn busy={d.busy} disabled={d.busy || !d.canContinue} onClick={d.submitGoal}>
              Continue
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      {d.step === "location" ? (
        <InventoryPanel
          title="Where do you want to operate?"
          subtitle="Where the business operates"
        >
          <ChoiceGrid
            options={[
              ...LEBANON_REGIONS.map((r) => r.label),
              "Tyre",
              "Saida",
              "Tripoli",
              "Zahle",
              "Other",
            ]}
            active={d.location}
            onSelect={d.setLocation}
          />
          {d.location === "Other" ? (
            <label className="tb-inv-field mt-3 block">
              <span>Location</span>
              <input
                value={d.customLocation}
                onChange={(e) => d.setCustomLocation(e.target.value)}
                onBlur={() => locationLive.touch("customLocation")}
                placeholder="City or region in Lebanon"
              />
              <FieldError error={locationLive.errors.customLocation} />
            </label>
          ) : null}
          <div className="tb-inv-form-actions">
            <InventoryBtn tone="ghost" busy={d.busy} disabled={d.busy} onClick={() => d.setStep("goal")}>
              Back
            </InventoryBtn>
            <InventoryBtn busy={d.busy} disabled={d.busy}
              onClick={() => {
                if (d.location === "Other" && !locationLive.finish()) return;
                void d.submitLocation();
              }}
            >
              Continue
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      {d.step === "budget" ? (
        <InventoryPanel title="How much are you willing to invest?">
          <div className="bp-choice-grid">
            {BUDGET_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`bp-choice ${d.budgetRange === opt.value ? "is-active" : ""}`}
                onClick={() => d.setBudgetRange(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="tb-inv-form-grid mt-4">
            <label className="tb-inv-field">
              <span>Initial inventory budget (optional)</span>
              <NumberInput
                kind="decimal"
                value={d.inventoryBudget}
                onChange={(e) => d.setInventoryBudget(e.target.value)}
                onBlur={() => budgetLive.touch("inventoryBudget")}
                placeholder="e.g. 2500"
              />
              <FieldError error={budgetLive.errors.inventoryBudget} />
            </label>
            <label className="tb-inv-field">
              <span>Keep as operating cash (optional)</span>
              <NumberInput
                kind="decimal"
                value={d.operatingCash}
                onChange={(e) => d.setOperatingCash(e.target.value)}
                onBlur={() => budgetLive.touch("operatingCash")}
                placeholder="e.g. 1000"
              />
              <FieldError error={budgetLive.errors.operatingCash} />
            </label>
          </div>
          <div className="tb-inv-form-actions">
            <InventoryBtn tone="ghost" busy={d.busy} disabled={d.busy} onClick={() => d.setStep("location")}>
              Back
            </InventoryBtn>
            <InventoryBtn busy={d.busy} disabled={d.busy}
              onClick={() => {
                if (!budgetLive.finish()) return;
                void d.submitBudget();
              }}
            >
              Continue
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      {d.step === "preferences" ? (
        <InventoryPanel title="Preferences">
          <h3 className="bp-subhead">Business model</h3>
          <ChoiceGrid
            multi
            options={[...BUSINESS_MODELS]}
            active={d.businessModel}
            onSelect={(m) => d.setBusinessModel(toggleListValue(d.businessModel, m))}
          />

          <h3 className="bp-subhead">Customer type</h3>
          <ChoiceGrid
            options={[...CUSTOMER_TYPES]}
            active={d.customerType || null}
            onSelect={d.setCustomerType}
          />

          <h3 className="bp-subhead">Category focus</h3>
          <ChoiceGrid
            multi
            options={[...CATEGORY_HINTS]}
            active={d.categoryHints}
            onSelect={(c) => d.setCategoryHints(toggleListValue(d.categoryHints, c))}
          />

          <div className="tb-inv-form-grid mt-4">
            <label className="tb-inv-field">
              <span>Experience</span>
              <select value={d.experience} onChange={(e) => d.setExperience(e.target.value)}>
                <option>Beginner</option>
                <option>Some experience</option>
                <option>Experienced</option>
              </select>
            </label>
            <label className="tb-inv-field">
              <span>Time commitment</span>
              <select
                value={d.timeCommitment}
                onChange={(e) => d.setTimeCommitment(e.target.value)}
              >
                <option>Part-time</option>
                <option>Full-time</option>
              </select>
            </label>
            <label className="tb-inv-field">
              <span>Risk preference</span>
              <select value={d.risk} onChange={(e) => d.setRisk(e.target.value)}>
                <option>Conservative</option>
                <option>Balanced</option>
                <option>Aggressive</option>
              </select>
            </label>
            <label className="tb-inv-field">
              <span>Desired monthly income</span>
              <input
                value={d.monthlyIncome}
                onChange={(e) => d.setMonthlyIncome(e.target.value)}
                onBlur={() => prefsLive.touch("monthlyIncome")}
                placeholder="e.g. 1500"
              />
              <FieldError error={prefsLive.errors.monthlyIncome} />
            </label>
            <label className="tb-inv-field">
              <span>Desired profit margin</span>
              <select value={d.margin} onChange={(e) => d.setMargin(e.target.value)}>
                <option>Not sure</option>
                <option>10-20%</option>
                <option>20-30%</option>
                <option>30-40%</option>
                <option>40%+</option>
              </select>
            </label>
          </div>

          <h3 className="bp-subhead">Product preference</h3>
          <ChoiceGrid
            multi
            options={[...PRODUCT_PREFS]}
            active={d.productPrefs}
            onSelect={(p) => d.setProductPrefs(toggleListValue(d.productPrefs, p))}
          />

          <div className="tb-inv-form-actions">
            <InventoryBtn tone="ghost" busy={d.busy} disabled={d.busy} onClick={() => d.setStep("budget")}>
              Back
            </InventoryBtn>
            <InventoryBtn busy={d.busy} disabled={d.busy}
              onClick={() => {
                if (!prefsLive.finish()) return;
                void d.submitPreferences();
              }}
            >
              Continue
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      {d.step === "adaptive" ? (
        <InventoryPanel title="A few more details">
          {d.questions.map((q) => (
            <div key={q.id} className="bp-adaptive">
              <h3 className="bp-subhead">{q.prompt}</h3>
              {q.why ? <p className="tb-inv-muted">{q.why}</p> : null}
              {q.input_type === "text" || q.input_type === "number" ? (
                <label className="tb-inv-field">
                  <span className="sr-only">{q.prompt}</span>
                  <input
                    value={String(d.adaptiveAnswers[q.id] ?? "")}
                    onChange={(e) =>
                      d.setAdaptiveAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                    }
                  />
                </label>
              ) : (
                <ChoiceGrid
                  multi={q.input_type === "multi"}
                  options={q.options}
                  active={
                    (d.adaptiveAnswers[q.id] as string | string[] | undefined) ??
                    (q.input_type === "multi" ? [] : null)
                  }
                  onSelect={(opt) => {
                    if (q.input_type === "multi") {
                      const current = d.adaptiveAnswers[q.id];
                      const arr = Array.isArray(current) ? current : [];
                      d.setAdaptiveAnswers((prev) => ({
                        ...prev,
                        [q.id]: toggleListValue(arr, opt),
                      }));
                    } else {
                      d.setAdaptiveAnswers((prev) => ({ ...prev, [q.id]: opt }));
                    }
                  }}
                />
              )}
            </div>
          ))}
          <div className="tb-inv-form-actions">
            <InventoryBtn
              tone="ghost" busy={d.busy} disabled={d.busy}
              onClick={() => d.setStep("preferences")}
            >
              Back
            </InventoryBtn>
            <InventoryBtn busy={d.busy} disabled={d.busy} onClick={d.submitAdaptive}>
              Generate my plan
            </InventoryBtn>
          </div>
        </InventoryPanel>
      ) : null}

      {d.step === "generating" ? (
        <InventoryPanel>
          <div className="bp-generating">
            <Spinner />
            <h2>Analyzing TradeBay marketplace…</h2>
            <p className="tb-inv-muted">Building your plan…</p>
          </div>
        </InventoryPanel>
      ) : null}
    </div>
  );
}

export function BusinessPlannerDiscovery() {
  return (
    <Suspense
      fallback={
        <div className="tb-inv-page">
          <InventorySkeleton entity="plans" />
        </div>
      }
    >
      <DiscoveryInner />
    </Suspense>
  );
}
