"use client";

import { buttonClass } from "@/components/ui/Button";
import { BusyText } from "@/components/ui/LoadingState";
import { cn } from "@/lib/utils";
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  useState,
} from "react";

type AuthFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "size"> & {
  label: string;
  error?: string;
  icon?: "mail" | "lock" | "briefcase" | "building" | "user" | "search";
  trailing?: ReactNode;
  size?: "md" | "sm";
  ok?: boolean;
  requiredMark?: boolean;
};

export function AuthField({
  label,
  error,
  icon,
  trailing,
  className,
  id,
  type,
  size = "md",
  ok,
  requiredMark,
  ...props
}: AuthFieldProps) {
  const inputId = id ?? props.name;
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  const resolvedType = isPassword && show ? "text" : type;
  const compact = size === "sm";
  const showOk = Boolean(ok) && !error && !isPassword;

  return (
    <div className={cn("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      <label
        htmlFor={inputId}
        className={cn("tb-field-label", compact ? "text-[0.75rem]" : "text-[0.8125rem]")}
      >
        {label}
        {requiredMark || props.required ? <span className="tb-req">*</span> : null}
      </label>
      <div className="relative">
        {icon ? (
          <span className="pointer-events-none absolute left-3 top-1/2 z-[1] -translate-y-1/2 text-subtle-foreground">
            <FieldIcon name={icon} />
          </span>
        ) : null}
        <input
          id={inputId}
          type={resolvedType}
          data-state={error ? "error" : showOk ? "ok" : undefined}
          className={cn(
            "tb-field",
            compact ? "h-9" : "h-11",
            icon ? "tb-has-icon" : undefined,
            isPassword || trailing || showOk ? "tb-has-trailing" : undefined,
            className,
          )}
          {...props}
        />
        {isPassword ? (
          <button
            type="button"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle-foreground transition hover:text-heading"
            aria-label={show ? "Hide password" : "Show password"}
            onClick={() => setShow((v) => !v)}
          >
            {show ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        ) : showOk ? (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-success">
            <CheckIcon />
          </span>
        ) : trailing ? (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle-foreground">
            {trailing}
          </span>
        ) : null}
      </div>
      {error ? (
        <p className="tb-hint" data-tone="error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type AuthSelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> & {
  label: string;
  error?: string;
  icon?: "building" | "briefcase";
  options: { value: string; label: string }[];
  placeholder?: string;
  size?: "md" | "sm";
  requiredMark?: boolean;
};

export function AuthSelect({
  label,
  error,
  icon = "building",
  options,
  placeholder = "Select type",
  className,
  id,
  size = "md",
  requiredMark,
  ...props
}: AuthSelectProps) {
  const selectId = id ?? props.name;
  const compact = size === "sm";
  return (
    <div className={cn("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      <label
        htmlFor={selectId}
        className={cn("tb-field-label", compact ? "text-[0.75rem]" : "text-[0.8125rem]")}
      >
        {label}
        {requiredMark || props.required ? <span className="tb-req">*</span> : null}
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 z-[1] -translate-y-1/2 text-subtle-foreground">
          <FieldIcon name={icon} />
        </span>
        <select
          id={selectId}
          data-state={error ? "error" : undefined}
          className={cn("tb-field tb-has-icon tb-has-trailing", compact ? "h-9" : "h-11", className)}
          {...props}
        >
          <option value="">{placeholder}</option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 z-[1] -translate-y-1/2 text-subtle-foreground">
          <ChevronIcon />
        </span>
      </div>
      {error ? (
        <p className="tb-hint" data-tone="error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function AuthSubmitButton({
  children,
  pending,
  tone = "green",
  className,
  disabled,
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  pending?: boolean;
  tone?: "green" | "orange";
  size?: "md" | "sm";
}) {
  return (
    <button
      type="submit"
      disabled={pending || disabled}
      aria-busy={pending || undefined}
      className={buttonClass({
        variant: tone === "orange" ? "accent" : "primary",
        size: size === "sm" ? "md" : "lg",
        block: true,
        className,
      })}
      {...props}
    >
      <BusyText busy={pending}>{children}</BusyText>
      {pending ? null : <ArrowIcon />}
    </button>
  );
}

export function AuthCheckbox({
  label,
  checked,
  onChange,
  id,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (next: boolean) => void;
  id: string;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-soft">
      <span className="relative mt-0.5 inline-flex h-[1.1rem] w-[1.1rem] shrink-0">
        <input
          id={id}
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="absolute inset-0 rounded-[4px] border border-input bg-[var(--tb-field-bg)] transition peer-checked:border-[var(--tb-form-orange)] peer-checked:bg-[var(--tb-form-orange)] peer-focus-visible:ring-2 peer-focus-visible:ring-[var(--tb-form-orange)]/25" />
        <svg
          className="pointer-events-none absolute inset-0 m-auto hidden h-3 w-3 text-white peer-checked:block"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
        >
          <path
            d="M2.5 6.2 4.8 8.5 9.5 3.5"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span>{label}</span>
    </label>
  );
}

function FieldIcon({
  name,
}: {
  name: "mail" | "lock" | "briefcase" | "building" | "user" | "search";
}) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "mail":
      return (
        <svg {...common}>
          <rect x="2" y="3.5" width="12" height="9" rx="1.5" />
          <path d="m2.5 4.5 5.5 4 5.5-4" />
        </svg>
      );
    case "lock":
      return (
        <svg {...common}>
          <rect x="3.5" y="7" width="9" height="6.5" rx="1.5" />
          <path d="M5.5 7V5.4a2.5 2.5 0 0 1 5 0V7" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="7" cy="7" r="4" />
          <path d="m10.5 10.5 3 3" />
        </svg>
      );
    case "briefcase":
      return (
        <svg {...common}>
          <rect x="2" y="5" width="12" height="8.5" rx="1.5" />
          <path d="M6 5V3.8A1.3 1.3 0 0 1 7.3 2.5h1.4A1.3 1.3 0 0 1 10 3.8V5M2 8.5h12" />
        </svg>
      );
    case "building":
      return (
        <svg {...common}>
          <path d="M3 13.5V4.5A1.5 1.5 0 0 1 4.5 3h7A1.5 1.5 0 0 1 13 4.5v9" />
          <path d="M6 6h1.2M8.8 6H10M6 8.5h1.2M8.8 8.5H10M6 11h4" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="8" cy="5.5" r="2.5" />
          <path d="M3.5 13.5c.8-2.4 2.4-3.5 4.5-3.5s3.7 1.1 4.5 3.5" />
        </svg>
      );
  }
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M3.5 8.2 6.4 11 12.5 4.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8s-2.5 4.5-6.5 4.5S1.5 8 1.5 8Z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="m2 2 12 12M6.5 6.6A2 2 0 0 0 9.4 9.5M4.2 4.4C2.6 5.5 1.5 8 1.5 8s2.5 4.5 6.5 4.5c1.2 0 2.3-.4 3.2-1M7.2 3.6c.26-.05.53-.1.8-.1 4 0 6.5 4.5 6.5 4.5a11 11 0 0 1-1.5 1.9"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
      <path
        d="M3 4.5 6 7.5 9 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M3 8h10M13 8 9.5 4.5M13 8 9.5 11.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
