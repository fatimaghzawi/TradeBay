"use client";

import { AskTheBayDesk } from "@/components/dashboard/AskTheBayDesk";
import { DashboardActivity } from "@/components/dashboard/DashboardActivity";
import { DashboardCategories } from "@/components/dashboard/DashboardCategories";
import { DashboardBanner, DashboardImpact } from "@/components/dashboard/DashboardImpact";
import { DashboardKpis } from "@/components/dashboard/DashboardKpis";
import { PlanBusinessDesk } from "@/components/dashboard/PlanBusinessDesk";
import { LoadingState } from "@/components/ui/LoadingState";
import { businessPlannerApi } from "@/lib/api/businessPlannerApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

function weatherHint(hour: number): { label: string; icon: "sun" | "moon" | "cloud" } {
  if (hour >= 6 && hour < 11) return { label: "Clear morning", icon: "sun" };
  if (hour >= 11 && hour < 17) return { label: "Sunny", icon: "sun" };
  if (hour >= 17 && hour < 20) return { label: "Golden hour", icon: "sun" };
  return { label: "Clear evening", icon: "moon" };
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, business, isLoading } = useAuth();
  const firstName = user?.first_name || "there";
  const hasBusiness = Boolean(business);
  const isPlatform = business?.type === "platform";
  const isSupplier = business?.type === "supplier";
  const showBuyerAi = !isSupplier && !isPlatform;
  const [recentPlanHref, setRecentPlanHref] = useState<string | null>(null);
  const [now] = useState(() => new Date());

  useEffect(() => {
    if (!isLoading && isPlatform) {
      router.replace(ROUTES.admin.home);
    }
  }, [isLoading, isPlatform, router]);

  const greeting = useMemo(() => {
    const hour = now.getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }, [now]);

  const city = business?.address?.city || "Tyre";
  const country = business?.address?.country || "Lebanon";
  const weather = useMemo(() => weatherHint(now.getHours()), [now]);
  const dateLabel = useMemo(
    () =>
      now.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
    [now],
  );

  useEffect(() => {
    if (!showBuyerAi) {
      setRecentPlanHref(null);
      return;
    }
    let cancelled = false;
    void businessPlannerApi
      .listPlans(1, 1)
      .then((res) => {
        if (cancelled) return;
        const plan = res.data[0];
        setRecentPlanHref(plan ? ROUTES.businessPlannerPlan(plan.id) : null);
      })
      .catch(() => {
        if (!cancelled) setRecentPlanHref(null);
      });
    return () => {
      cancelled = true;
    };
  }, [showBuyerAi]);

  if (isLoading || isPlatform) {
    return (
      <div className="tb-page">
        <LoadingState variant="section" title="Loading" />
      </div>
    );
  }

  const helloCopy = isSupplier
    ? hasBusiness
      ? "Keep your catalog sharp — stock, pricing, and fulfilment in one place."
      : "Set up your supplier company to start listing products."
    : hasBusiness
      ? "New opportunities are waiting. Let's build something great today."
      : "New opportunities are waiting — start by planning a business or asking the Bay.";

  return (
    <div className="tb-page tb-desk">
      <header className="tb-desk-hello">
        <div className="tb-desk-hello__copy">
          <h1>
            {greeting}, {firstName}
          </h1>
          <p>{helloCopy}</p>
        </div>
        <aside className="tb-desk-weather" aria-label="Location and weather">
          <div>
            <strong>
              {city}, {country}
            </strong>
            <span>{dateLabel}</span>
          </div>
          <div className="tb-desk-weather__temp">
            <span className="tb-desk-weather__icon" aria-hidden>
              {weather.icon === "moon" ? "☾" : "☀"}
            </span>
            <em>{weather.label}</em>
          </div>
        </aside>
      </header>

      {showBuyerAi ? (
        <div className="tb-desk-heroes">
          <AskTheBayDesk businessName={business?.name} />
          <PlanBusinessDesk hasBusiness={hasBusiness} recentPlanHref={recentPlanHref} />
        </div>
      ) : null}

      <DashboardKpis />

      <div className="tb-desk-bottom">
        <DashboardActivity />
        <DashboardCategories />
        <DashboardImpact />
      </div>

      <DashboardBanner />
    </div>
  );
}
