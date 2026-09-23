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
                  done || current ? "bg-[#e86f2a]" : "bg-[#dce5e0]",
                )}
              />
            ) : null}
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                  done && "bg-[#1a6b4f] text-white",
                  current && "bg-[#e86f2a] text-white",
                  !done && !current && "bg-[#eef3f0] text-[#6a726c]",
                )}
              >
                {done ? "✓" : step.id}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold sm:text-sm",
                  current
                    ? "text-[#e86f2a]"
                    : done
                      ? "text-[#1a6b4f]"
                      : "text-[#8a9690]",
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
