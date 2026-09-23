"use client";

import { cn } from "@/lib/utils";

export function BusinessTypePicker({
  value,
  onChange,
}: {
  value: "buyer" | "supplier";
  onChange: (value: "buyer" | "supplier") => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <TypeCard
        selected={value === "buyer"}
        title="Buyer"
        badge="No doc review"
        body="Create a company and start sourcing immediately. Document verification is not required to buy."
        onSelect={() => onChange("buyer")}
      />
      <TypeCard
        selected={value === "supplier"}
        title="Supplier"
        badge="Verification required"
        body="Create a company, then upload registration documents. Selling unlocks after platform approval."
        onSelect={() => onChange("supplier")}
      />
    </div>
  );
}

function TypeCard({
  selected,
  title,
  badge,
  body,
  onSelect,
}: {
  selected: boolean;
  title: string;
  badge: string;
  body: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn("tb-card overflow-hidden text-left", selected && "ring-0")}
      data-kind="category"
      data-state={selected ? "selected" : undefined}
    >
      <div className="relative z-[1] flex flex-1 flex-col px-4 pb-3 pt-4">
        <div className="flex items-start justify-between gap-2">
          <span className="tb-card-icon" data-tone={title === "Supplier" ? "orange" : undefined}>
            {title === "Buyer" ? "BY" : "SU"}
          </span>
          <span
            className="tb-card-badge"
            data-tone={title === "Buyer" ? "ok" : "open"}
          >
            {badge}
          </span>
        </div>
        <span className="mt-3 font-[family-name:var(--font-outfit)] text-base font-bold text-[var(--tb-card-fg)]">
          {title}
        </span>
        <span className="mt-2 block flex-1 text-sm leading-relaxed text-[var(--tb-card-muted)]">
          {body}
        </span>
      </div>
      <div className="tb-card-footer justify-end">
        <span className="tb-card-go" aria-hidden>
          →
        </span>
      </div>
    </button>
  );
}
