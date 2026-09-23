"use client";

import { CartButton } from "@/components/cart/CartButton";
import { FavoritesButton } from "@/components/cart/FavoritesButton";
import { ChatBell } from "@/components/layout/ChatBell";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { Logo } from "@/components/layout/Logo";
import { NavIcon } from "@/components/layout/NavIcon";
import { useShell } from "@/components/layout/ShellContext";
import { UserMenu } from "@/components/layout/UserMenu";
import { ROUTES } from "@/lib/constants";
import type { NavItem, NavIconKey, WorkspaceNav } from "@/lib/navigation";
import {
  BUYER_COMMERCE_NAV_GROUPS,
  BUYER_INVENTORY_NAV_GROUPS,
  COMPANY_NAV_GROUPS,
  COMPANY_SPACE_NAV,
  SUPPLIER_COMMERCE_NAV_GROUPS,
  SUPPLIER_INVENTORY_NAV_GROUPS,
  filterNavItems,
  isCompanySpacePath,
  isNavActive,
  isNavItemActive,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

function NavLink({
  item,
  onNavigate,
  workspaceKind,
}: {
  item: NavItem;
  onNavigate?: () => void;
  workspaceKind: WorkspaceNav["kind"];
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = isNavItemActive(pathname, item, searchParams.toString());

  if (item.children?.length) {
    return (
      <SpaceMenu item={item} onNavigate={onNavigate} workspaceKind={workspaceKind} />
    );
  }

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      data-active={active}
      data-featured={item.key === "ai-sourcing" ? "true" : undefined}
      className={cn(
        "tb-navbar-link",
        item.key === "ai-sourcing" && "tb-navbar-link-bay",
      )}
    >
      {item.key === "ai-sourcing" ? (
        <span className="tb-navbar-bay-mark" aria-hidden>
          ✦
        </span>
      ) : null}
      {item.label}
    </Link>
  );
}

function SpaceMenu({
  item,
  onNavigate,
  workspaceKind,
}: {
  item: NavItem;
  onNavigate?: () => void;
  workspaceKind: WorkspaceNav["kind"];
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = isNavItemActive(pathname, item, searchParams.toString());
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const children = item.children ?? [];
  const isInventory = item.key === "inventory";
  const isCommerce = item.key === "procurement";
  const isBuyerInventory = isInventory && workspaceKind === "buyer";
  const isBuyerCommerce = isCommerce && workspaceKind === "buyer";
  const groups = isInventory
    ? isBuyerInventory
      ? BUYER_INVENTORY_NAV_GROUPS
      : SUPPLIER_INVENTORY_NAV_GROUPS
    : isCommerce
      ? isBuyerCommerce
        ? BUYER_COMMERCE_NAV_GROUPS
        : SUPPLIER_COMMERCE_NAV_GROUPS
      : COMPANY_NAV_GROUPS;
  const panelKicker = isInventory
    ? isBuyerInventory
      ? "Marketplace"
      : "Your catalog"
    : isCommerce
      ? isBuyerCommerce
        ? "Procurement"
        : "Fulfilment"
      : "Company identity";
  const panelTitle = isInventory
    ? isBuyerInventory
      ? "Browse & order"
      : "Manage products & stock"
    : isCommerce
      ? isBuyerCommerce
        ? "Buy & receive"
        : "Ship & settle"
      : "Build your company";

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        data-active={active || open}
        className="tb-navbar-link"
      >
        {item.label}
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
          className={cn("tb-nav-fly-chevron", open && "is-open")}
        >
          <path
            d="M2.5 4.5 6 8l3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open ? (
        <div className="tb-nav-fly" role="menu" aria-label={item.label}>
          <div className="tb-nav-fly__bloom" aria-hidden />
          <header className="tb-nav-fly__head">
            <p className="tb-nav-fly__kicker">{panelKicker}</p>
            <p className="tb-nav-fly__title">{panelTitle}</p>
          </header>
          <div className="tb-nav-fly__list">
            {groups.map((group) => {
              const groupItems = children.filter((child) => child.group === group);
              if (groupItems.length === 0) return null;
              return (
                <div key={group} className="tb-nav-fly__group">
                  <p className="tb-nav-fly__group-label">{group}</p>
                  {groupItems.map((child, index) => {
                    const childActive = isNavActive(
                      pathname,
                      child.href,
                      searchParams.toString(),
                    );
                    return (
                      <Link
                        key={child.key}
                        href={child.href}
                        role="menuitem"
                        title={child.hint || child.label}
                        data-active={childActive}
                        onClick={() => {
                          setOpen(false);
                          onNavigate?.();
                        }}
                        className="tb-nav-fly__link"
                        style={{ animationDelay: `${index * 28}ms` }}
                      >
                        <span className="tb-nav-fly__icon" aria-hidden>
                          <NavIcon name={child.icon} />
                        </span>
                        <span className="tb-nav-fly__label">{child.label}</span>
                        <span className="tb-nav-fly__go" aria-hidden>
                          →
                        </span>
                      </Link>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CompanySpaceBar({
  items,
  onNavigate,
}: {
  items: NavItem[];
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const groupMeta: Record<
    (typeof COMPANY_NAV_GROUPS)[number],
    { icon: NavIconKey; label: string }
  > = {
    Company: { icon: "building", label: "Company" },
    Team: { icon: "users", label: "Team" },
    Access: { icon: "roles", label: "Access" },
    Security: { icon: "shield", label: "Security" },
  };

  useEffect(() => {
    setOpenGroup(null);
  }, [pathname, search]);

  useEffect(() => {
    if (!openGroup) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpenGroup(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenGroup(null);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [openGroup]);

  return (
    <div className="tb-company-space" ref={rootRef}>
      <div className="mx-auto flex max-w-[92rem] items-center gap-3 px-4 sm:px-6 lg:px-8">
        <div className="hidden shrink-0 items-center gap-2 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--tb-accent)] shadow-[0_0_0_3px_color-mix(in_srgb,var(--tb-accent)_20%,transparent)]" />
          <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-[var(--tb-secondary)]">
            Company identity
          </p>
        </div>
        <nav className="tb-company-icon-nav" aria-label="Company identity sections">
          {COMPANY_NAV_GROUPS.map((group) => {
            const groupItems = items.filter((item) => item.group === group);
            if (groupItems.length === 0) return null;
            const meta = groupMeta[group];
            const groupActive = groupItems.some((item) =>
              isNavActive(pathname, item.href, search),
            );
            const open = openGroup === group;

            return (
              <div key={group} className="tb-company-icon-wrap">
                <button
                  type="button"
                  className="tb-company-icon-btn"
                  data-active={groupActive}
                  data-open={open}
                  aria-expanded={open}
                  aria-haspopup="menu"
                  aria-label={meta.label}
                  title={meta.label}
                  onClick={() => setOpenGroup((cur) => (cur === group ? null : group))}
                >
                  <NavIcon name={meta.icon} className="h-4 w-4" />
                  <span className="tb-company-icon-name">{meta.label}</span>
                </button>

                {open ? (
                  <div className="tb-company-icon-menu" role="menu">
                    <p className="tb-company-icon-menu-label">{meta.label}</p>
                    {groupItems.map((item) => {
                      const active = isNavActive(pathname, item.href, search);
                      return (
                        <Link
                          key={item.key}
                          href={item.href}
                          role="menuitem"
                          title={item.hint || item.label}
                          data-active={active}
                          className="tb-company-icon-link"
                          onClick={() => {
                            setOpenGroup(null);
                            onNavigate?.();
                          }}
                        >
                          <span className="tb-company-icon-link-icon">
                            <NavIcon name={item.icon} className="h-3.5 w-3.5" />
                          </span>
                          <span className="tb-company-icon-link-label">{item.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

export function AppNavbar({
  nav,
  showCompanySpace = true,
}: {
  nav: WorkspaceNav;
  showCompanySpace?: boolean;
}) {
  const { mobileNavOpen, setMobileNavOpen, toggleMobileNav } = useShell();
  const { permissions, business } = useAuth();
  const pathname = usePathname();
  const close = () => setMobileNavOpen(false);
  const items = useMemo(
    () => [
      ...filterNavItems(nav.primary, (code) => permissions.includes(code)),
      ...filterNavItems(nav.secondary, (code) => permissions.includes(code)),
    ],
    [permissions, nav.primary, nav.secondary],
  );
  const companyItems = useMemo(
    () => filterNavItems(COMPANY_SPACE_NAV, (code) => permissions.includes(code)),
    [permissions],
  );
  const inCompany = isCompanySpacePath(pathname);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname, setMobileNavOpen]);

  return (
    <header className="tb-navbar">
      <div className="mx-auto flex h-[var(--tb-topbar-height)] max-w-[92rem] items-center gap-5 px-4 sm:px-6 lg:px-8">
        <Logo compact href={nav.kind === "platform" ? ROUTES.admin.home : ROUTES.dashboard} />
        <span className="hidden h-7 w-px bg-[var(--tb-line)] lg:block" aria-hidden />

        <nav className="hidden min-w-0 flex-1 items-center lg:flex">
          {items.map((item) => (
            <NavLink key={item.key} item={item} workspaceKind={nav.kind} />
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2.5">
          <FavoritesButton />
          <CartButton />
          <ChatBell />
          <NotificationBell />
          <div className="tb-nav-who">
            {business && business.type !== "platform" ? (
              <Link
                href={ROUTES.businesses}
                className="tb-nav-biz"
                title={`${business.name}${business.email_domain ? ` · @${business.email_domain}` : ""}`}
              >
                <span className="tb-nav-biz__mark" aria-hidden>
                  {(business.name || "TB")
                    .split(/\s+/)
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((p) => p[0]?.toUpperCase() ?? "")
                    .join("") || "TB"}
                </span>
                <span className="tb-nav-biz__copy">
                  <span className="tb-nav-biz__name">{business.name}</span>
                  {business.email_domain ? (
                    <span className="tb-nav-biz__domain">
                      <em>@</em>
                      {business.email_domain}
                    </span>
                  ) : null}
                </span>
              </Link>
            ) : null}
            <UserMenu company={business?.name} />
          </div>
          <button
            type="button"
            aria-label="Open navigation"
            onClick={toggleMobileNav}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--tb-border)] bg-[var(--tb-surface)] text-[var(--tb-ink)] lg:hidden"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path
                d="M3 5h12M3 9h12M3 13h12"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>

      {showCompanySpace && inCompany ? <CompanySpaceBar items={companyItems} /> : null}

      {mobileNavOpen ? (
        <div className="border-t border-[var(--tb-line)] bg-[var(--tb-surface)] px-4 py-4 lg:hidden">
          <nav className="flex flex-col">
            {items.map((item) =>
              item.children?.length ? (
                <div key={item.key} className="mt-2">
                  <p className="tb-nav-fly__mobile-kicker">{item.label}</p>
                  <div className="tb-nav-fly__list">
                    {item.children.map((child) => (
                      <Link
                        key={child.key}
                        href={child.href}
                        title={child.hint || child.label}
                        onClick={close}
                        className="tb-nav-fly__link"
                      >
                        <span className="tb-nav-fly__icon" aria-hidden>
                          <NavIcon name={child.icon} />
                        </span>
                        <span className="tb-nav-fly__label">{child.label}</span>
                        <span className="tb-nav-fly__go" aria-hidden>
                          →
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              ) : (
                <Link
                  key={item.key}
                  href={item.href}
                  onClick={close}
                  className={cn(
                    "border-b border-[var(--tb-line)] py-3 font-[family-name:var(--font-outfit)] text-sm font-semibold text-[var(--tb-ink)]",
                    item.key === "ai-sourcing" && "tb-navbar-bay-mobile",
                  )}
                >
                  {item.key === "ai-sourcing" ? (
                    <span className="mr-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-[var(--tb-accent)] text-xs text-white">
                      ✦
                    </span>
                  ) : null}
                  {item.label}
                  {item.key === "ai-sourcing" && item.hint ? (
                    <span className="mt-1 block text-xs font-medium text-[var(--tb-muted-fg)]">
                      {item.hint}
                    </span>
                  ) : null}
                </Link>
              ),
            )}
          </nav>
          <div className="mt-4 flex flex-wrap items-center gap-2 sm:hidden">
            {business && business.type !== "platform" ? (
              <Link href={ROUTES.businesses} className="tb-nav-biz is-mobile" onClick={close}>
                <span className="tb-nav-biz__mark" aria-hidden>
                  {(business.name || "TB")
                    .split(/\s+/)
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((p) => p[0]?.toUpperCase() ?? "")
                    .join("") || "TB"}
                </span>
                <span className="tb-nav-biz__copy">
                  <span className="tb-nav-biz__name">{business.name}</span>
                  {business.email_domain ? (
                    <span className="tb-nav-biz__domain">
                      <em>@</em>
                      {business.email_domain}
                    </span>
                  ) : null}
                </span>
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </header>
  );
}
