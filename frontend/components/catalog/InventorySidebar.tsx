"use client";

import { NavIcon } from "@/components/layout/NavIcon";
import {
  BUYER_INVENTORY_NAV,
  BUYER_INVENTORY_NAV_GROUPS,
  SUPPLIER_INVENTORY_NAV,
  SUPPLIER_INVENTORY_NAV_GROUPS,
  filterNavItems,
  isNavActive,
  type NavIconKey,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";

const SUPPLIER_GROUP_ICONS: Record<
  (typeof SUPPLIER_INVENTORY_NAV_GROUPS)[number],
  NavIconKey
> = {
  Catalog: "catalog",
  Stock: "truck",
};

const BUYER_GROUP_ICONS: Record<(typeof BUYER_INVENTORY_NAV_GROUPS)[number], NavIconKey> = {
  Marketplace: "catalog",
};

export function InventorySidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const { permissions, business } = useAuth();

  const isSupplier = business?.type === "supplier";
  const spaceNav = isSupplier ? SUPPLIER_INVENTORY_NAV : BUYER_INVENTORY_NAV;
  const groups = isSupplier ? SUPPLIER_INVENTORY_NAV_GROUPS : BUYER_INVENTORY_NAV_GROUPS;
  const groupIcons = isSupplier ? SUPPLIER_GROUP_ICONS : BUYER_GROUP_ICONS;

  const items = useMemo(
    () => filterNavItems(spaceNav, (code) => permissions.includes(code)),
    [permissions, spaceNav],
  );

  const monogram = (business?.name ?? "TB").slice(0, 2).toUpperCase();

  return (
    <aside className="tb-id-sidebar tb-inv-sidebar">
      <div className="tb-id-sidebar-inner">
        <div className="tb-inv-sidebar-brand">
          <div className="tb-inv-sidebar-mark" aria-hidden>
            {monogram}
          </div>
          <div className="min-w-0">
            <p className="tb-inv-sidebar-kicker">
              {isSupplier ? "Inventory" : "Marketplace"}
            </p>
            <p className="tb-inv-sidebar-title">
              {isSupplier ? "Your catalog" : "Browse & order"}
            </p>
            <p className="tb-inv-sidebar-sub truncate">{business?.name ?? "TradeBay"}</p>
          </div>
        </div>

        <nav className="tb-id-sidebar-nav" aria-label={isSupplier ? "Inventory space" : "Marketplace"}>
          {groups.map((group) => {
            const groupItems = items.filter((item) => item.group === group);
            if (groupItems.length === 0) return null;
            return (
              <div key={group} className="tb-id-sidebar-group">
                <p className="tb-id-sidebar-group-label">
                  <NavIcon
                    name={groupIcons[group as keyof typeof groupIcons]}
                    className="h-3.5 w-3.5 opacity-70"
                  />
                  {group}
                </p>
                <ul>
                  {groupItems.map((item) => {
                    const active = isNavActive(pathname, item.href, search);
                    return (
                      <li key={item.key}>
                        <Link
                          href={item.href}
                          data-active={active}
                          className={cn("tb-id-sidebar-link", active && "is-active")}
                        >
                          <NavIcon name={item.icon} className="h-4 w-4" />
                          <span className="min-w-0 flex-1 truncate">{item.label}</span>
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
