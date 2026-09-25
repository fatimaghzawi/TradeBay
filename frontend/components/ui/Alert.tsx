import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const variants = {
  info: "",
  success: "tb-alert--success",
  warning: "tb-alert--warning",
  error: "tb-alert--error",
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
      role={variant === "error" || variant === "warning" ? "alert" : "status"}
      className={cn("tb-alert", variants[variant], className)}
      {...props}
    >
      <div className="min-w-0">
        {title ? <p className="mb-0.5 font-semibold">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}
