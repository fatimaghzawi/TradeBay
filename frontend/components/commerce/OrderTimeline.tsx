import type { OrderTimelineStep } from "@/lib/api/procurementApi";
import { formatDate } from "@/lib/commerce/format";
import { cn } from "@/lib/utils";

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function TimelineIcon({ step }: { step: string }) {
  switch (step) {
    case "placed":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M7 4h10v16H7z" {...stroke} />
          <path d="M9 8h6M9 12h6M9 16h4" {...stroke} />
        </svg>
      );
    case "paid":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="3" y="6" width="18" height="12" rx="2" {...stroke} />
          <path d="M3 10h18M7 15h3" {...stroke} />
        </svg>
      );
    case "confirmed":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5v-7Z" {...stroke} />
          <path d="m9 12 2 2 4-4" {...stroke} />
        </svg>
      );
    case "shipped":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M3 13h11V8H3v5Z" {...stroke} />
          <path d="M14 13h3.5L20 16v3h-6v-6Z" {...stroke} />
          <circle cx="7" cy="19" r="1.6" {...stroke} />
          <circle cx="17" cy="19" r="1.6" {...stroke} />
        </svg>
      );
    case "delivered":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M12 21s6.5-5.2 6.5-10.2a6.5 6.5 0 1 0-13 0C5.5 15.8 12 21 12 21Z" {...stroke} />
          <circle cx="12" cy="10.8" r="2.2" {...stroke} />
        </svg>
      );
    case "cancelled":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="8" {...stroke} />
          <path d="m9 9 6 6M15 9l-6 6" {...stroke} />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="8" {...stroke} />
          <path d="m8.5 12.2 2.4 2.4 4.6-5" {...stroke} />
        </svg>
      );
  }
}

export function timelineHeadline(steps: OrderTimelineStep[] | undefined): OrderTimelineStep | null {
  if (!steps?.length) return null;
  const cancelled = steps.find((s) => s.state === "cancelled");
  if (cancelled) return cancelled;
  const done = steps.filter((s) => s.state === "done");
  const last = done[done.length - 1];
  if (last?.key === "completed") return last;
  return steps.find((s) => s.state === "current") ?? last ?? steps[0] ?? null;
}

export function OrderTimeline({
  steps,
  compact = false,
  className,
}: {
  steps: OrderTimelineStep[] | undefined;
  compact?: boolean;
  className?: string;
}) {
  if (!steps?.length) return null;
  const count = steps.length;
  const lastDone = steps.reduce((acc, s, i) => (s.state === "done" ? i : acc), -1);
  const cancelledIdx = steps.findIndex((s) => s.state === "cancelled");
  const reach = cancelledIdx >= 0 ? cancelledIdx : lastDone;
  const fill = count > 1 ? (Math.max(reach, 0) / (count - 1)) * 100 : 0;
  const inset = `${50 / count}%`;

  return (
    <div className={cn("tb-shein tb-co-timeline", compact && "tb-co-timeline--compact", className)}>
      <div className="tb-shein-stepper">
        <div className="tb-shein-stepper__line" style={{ left: inset, right: inset }} aria-hidden>
          <span style={{ width: `${fill}%` }} />
        </div>
        <ol
          className="tb-shein-stepper__list"
          style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}
        >
          {steps.map((step) => (
            <li
              key={step.key}
              data-done={step.state === "done" || undefined}
              data-current={step.state === "current" || undefined}
              data-todo={step.state === "upcoming" || step.state === "skipped" || undefined}
              data-cancelled={step.state === "cancelled" || undefined}
              aria-current={step.state === "current" ? "step" : undefined}
            >
              <span className="tb-shein-stepper__icon">
                <TimelineIcon step={step.key} />
              </span>
              <strong>{step.label}</strong>
              {!compact ? <em>{step.at ? formatDate(step.at) : step.state === "current" ? "In progress" : "\u00a0"}</em> : null}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
