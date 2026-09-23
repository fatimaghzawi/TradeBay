"use client";

import { Logo } from "@/components/layout/Logo";
import { NavIcon } from "@/components/layout/NavIcon";
import { useShell } from "@/components/layout/ShellContext";
import type { NavItem, WorkspaceNav } from "@/lib/navigation";
import { filterNavItems, isNavActive } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";

function NavLink({
  item,
  onNavigate,
}: {
  item: NavItem;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = isNavActive(pathname, item.href, searchParams.toString());

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "tb-app-sidebar-link group relative mx-1 flex items-center gap-3 rounded-xl px-3 py-2.5 text-[0.9rem] font-medium transition",
        "font-[family-name:var(--font-outfit)]",
        active && "is-active",
      )}
    >
      <NavIcon name={item.icon} className="tb-app-sidebar-icon" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

function groupItems(items: NavItem[]): { group: string | null; items: NavItem[] }[] {
  const sections: { group: string | null; items: NavItem[] }[] = [];
  for (const item of items) {
    const group = item.group ?? null;
    const last = sections[sections.length - 1];
    if (last && last.group === group) {
      last.items.push(item);
    } else {
      sections.push({ group, items: [item] });
    }
  }
  return sections;
}

export function AppSidebar({ nav }: { nav: WorkspaceNav }) {
  const { mobileNavOpen, setMobileNavOpen } = useShell();
  const { permissions } = useAuth();
  const close = () => setMobileNavOpen(false);
  const primary = useMemo(
    () => filterNavItems(nav.primary, (code) => permissions.includes(code)),
    [permissions, nav.primary],
  );
  const secondary = useMemo(
    () => filterNavItems(nav.secondary, (code) => permissions.includes(code)),
    [permissions, nav.secondary],
  );
  const grouped = useMemo(() => groupItems(primary), [primary]);
  const showGroups = nav.kind === "platform" && grouped.some((g) => g.group);

  const panel = (
    <aside className="tb-app-sidebar relative flex h-screen w-[var(--tb-sidebar-width)] shrink-0 flex-col overflow-hidden">
      <div className="relative z-[1] flex h-full flex-col px-2 pb-4 pt-5">
        <div className="mb-4 px-3">
          <Logo compact href={nav.kind === "platform" ? "/admin" : "/dashboard"} />
          {nav.kind === "platform" ? (
            <p className="tb-app-sidebar-tagline mt-3 px-1">{nav.tagline}</p>
          ) : null}
        </div>

        <nav className="tb-sidebar-scroll flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
          {showGroups
            ? grouped.map((section, index) => (
                <div
                  key={section.group ?? `ungrouped-${index}`}
                  className="mb-2"
                >
                  {section.group ? (
                    <p className="tb-app-sidebar-group px-4 pb-1 pt-2">{section.group}</p>
                  ) : null}
                  {section.items.map((item) => (
                    <NavLink key={item.key} item={item} onNavigate={close} />
                  ))}
                </div>
              ))
            : primary.map((item) => (
                <NavLink key={item.key} item={item} onNavigate={close} />
              ))}

          <div className="mt-auto space-y-3 pt-4">
            <div className="tb-app-sidebar-foot flex flex-col gap-0.5 pt-3">
              {secondary.map((item) => (
                <NavLink key={item.key} item={item} onNavigate={close} />
              ))}
            </div>
          </div>
        </nav>
      </div>
    </aside>
  );

  return (
    <>
      <div className="relative z-20 hidden shrink-0 lg:block">{panel}</div>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/50"
            onClick={close}
          />
          <div className="absolute inset-y-0 left-0 shadow-2xl">{panel}</div>
        </div>
      ) : null}
    </>
  );
}
