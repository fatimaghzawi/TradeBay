"use client";

import { StatusBadge as BaseStatusBadge } from "@/components/ui/StatusBadge";

export function StatusBadge({ status }: { status: string }) {
  return (
    <BaseStatusBadge status={status} label={status === "invited" ? "Pending" : undefined} />
  );
}
