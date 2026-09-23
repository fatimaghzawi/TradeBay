"use client";

import { ROUTES } from "@/lib/constants";
import Link from "next/link";

const FLOW = [
  { key: "idea", label: "Your Idea" },
  { key: "products", label: "Products" },
  { key: "suppliers", label: "Suppliers" },
  { key: "plan", label: "Business Plan" },
] as const;

type Props = {
  hasBusiness: boolean;
  recentPlanHref?: string | null;
};

export function PlanBusinessDesk({ hasBusiness, recentPlanHref }: Props) {
  return (
    <section className="tb-desk-plan" aria-labelledby="tb-desk-plan-title">
      <div className="tb-desk-plan__media" aria-hidden>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/images/tradebay-port-banner.jpg" alt="" />
      </div>
      <div className="tb-desk-plan__veil" aria-hidden />
      <p className="tb-desk-plan__signature" aria-hidden>
        Ideas into Opportunities
      </p>

      <div className="tb-desk-plan__body">
        <p className="tb-desk-plan__pill">Build Something New</p>
        <h2 id="tb-desk-plan-title" className="tb-desk-plan__title">
          Plan a Business
        </h2>
        <p className="tb-desk-plan__lede">
          {hasBusiness
            ? "Turn a new idea into a funded plan — products, suppliers, and financials on TradeBay."
            : "Don't have a business yet? Tell TradeBay what you have, what you want, and what you'll invest."}
        </p>

        <div className="tb-desk-plan__actions">
          <Link href={ROUTES.businessPlannerNew} className="tb-desk-plan__cta">
            Plan My Business
            <span aria-hidden>→</span>
          </Link>
          {recentPlanHref ? (
            <Link href={recentPlanHref} className="tb-desk-plan__secondary">
              Continue last plan
            </Link>
          ) : hasBusiness ? (
            <Link href={ROUTES.businessPlanner} className="tb-desk-plan__secondary">
              View my plans
            </Link>
          ) : null}
        </div>
      </div>

      <ol className="tb-desk-plan__flow" aria-label="How TradeBay builds a plan">
        {FLOW.map((step, i) => (
          <li key={step.key}>
            <span className="tb-desk-plan__step-icon" aria-hidden>
              {i + 1}
            </span>
            <strong>{step.label}</strong>
            {i < FLOW.length - 1 ? (
              <span className="tb-desk-plan__arrow" aria-hidden>
                →
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
