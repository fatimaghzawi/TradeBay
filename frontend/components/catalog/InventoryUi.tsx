import { cn } from "@/lib/utils";
import { buttonClass, type ButtonVariant } from "@/components/ui/Button";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { BusyText, LoadingEntity } from "@/components/ui/LoadingState";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function InventoryPageHeader({
  title,
  description,
  actions,
  eyebrow: _eyebrow = "Inventory",
  mark,
  meta: _meta,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: string;
  mark?: string;
  meta?: ReactNode;
}) {
  return (
    <DirectoryMast
      title={title}
      lede={description}
      actions={actions}
      mark={mark}
      size="page"
    />
  );
}

type InventoryTone = "primary" | "accent" | "ghost" | "soft";

const INVENTORY_VARIANT: Record<InventoryTone, ButtonVariant> = {
  primary: "primary",
  accent: "primary",
  ghost: "outline",
  soft: "secondary",
};

export function InventoryBtn({
  children,
  className,
  tone = "primary",
  busy = false,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: InventoryTone;
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={buttonClass({ variant: INVENTORY_VARIANT[tone], className })}
      {...props}
    >
      <BusyText busy={busy}>{children}</BusyText>
    </button>
  );
}

export function InventoryLinkBtn({
  href,
  children,
  className,
  tone = "primary",
}: {
  href: string;
  children: ReactNode;
  className?: string;
  tone?: InventoryTone;
}) {
  return (
    <Link href={href} className={buttonClass({ variant: INVENTORY_VARIANT[tone], className })}>
      {children}
    </Link>
  );
}

export function InventoryPanel({
  children,
  className,
  flush = false,
  title,
  action,
  subtitle,
}: {
  children: ReactNode;
  className?: string;
  flush?: boolean;
  title?: ReactNode;
  action?: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <section className={cn("tb-inv-panel", flush && "tb-inv-panel-flush", className)}>
      {title || action || subtitle ? (
        <div className={cn("tb-inv-panel-head", flush && "px-5 pt-4")}>
          <div className="min-w-0">
            {title ? <div className="tb-inv-panel-title">{title}</div> : null}
            {subtitle ? <p className="tb-inv-panel-sub">{subtitle}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function InventoryKpi({
  label,
  value,
  hint,
  tone = "default",
  icon,
  index = 0,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "warn" | "ok" | "accent";
  icon?: ReactNode;
  index?: number;
}) {
  return (
    <article
      className="tb-inv-kpi"
      data-tone={tone}
      data-has-icon={icon ? "true" : "false"}
      style={{ animationDelay: `${index * 75}ms` }}
    >
      <div className="tb-inv-kpi-ribbon" aria-hidden />
      <div className="tb-inv-kpi-copy">
        <p className="tb-inv-kpi-value">{value}</p>
        <p className="tb-inv-kpi-label">{label}</p>
        {hint ? <p className="tb-inv-kpi-hint">{hint}</p> : null}
      </div>
      {icon ? (
        <span className="tb-inv-kpi-icon" aria-hidden>
          {icon}
        </span>
      ) : null}
    </article>
  );
}

export function InventoryToolbar({ children }: { children: ReactNode }) {
  return <div className="tb-inv-toolbar">{children}</div>;
}

export function InventoryEmpty({
  title,
  body,
  action,
  mark = "◇",
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  mark?: ReactNode;
}) {
  return (
    <div className="tb-inv-empty">
      <div className="tb-inv-empty-mark" aria-hidden>
        {mark}
      </div>
      <p className="tb-inv-empty-title">{title}</p>
      {body ? <p className="tb-inv-empty-body">{body}</p> : null}
      {action ? <div className="tb-inv-empty-action">{action}</div> : null}
    </div>
  );
}

export function InventorySkeleton({
  rows: _rows = 4,
  entity = "data",
}: {
  rows?: number;
  
  entity?: string;
}) {
  return <LoadingEntity entity={entity} />;
}

export function InventoryTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tb-inv-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={value === tab.id}
          data-active={value === tab.id}
          className="tb-inv-tab"
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function InventoryTable({
  columns,
  children,
  empty,
}: {
  columns: string[];
  children: ReactNode;
  empty?: ReactNode;
}) {
  return (
    <div className="tb-inv-table-wrap">
      <table className="tb-inv-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
      {empty}
    </div>
  );
}

export function InventoryFoot({
  left,
  right,
}: {
  left?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="tb-inv-foot">
      <div className="tb-inv-foot-left">{left}</div>
      <div className="tb-inv-foot-right">{right}</div>
    </div>
  );
}

export { StatusBadge } from "@/components/ui/StatusBadge";

export function StockBar({
  label,
  value,
  max,
  tone = "ok",
}: {
  label: string;
  value: number;
  max: number;
  tone?: "ok" | "warn";
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="tb-inv-stock-bar">
      <div className="tb-inv-stock-bar-head">
        <span>{label}</span>
        <strong>
          {value} <em>{pct}%</em>
        </strong>
      </div>
      <div className="tb-inv-stock-bar-track">
        <span data-tone={tone} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
