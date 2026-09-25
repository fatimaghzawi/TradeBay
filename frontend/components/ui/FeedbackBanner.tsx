"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const STYLES = {
  info: "border-border bg-card text-foreground",
  success:
    "border-[color-mix(in_srgb,var(--tb-success)_35%,var(--tb-line))] bg-success-soft text-success",
  warning:
    "border-[color-mix(in_srgb,var(--tb-warning)_35%,var(--tb-line))] bg-warning-soft text-warning",
  error:
    "border-[color-mix(in_srgb,var(--tb-danger)_35%,var(--tb-line))] bg-destructive-soft text-destructive",
} as const;

const ICONS = {
  info: { bg: "bg-primary text-primary-foreground", mark: "i" },
  success: { bg: "bg-[var(--tb-success)] text-white", mark: "✓" },
  warning: { bg: "bg-[var(--tb-warning)] text-white", mark: "!" },
  error: { bg: "bg-[var(--tb-danger)] text-white", mark: "!" },
} as const;

export type FeedbackBannerProps = {
  tone?: keyof typeof STYLES;
  title?: string;
  children: ReactNode;
  className?: string;
  onDismiss?: () => void;
};

export function FeedbackBanner({
  tone = "info",
  title,
  children,
  className,
  onDismiss,
}: FeedbackBannerProps) {
  const icon = ICONS[tone];
  return (
    <div
      role="status"
      className={cn(
        "flex items-start justify-between gap-3 border-l-[3px] border px-4 py-3 text-sm",
        STYLES[tone],
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        <span
          aria-hidden
          className={cn(
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center text-xs font-bold",
            icon.bg,
          )}
        >
          {icon.mark}
        </span>
        <div className="min-w-0">
          {title ? (
            <p className="font-[family-name:var(--font-outfit)] font-bold">{title}</p>
          ) : null}
          <div className={cn(title ? "mt-0.5 opacity-90" : undefined)}>{children}</div>
        </div>
      </div>
      {onDismiss ? (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="shrink-0 rounded-lg px-1.5 text-base leading-none opacity-70 hover:bg-[var(--tb-hover)] hover:opacity-100"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
