"use client";

import { cn } from "@/lib/utils";
import { useState, type ReactNode } from "react";

export type TabItem = { key: string; label: string; content: ReactNode };

export type TabsProps = {
  items: TabItem[];
  defaultKey?: string;
  className?: string;
};

export function Tabs({ items, defaultKey, className }: TabsProps) {
  const [active, setActive] = useState(defaultKey ?? items[0]?.key ?? "");
  const current = items.find((t) => t.key === active) ?? items[0];

  return (
    <div className={className}>
      <div
        role="tablist"
        className="flex flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-1"
      >
        {items.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={tab.key === active}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition",
              tab.key === active
                ? "bg-surface text-primary shadow-sm"
                : "text-muted-foreground hover:text-primary",
            )}
            onClick={() => setActive(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="mt-4">
        {current?.content}
      </div>
    </div>
  );
}
