"use client";

import { useShell } from "@/components/layout/ShellContext";

export function SpaceSectionsBar({ label }: { label: string }) {
  const { mobileSpaceOpen, toggleMobileSpace } = useShell();

  return (
    <div className="tb-space-bar">
      <button
        type="button"
        className="tb-space-bar__btn"
        aria-expanded={mobileSpaceOpen}
        aria-controls="tb-space-sidebar-drawer"
        onClick={toggleMobileSpace}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path
            d="M2.5 4h11M2.5 8h11M2.5 12h7"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        <span>{label}</span>
        <span className="tb-space-bar__hint" aria-hidden>
          {mobileSpaceOpen ? "Close" : "Open"}
        </span>
      </button>
    </div>
  );
}
