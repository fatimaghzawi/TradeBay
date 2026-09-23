import type { ReactNode } from "react";

/**
 * Business onboarding aside — unique leaf-framed panel for create/verify only.
 */
export function BusinessAsideCard({
  title,
  points,
  action,
  illustration = "warehouse",
}: {
  title: string;
  points: string[];
  action?: ReactNode;
  illustration?: "warehouse" | "docs";
}) {
  return (
    <aside className="relative overflow-hidden rounded-[1.5rem] border border-[#e2ebe6] bg-[#fffdf9] p-5 shadow-[0_16px_40px_rgba(21,36,29,0.06)] lg:p-6">
      <LeafCorner className="pointer-events-none absolute -right-6 -top-8 h-36 w-36 text-[#cfe3d6]" />
      <LeafCorner className="pointer-events-none absolute -bottom-10 -left-8 h-40 w-40 rotate-180 text-[#f3d0b8]/80" />

      <div className="relative">
        <div className="mb-4 flex h-32 items-end justify-center rounded-2xl bg-gradient-to-b from-[#f3f6f4] to-[#eaf3ee]">
          {illustration === "docs" ? <DocsArt /> : <WarehouseArt />}
        </div>
        <h2 className="font-[family-name:var(--font-instrument)] text-xl leading-snug tracking-tight text-[#0c1612]">
          {title}
        </h2>
        <ul className="mt-4 space-y-2.5">
          {points.map((point) => (
            <li key={point} className="flex gap-2.5 text-sm text-[#3f4f47]">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#e8f6ef] text-[0.65rem] font-bold text-[#1a6b4f]">
                ✓
              </span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
        {action ? <div className="mt-6">{action}</div> : null}
      </div>
    </aside>
  );
}

function LeafCorner({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 160 160" fill="currentColor" aria-hidden>
      <path d="M120 12c-36 22-58 62-48 110 32-14 58-4 84 24-8-56-12-100-36-134Z" />
      <path
        d="M40 40c28 14 42 52 30 90-26-8-46 6-64 30 8-52 14-90 34-120Z"
        opacity="0.55"
      />
    </svg>
  );
}

function WarehouseArt() {
  return (
    <svg viewBox="0 0 180 100" className="h-24 w-40" aria-hidden>
      <rect x="28" y="38" width="90" height="48" rx="4" fill="#0d3b2a" />
      <path d="M28 42 73 18l45 24H28Z" fill="#1a6b4f" />
      <rect x="48" y="54" width="18" height="32" fill="#e8ebe6" />
      <rect x="78" y="54" width="22" height="14" fill="#e86f2a" opacity="0.85" />
      <rect x="118" y="58" width="42" height="28" rx="3" fill="#e86f2a" />
      <circle cx="128" cy="88" r="6" fill="#0c1612" />
      <circle cx="150" cy="88" r="6" fill="#0c1612" />
      <rect x="118" y="50" width="18" height="10" fill="#c45b2a" />
    </svg>
  );
}

function DocsArt() {
  return (
    <svg viewBox="0 0 140 100" className="h-24 w-32" aria-hidden>
      <rect x="38" y="18" width="54" height="68" rx="6" fill="#0d3b2a" />
      <rect x="48" y="28" width="34" height="6" rx="2" fill="#e8ebe6" />
      <rect x="48" y="40" width="28" height="4" rx="2" fill="#1a6b4f" />
      <rect x="48" y="50" width="30" height="4" rx="2" fill="#1a6b4f" />
      <circle cx="98" cy="68" r="22" fill="#e8f6ef" />
      <path
        d="M88 68.5 95 75.5 110 58"
        fill="none"
        stroke="#1a6b4f"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
