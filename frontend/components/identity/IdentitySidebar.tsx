"use client";

import { NavIcon } from "@/components/layout/NavIcon";
import {
  COMPANY_NAV_GROUPS,
  COMPANY_SPACE_NAV,
  filterNavItems,
  isNavActive,
  type NavIconKey,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { identityApi } from "@/lib/api/identityApi";

const GROUP_ICONS: Record<(typeof COMPANY_NAV_GROUPS)[number], NavIconKey> = {
  Company: "building",
  Team: "users",
  Access: "roles",
  Security: "shield",
};

export function IdentitySidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const { permissions, hasPermission, business } = useAuth();
  const [pendingInvites, setPendingInvites] = useState(0);

  const items = useMemo(
    () => filterNavItems(COMPANY_SPACE_NAV, (code) => permissions.includes(code)),
    [permissions],
  );

  useEffect(() => {
    if (!hasPermission("users.invite") && !hasPermission("users.read")) return;
    void identityApi
      .listInvitations({ status: "pending", page: 1, page_size: 1 })
      .then((result) => setPendingInvites(result.meta.total))
      .catch(() => setPendingInvites(0));
  }, [hasPermission]);

  return (
    <aside className="tb-id-sidebar">
      <div className="tb-id-sidebar-inner">
        <div className="tb-id-sidebar-brand">
          <p className="text-[0.62rem] font-extrabold uppercase tracking-[0.18em] text-[var(--tb-secondary)]">
            Company
          </p>
          <p className="mt-1 font-[family-name:var(--font-outfit)] text-base font-semibold tracking-tight text-[var(--tb-ink)]">
            {business?.name ?? "Company identity"}
          </p>
          {business?.email_domain ? (
            <p className="mt-0.5 text-[0.72rem] font-semibold text-[var(--tb-muted-fg)]">
              @{business.email_domain}
            </p>
          ) : null}
        </div>

        <nav className="tb-id-sidebar-nav" aria-label="Company identity">
          {COMPANY_NAV_GROUPS.map((group) => {
            const groupItems = items.filter((item) => item.group === group);
            if (groupItems.length === 0) return null;
            return (
              <div key={group} className="tb-id-sidebar-group">
                <p className="tb-id-sidebar-group-label">
                  <NavIcon name={GROUP_ICONS[group]} className="h-3.5 w-3.5 opacity-70" />
                  {group}
                </p>
                <ul>
                  {groupItems.map((item) => {
                    const active = isNavActive(pathname, item.href, search);
                    const showBadge =
                      item.key === "invites" && pendingInvites > 0;
                    return (
                      <li key={item.key}>
                        <Link
                          href={item.href}
                          data-active={active}
                          className={cn("tb-id-sidebar-link", active && "is-active")}
                        >
                          <NavIcon name={item.icon} className="h-4 w-4" />
                          <span className="min-w-0 flex-1 truncate">{item.label}</span>
                          {showBadge ? (
                            <span className="tb-id-sidebar-badge">{pendingInvites}</span>
                          ) : null}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
