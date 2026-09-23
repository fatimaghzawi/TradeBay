"use client";

import { statusTone, type StatusTone } from "@/lib/team";

const TONE_MAP: Record<StatusTone, "ok" | "wait" | "off" | "bad"> = {
  active: "ok",
  pending: "wait",
  removed: "off",
  suspended: "bad",
  expired: "off",
  neutral: "off",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="tb-status" data-tone={TONE_MAP[statusTone(status)]}>
      {status === "invited" ? "Pending" : status}
    </span>
  );
}
