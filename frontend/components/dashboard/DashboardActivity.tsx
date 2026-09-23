"use client";

import {
  procurementApi,
  type ProcurementDashboard,
} from "@/lib/api/procurementApi";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { businessPlannerApi, type BusinessPlan } from "@/lib/api/businessPlannerApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  href: string;
  at: string | null;
  tone: "green" | "orange" | "teal";
};

function relativeTime(iso: string | null): string {
  if (!iso) return "Recently";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "Recently";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function DashboardActivity() {
  const { business, hasPermission } = useAuth();
  const canReadRfqs = hasPermission("rfqs.read");
  const isSupplier = business?.type === "supplier";
  const [dash, setDash] = useState<ProcurementDashboard | null>(null);
  const [plans, setPlans] = useState<BusinessPlan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const tasks: Promise<void>[] = [];

    if (business && canReadRfqs) {
      tasks.push(
        procurementApi
          .dashboard()
          .then((data) => {
            if (!cancelled) setDash(data);
          })
          .catch(() => {
            if (!cancelled) setDash(null);
          }),
      );
    }

    if (!isSupplier) {
      tasks.push(
        businessPlannerApi
          .listPlans(1, 3)
          .then((res) => {
            if (!cancelled) setPlans(res.data);
          })
          .catch(() => {
            if (!cancelled) setPlans([]);
          }),
      );
    } else if (!cancelled) {
      setPlans([]);
    }

    void Promise.all(tasks).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [business, canReadRfqs, isSupplier]);

  const items = useMemo(() => {
    const out: ActivityItem[] = [];

    for (const rfq of dash?.rfqs ?? []) {
      if ((rfq.quotation_count || 0) > 0) {
        out.push({
          id: `q-${rfq.id}`,
          title: "New quotation received",
          detail: `${rfq.rfq_number} · ${rfq.title}`,
          href: ROUTES.procurementRfq(rfq.id),
          at: rfq.updated_at || rfq.created_at,
          tone: "orange",
        });
      } else {
        out.push({
          id: `r-${rfq.id}`,
          title: "RFQ activity",
          detail: `${rfq.rfq_number} · ${rfq.status.replaceAll("_", " ")}`,
          href: ROUTES.procurementRfq(rfq.id),
          at: rfq.updated_at || rfq.created_at,
          tone: "green",
        });
      }
    }

    for (const order of dash?.orders ?? []) {
      out.push({
        id: `o-${order.id}`,
        title: "Order update",
        detail: `${order.order_number} · ${order.status.replaceAll("_", " ")}`,
        href: ROUTES.procurementOrder(order.id),
        at: order.confirmed_at || order.created_at,
        tone: "teal",
      });
    }

    for (const plan of plans) {
      out.push({
        id: `p-${plan.id}`,
        title: "Business plan updated",
        detail: plan.title || "Untitled plan",
        href: ROUTES.businessPlannerPlan(plan.id),
        at: plan.updated_at || plan.created_at || null,
        tone: "green",
      });
    }

    return out
      .sort((a, b) => {
        const ta = a.at ? new Date(a.at).getTime() : 0;
        const tb = b.at ? new Date(b.at).getTime() : 0;
        return tb - ta;
      })
      .slice(0, 5);
  }, [dash, plans]);

  if (loading) {
    return (
      <section className="tb-desk-activity" aria-busy="true">
        <header className="tb-desk-panel__head">
          <h2>Recent Activity</h2>
        </header>
        <LoadingEntity entity="activity" />
      </section>
    );
  }

  return (
    <section className="tb-desk-activity" aria-labelledby="tb-desk-activity-title">
      <header className="tb-desk-panel__head">
        <h2 id="tb-desk-activity-title">Recent Activity</h2>
        <Link href={ROUTES.procurement} className="tb-desk-panel__link">
          View all
        </Link>
      </header>

      {items.length === 0 ? (
        <p className="tb-desk-activity__empty">
          No recent activity yet.{" "}
          <Link href={ROUTES.procurementNew}>Create an RFQ</Link> or{" "}
          <Link href={ROUTES.marketplace}>browse products</Link>.
        </p>
      ) : (
        <ul className="tb-desk-activity__list">
          {items.map((item) => (
            <li key={item.id}>
              <Link href={item.href} className={`tb-desk-activity__item is-${item.tone}`}>
                <span className="tb-desk-activity__dot" aria-hidden />
                <span className="tb-desk-activity__copy">
                  <strong>{item.title}</strong>
                  <em>{item.detail}</em>
                </span>
                <time dateTime={item.at ?? undefined}>{relativeTime(item.at)}</time>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
