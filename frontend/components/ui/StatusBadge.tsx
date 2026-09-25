import { statusLabel, statusTone, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type StatusBadgeProps = {
  status: string | null | undefined;
  
  label?: ReactNode;
  
  tone?: StatusTone;
  className?: string;
};

export function StatusBadge({ status, label, tone, className }: StatusBadgeProps) {
  return (
    <span className={cn("tb-badge", className)} data-tone={tone ?? statusTone(status)}>
      {label ?? statusLabel(status)}
    </span>
  );
}

export function Badge({
  tone = "off",
  children,
  dot = true,
  className,
}: {
  tone?: StatusTone;
  children: ReactNode;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("tb-badge", className)} data-tone={tone} data-dot={dot ? undefined : "false"}>
      {children}
    </span>
  );
}
