import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type SpinnerSize = "sm" | "md";

export function Spinner({
  size = "md",
  className,
  label = "Loading",
}: {
  size?: SpinnerSize;
  className?: string;
  label?: string;
}) {
  return (
    <span
      className={cn("tb-spin", size === "sm" && "tb-spin--sm", className)}
      role="status"
      aria-label={label}
    >
      <i />
      <i />
      <i />
    </span>
  );
}

export function BusyText({
  busy,
  children,
}: {
  busy?: boolean;
  children: ReactNode;
}) {
  return (
    <span className="tb-busy-label">
      {busy ? <Spinner size="sm" /> : null}
      {children}
    </span>
  );
}

type LoadingStateProps = {
  variant?: "page" | "section" | "rows";
  title?: string;
  message?: string;
  rows?: number;
  className?: string;
};

export function LoadingState({
  variant = "section",
  title = "Loading",
  message,
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn(
        variant === "page" ? "tb-loading-page" : "tb-loading-section",
        className,
      )}
      aria-busy="true"
      aria-live="polite"
    >
      <Spinner size={variant === "page" ? "md" : "sm"} />
      <p>{title}</p>
      {message ? <span>{message}</span> : null}
    </div>
  );
}

export function LoadingEntity({
  entity,
  className,
  compact = false,
}: {
  entity: string;
  className?: string;
  compact?: boolean;
}) {
  const label = `Loading ${entity}…`;
  return (
    <p
      className={cn("tb-loading-entity", compact && "tb-loading-entity--compact", className)}
      aria-busy="true"
      aria-live="polite"
    >
      <Spinner size="sm" />
      {label}
    </p>
  );
}
