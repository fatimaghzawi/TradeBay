"use client";

import { BusyText } from "@/components/ui/LoadingState";
import { cn } from "@/lib/utils";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ActTone = "go" | "ghost" | "ok" | "danger" | "soft";

export function AdminPage({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("tb-cc", className)}>{children}</div>;
}

export function AdminKpis({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("tb-cc-kpis tb-cc-kpis--page", className)}>{children}</section>
  );
}

export function AdminKpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "green" | "orange";
}) {
  return (
    <div className="tb-cc-kpi">
      <div className="tb-cc-kpi__top">
        <span>{label}</span>
        {hint ? <em data-tone={tone}>{hint}</em> : null}
      </div>
      <strong>{value}</strong>
    </div>
  );
}

export function AdminPanel({
  title,
  aside,
  children,
  className,
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("tb-cc-panel", className)}>
      {title || aside ? (
        <header className="tb-cc-panel__head">
          {title ? <h2>{title}</h2> : <span />}
          {aside ? <span>{aside}</span> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function AdminCards({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <ul className={cn("tb-cc-cards", className)}>{children}</ul>;
}

export function AdminAct({
  children,
  href,
  tone = "ghost",
  arrow: _arrow = false,
  busy = false,
  className,
  disabled,
  onClick,
  type = "button",
  title,
}: {
  children: ReactNode;
  href?: string;
  tone?: ActTone;
  arrow?: boolean;
  busy?: boolean;
  className?: string;
  disabled?: boolean;
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  type?: "button" | "submit";
  title?: string;
}) {
  const cls = cn("tb-cc-act", `tb-cc-act--${tone}`, className);
  const inner = <BusyText busy={busy}>{children}</BusyText>;
  if (href) {
    return (
      <Link href={href} className={cls} title={title} onClick={onClick as never}>
        {inner}
      </Link>
    );
  }
  return (
    <button
      type={type}
      className={cls}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      onClick={onClick}
      title={title}
    >
      {inner}
    </button>
  );
}
