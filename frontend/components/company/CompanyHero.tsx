import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function CompanyHero({
  kicker = "Company",
  title,
  lede,
  mark,
  status,
  action,
}: {
  kicker?: string;
  title: string;
  lede?: ReactNode;
  mark?: string;
  status?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="tb-studio-head">
      <div className="relative z-[1] flex min-w-0 flex-1 items-start gap-3.5">
        {mark ? (
          <span className="tb-studio-avatar" aria-hidden>
            {mark}
          </span>
        ) : null}
        <div className="min-w-0">
          {kicker ? <p className="tb-studio-kicker">{kicker}</p> : null}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h1 className="tb-studio-title">{title}</h1>
            {status}
          </div>
          {lede ? <div className="tb-studio-lede">{lede}</div> : null}
        </div>
      </div>
      {action ? <div className="relative z-[1] shrink-0">{action}</div> : null}
    </header>
  );
}

export function StudioCard({
  children,
  className,
  kind = "info",
}: {
  children: ReactNode;
  className?: string;
  kind?: "stat" | "info" | "action" | "order" | "rfq" | "insight" | "alert" | "tip";
}) {
  return (
    <section className={cn("tb-card", className)} data-kind={kind}>
      {children}
    </section>
  );
}

export function StudioKpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="tb-card" data-kind="stat">
      <div className="relative z-[1] flex-1 px-4 pb-2 pt-4">
        <span className="tb-card-icon">{label.slice(0, 2).toUpperCase()}</span>
        <p className="tb-studio-kpi-label mt-3">{label}</p>
        <p className="tb-studio-kpi-value">{value}</p>
        {hint ? <div className="mt-2 text-xs font-semibold">{hint}</div> : null}
      </div>
      <div className="tb-card-footer">
        <span className="tb-card-action">View details →</span>
      </div>
    </div>
  );
}
