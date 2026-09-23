import { cn } from "@/lib/utils";
import { BusyText } from "@/components/ui/LoadingState";
import type { ButtonHTMLAttributes } from "react";

const variants = {
  primary:
    "bg-[var(--tb-primary)] text-[var(--tb-primary-foreground)] hover:bg-[var(--tb-secondary)] focus-visible:ring-[var(--tb-primary)] shadow-[0_8px_20px_-12px_color-mix(in_srgb,var(--tb-primary)_55%,transparent)]",
  secondary:
    "border border-[var(--tb-accent)] bg-[var(--tb-surface)] text-[var(--tb-accent)] hover:bg-[var(--tb-accent-soft)] focus-visible:ring-[var(--tb-accent)]",
  accent:
    "bg-[var(--tb-accent)] text-white hover:brightness-95 focus-visible:ring-[var(--tb-accent)] shadow-[0_8px_20px_-12px_color-mix(in_srgb,var(--tb-accent)_55%,transparent)]",
  ghost:
    "bg-[var(--tb-interactive)] text-[var(--tb-ink-soft)] hover:bg-[var(--tb-muted)] focus-visible:ring-[var(--tb-border)]",
  outline:
    "border border-[var(--tb-border)] bg-[var(--tb-surface)] text-[var(--tb-ink-soft)] hover:bg-[var(--tb-interactive)] focus-visible:ring-[var(--tb-border)]",
  danger:
    "border border-[var(--tb-danger)] bg-[var(--tb-surface)] text-[var(--tb-danger)] hover:bg-[var(--tb-danger-soft)] focus-visible:ring-[var(--tb-danger)]",
} as const;

const sizes = {
  sm: "h-8 rounded-[var(--tb-radius-field)] px-3 text-xs",
  md: "h-10 rounded-[var(--tb-radius-field)] px-4 text-sm",
  lg: "h-11 rounded-[var(--tb-radius-control)] px-5 text-[0.95rem]",
} as const;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  busy?: boolean;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  busy = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-[family-name:var(--font-outfit)] font-semibold tracking-tight transition duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--tb-canvas)] disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      <BusyText busy={busy}>{children}</BusyText>
    </button>
  );
}
