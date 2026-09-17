"use client";

import { Select } from "@/components/ui/Select";
import { useAuth } from "@/providers/AuthProvider";

export function BusinessSwitcher() {
  const { businesses, business, setBusiness } = useAuth();

  if (businesses.length === 0) {
    return (
      <span className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
        No business context
      </span>
    );
  }

  return (
    <Select
      aria-label="Switch business"
      className="min-w-[12rem]"
      value={business?.id ?? businesses[0]?.id ?? ""}
      onChange={(e) => {
        const next = businesses.find((b) => b.id === e.target.value) ?? null;
        setBusiness(next);
      }}
      options={businesses.map((b) => ({ value: b.id, label: b.name }))}
    />
  );
}
