import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const tones = {
  default: "bg-muted text-primary",
  success: "bg-success/15 text-success",
  warning: "bg-accent/15 text-accent",
  danger: "bg-danger/15 text-danger",
} as const;

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: keyof typeof tones;
};

export function Badge({ className, tone = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
