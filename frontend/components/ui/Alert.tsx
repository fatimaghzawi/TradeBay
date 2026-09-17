import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const variants = {
  info: "border-border bg-surface text-primary",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-accent/40 bg-accent/10 text-accent-foreground",
  error: "border-danger/30 bg-danger/10 text-danger",
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
      className={cn("rounded-lg border px-4 py-3 text-sm", variants[variant], className)}
      {...props}
    >
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      {children}
    </div>
  );
}
