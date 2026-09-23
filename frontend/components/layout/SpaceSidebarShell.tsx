"use client";

import { useShell } from "@/components/layout/ShellContext";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

/**
 * Desktop sticky sidebar + mobile slide-over drawer for company / inventory / commerce spaces.
 */
export function SpaceSidebarShell({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  const { mobileSpaceOpen, setMobileSpaceOpen } = useShell();
  const pathname = usePathname();

  useEffect(() => {
    setMobileSpaceOpen(false);
  }, [pathname, setMobileSpaceOpen]);

  useEffect(() => {
    if (!mobileSpaceOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileSpaceOpen]);

  return (
    <>
      <div className="tb-space-sidebar-desktop">{children}</div>

      {mobileSpaceOpen ? (
        <div
          id="tb-space-sidebar-drawer"
          className="tb-space-sidebar-drawer"
          role="dialog"
          aria-modal="true"
          aria-label={label}
        >
          <button
            type="button"
            className="tb-space-sidebar-scrim"
            aria-label="Close sections"
            onClick={() => setMobileSpaceOpen(false)}
          />
          <div
            className="tb-space-sidebar-panel"
            onClick={(e) => {
              if ((e.target as HTMLElement).closest("a")) {
                setMobileSpaceOpen(false);
              }
            }}
          >
            <div className="tb-space-sidebar-drawer-head">
              <p>{label}</p>
              <button
                type="button"
                className="tb-space-sidebar-close"
                aria-label="Close"
                onClick={() => setMobileSpaceOpen(false)}
              >
                ✕
              </button>
            </div>
            <div className="tb-space-sidebar-drawer-body">{children}</div>
          </div>
        </div>
      ) : null}
    </>
  );
}
