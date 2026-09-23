import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const variants = {
  info: "bg-[var(--tb-accent-soft)] text-[var(--tb-warning)]",
  success: "bg-[var(--tb-success-soft)] text-[var(--tb-success)]",
  warning: "bg-[var(--tb-warning-soft)] text-[var(--tb-warning)]",
  error: "bg-[var(--tb-danger-soft)] text-[var(--tb-danger)]",
} as const;

export type AlertProps = HTMLAttributes<HTMLDivElement> & {
  variant?: keyof typeof variants;
  title?: string;
};

export function Alert({
  className,
  variant = "info",
  title,
  children,
  ...props
}: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        "tb-banner rounded-[var(--tb-radius-field)] border-0 px-3.5 py-2.5 text-sm",
        variants[variant],
        className,
      )}
      {...props}
    >
      {title ? <p className="mb-0.5 font-semibold">{title}</p> : null}
      {children}
    </div>
  );
}
