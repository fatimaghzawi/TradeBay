"use client";

import { CartButton } from "@/components/cart/CartButton";
import { FavoritesButton } from "@/components/cart/FavoritesButton";
import { ChatBell } from "@/components/layout/ChatBell";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { PlatformSearch } from "@/components/layout/PlatformSearch";
import { useShell } from "@/components/layout/ShellContext";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { UserMenu } from "@/components/layout/UserMenu";
import type { WorkspaceNav } from "@/lib/navigation";
import { useAuth } from "@/providers/AuthProvider";

export function AppTopBar({ nav }: { nav: WorkspaceNav }) {
  const { toggleMobileNav } = useShell();
  const { business } = useAuth();
  const isPlatform = nav.kind === "platform";

  return (
    <header
      className={
        isPlatform
          ? "tb-app-topbar tb-app-topbar--platform sticky top-0 z-30 flex h-[var(--tb-topbar-height)] items-center gap-3 border-b px-3 backdrop-blur-md sm:px-6"
          : "sticky top-0 z-30 flex h-[var(--tb-topbar-height)] items-center gap-3 border-b border-border-strong bg-[color-mix(in_srgb,var(--tb-surface)_88%,transparent)] px-3 backdrop-blur-md sm:px-6"
      }
    >
      <button
        type="button"
        aria-label="Open navigation"
        onClick={toggleMobileNav}
        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border-strong bg-muted text-foreground lg:hidden"
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

      {isPlatform ? (
        <PlatformSearch nav={nav} />
      ) : (
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search</span>
          <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16 16l4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </span>
          <input
            type="search"
            placeholder={nav.searchPlaceholder}
            className="tb-icon-field h-11 w-full rounded-full border border-input bg-[var(--tb-field-bg)] py-0 pl-11 pr-4 text-sm text-[var(--tb-field-fg)] outline-none placeholder:text-[var(--tb-field-muted)] focus:border-[var(--tb-field-focus)]"
          />
        </label>
      )}

      {isPlatform ? null : (
        <>
          <FavoritesButton />
          <CartButton />
          <ChatBell />
        </>
      )}
      <NotificationBell />
      <ThemeToggle />
      {nav.kind === "platform" ? (
        <span className="tb-admin-badge hidden sm:inline-flex">Platform admin</span>
      ) : null}
      {isPlatform ? (
        <UserMenu company={business?.name} />
      ) : (
        <div className="tb-nav-who">
          {business && business.type !== "platform" ? (
            <span className="tb-nav-biz tb-nav-biz--inline" title={business.name}>
              <span className="tb-nav-biz__name">{business.name}</span>
            </span>
          ) : null}
          <UserMenu company={business?.name} />
        </div>
      )}
    </header>
  );
}
