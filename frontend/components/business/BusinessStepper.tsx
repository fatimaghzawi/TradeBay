"use client";

import { cn } from "@/lib/utils";

type Step = { id: number; label: string };

const BUYER_STEPS: Step[] = [
  { id: 1, label: "Tell us about your company" },
  { id: 2, label: "Ready to trade" },
];

const SUPPLIER_STEPS: Step[] = [
  { id: 1, label: "Tell us about your company" },
  { id: 2, label: "Establish your identity" },
  { id: 3, label: "Ready to trade" },
];

export function BusinessStepper({
  active,
  variant = "supplier",
}: {
  active: number;
  variant?: "buyer" | "supplier";
}) {
  const steps = variant === "buyer" ? BUYER_STEPS : SUPPLIER_STEPS;

  return (
    <ol className="flex flex-wrap items-center gap-2 sm:gap-3">
      {steps.map((step, index) => {
        const done = step.id < active;
        const current = step.id === active;
        return (
          <li key={step.id} className="flex items-center gap-2 sm:gap-3">
            {index > 0 ? (
              <span
                aria-hidden
                className={cn(
                  "hidden h-px w-6 sm:block sm:w-10",
                  done || current ? "bg-accent" : "bg-muted",
                )}
              />
            ) : null}
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                  done && "bg-primary text-primary-foreground",
                  current && "bg-accent text-accent-foreground",
                  !done && !current && "bg-muted text-muted-foreground",
                )}
              >
                {done ? "✓" : step.id}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold sm:text-sm",
                  current
                    ? "text-accent-text"
                    : done
                      ? "text-link"
                      : "text-subtle-foreground",
                )}
              >
                {step.label}
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
