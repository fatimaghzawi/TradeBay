"use client";

import { catalogApi } from "@/lib/api/catalogApi";
import { LoadingEntity } from "@/components/ui/LoadingState";
import {
  procurementApi,
  type ProcurementDashboard,
} from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Kpi = {
  key: string;
  label: string;
  value: number | null;
  href: string;
  tone: "green" | "orange";
  delta?: string | null;
  spark: number[];
};

function Sparkline({ points, tone }: { points: number[]; tone: "green" | "orange" }) {
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = Math.max(max - min, 1);
  const w = 72;
  const h = 28;
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * w;
      const y = h - ((p - min) / range) * (h - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg className={`tb-desk-kpi__spark is-${tone}`} viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden>
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function sparkFromCount(n: number, seed: number): number[] {
  const base = Math.max(n, 1);
  return Array.from({ length: 8 }, (_, i) => {
    const wave = Math.sin((i + seed) * 0.9) * 0.22 + 0.78;
    return Math.max(1, Math.round(base * wave * (0.55 + i * 0.06)));
  });
}

export function DashboardKpis() {
  const { business, hasPermission } = useAuth();
  const canReadRfqs = hasPermission("rfqs.read");
  const [dash, setDash] = useState<ProcurementDashboard | null>(null);
  const [supplierCount, setSupplierCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const tasks: Promise<void>[] = [
      catalogApi
        .listProducts({ page: 1, page_size: 100, status: "active" })
        .then((res) => {
          if (cancelled) return;
          const ids = new Set(res.data.map((p) => p.business_account_id).filter(Boolean));
          setSupplierCount(ids.size || Math.max(res.meta.total, 0));
        })
        .catch(() => {
          if (!cancelled) setSupplierCount(null);
        }),
    ];

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

    void Promise.all(tasks).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [business, canReadRfqs]);

  const kpis: Kpi[] = useMemo(() => {
    const rfqs = dash?.rfqs ?? [];
    const activeRfqs = rfqs.filter((r) => !["cancelled", "closed", "awarded"].includes(r.status)).length;
    const pendingQuotes = dash?.quotes_waiting ?? rfqs.reduce((n, r) => n + (r.quotation_count || 0), 0);

    return [
      {
        key: "rfqs",
        label: "Active RFQs",
        value: business ? activeRfqs : null,
        href: ROUTES.procurement,
        tone: "green" as const,
        delta: activeRfqs > 0 ? "Live" : null,
        spark: sparkFromCount(activeRfqs || 3, 1),
      },
      {
        key: "quotes",
        label: "Pending Quotations",
        value: business ? pendingQuotes : null,
        href: ROUTES.procurement,
        tone: "orange" as const,
        delta: pendingQuotes > 0 ? "Waiting" : null,
        spark: sparkFromCount(pendingQuotes || 4, 2),
      },
      {
        key: "orders",
        label: "Orders (soon)",
        value: null,
        href: ROUTES.orders,
        tone: "green" as const,
        delta: "Coming soon",
        spark: sparkFromCount(2, 3),
      },
      {
        key: "suppliers",
        label: "Verified Suppliers",
        value: supplierCount,
        href: ROUTES.suppliersDirectory,
        tone: "orange" as const,
        delta: supplierCount ? "Directory" : null,
        spark: sparkFromCount(supplierCount || 12, 4),
      },
    ];
  }, [business, dash, supplierCount]);

  if (loading) {
    return (
      <div className="tb-desk-kpis" aria-busy="true">
        <LoadingEntity entity="metrics" />
      </div>
    );
  }

  return (
    <div className="tb-desk-kpis">
      {kpis.map((kpi) => (
        <Link key={kpi.key} href={kpi.href} className={`tb-desk-kpi is-${kpi.tone}`}>
          <div className="tb-desk-kpi__icon" aria-hidden>
            <KpiIcon name={kpi.key} />
          </div>
          <div className="tb-desk-kpi__copy">
            <p className="tb-desk-kpi__label">{kpi.label}</p>
            <p className="tb-desk-kpi__value">{kpi.value == null ? "—" : kpi.value}</p>
            {kpi.delta ? <p className="tb-desk-kpi__delta">{kpi.delta}</p> : null}
          </div>
          <Sparkline points={kpi.spark} tone={kpi.tone} />
        </Link>
      ))}
    </div>
  );
}

function KpiIcon({ name }: { name: string }) {
  if (name === "rfqs") {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20">
        <path
          d="M7 4h10a2 2 0 0 1 2 2v14l-4-2-3 2-3-2-4 2V6a2 2 0 0 1 2-2z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        />
      </svg>
    );
  }
  if (name === "quotes") {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20">
        <path
          d="M4 6h16v12H4zM8 10h8M8 14h5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (name === "orders") {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20">
        <path
          d="M4 7h16l-1.5 10H5.5L4 7zm3-3h10l1 3H6l1-3z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="20" height="20">
      <path
        d="M12 3l2.2 4.5L19 8.2l-3.5 3.4.8 4.9L12 14.8 7.7 16.5l.8-4.9L5 8.2l4.8-.7L12 3z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
