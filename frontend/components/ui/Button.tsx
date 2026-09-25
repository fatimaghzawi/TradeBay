import { cn } from "@/lib/utils";
import { BusyText } from "@/components/ui/LoadingState";
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "accent"
  | "outline"
  | "ghost"
  | "destructive"
  | "danger"
  | "success"
  | "link";

export type ButtonSize = "sm" | "md" | "lg" | "icon";

export function buttonClass({
  variant = "primary",
  size = "md",
  block = false,
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  className?: string;
} = {}) {
  return cn(
    "tb-btn",
    `tb-btn--${variant}`,
    size !== "md" && `tb-btn--${size}`,
    block && "tb-btn--block",
    className,
  );
}

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  busy?: boolean;
  block?: boolean;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  busy = false,
  block = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={buttonClass({ variant, size, block, className })}
      {...props}
    >
      <BusyText busy={busy}>{children}</BusyText>
    </button>
  );
}
