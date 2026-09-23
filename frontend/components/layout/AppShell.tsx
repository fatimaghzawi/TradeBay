"use client";

import { AppNavbar } from "@/components/layout/AppNavbar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppTopBar } from "@/components/layout/AppTopBar";
import { ShoppingTraysHost } from "@/components/cart/ShoppingTrays";
import { IdentitySidebar } from "@/components/identity/IdentitySidebar";
import { InventorySidebar } from "@/components/catalog/InventorySidebar";
import { CommerceSidebar } from "@/components/procurement/CommerceSidebar";
import { ShellProvider } from "@/components/layout/ShellContext";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ROUTES } from "@/lib/constants";
import {
  getWorkspaceNav,
  isCommerceSpacePath,
  isCompanySpacePath,
  isInventorySpacePath,
  resolveWorkspaceKind,
} from "@/lib/navigation";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, type ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { business, user } = useAuth();
  const kind = resolveWorkspaceKind(business?.type, pathname);
  const nav = getWorkspaceNav(kind);
  const emailVerified = Boolean(user?.email_verified_at);
  const showVerifyBanner =
    Boolean(user) && !emailVerified && !pathname.startsWith("/verify-email");
  const useSidebar = kind === "platform";
  const useIdentitySidebar = !useSidebar && isCompanySpacePath(pathname);
  const useInventorySidebar = !useSidebar && !useIdentitySidebar && isInventorySpacePath(pathname);
  const useCommerceSidebar =
    !useSidebar && !useIdentitySidebar && !useInventorySidebar && isCommerceSpacePath(pathname);
  const useSpaceSidebar = useIdentitySidebar || useInventorySidebar || useCommerceSidebar;

  return (
    <ShellProvider>
      <div
        className={
          useSidebar
            ? "tb-app flex min-h-screen"
            : "tb-app flex min-h-screen flex-col"
        }
        data-workspace={kind}
      >
        {useSidebar ? (
          <Suspense
            fallback={
              <div className="hidden w-[var(--tb-sidebar-width)] shrink-0 border-r border-[var(--tb-border)] bg-[var(--tb-surface)] lg:block" />
            }
          >
            <AppSidebar key={business?.id ?? "no-business"} nav={nav} />
          </Suspense>
        ) : (
          <Suspense
            fallback={
              <div className="h-[var(--tb-topbar-height)] border-b border-[var(--tb-border)] bg-[var(--tb-surface)]" />
            }
          >
            <AppNavbar
              key={business?.id ?? "no-business"}
              nav={nav}
              showCompanySpace={!useSpaceSidebar}
            />
          </Suspense>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {useSidebar ? (
            <AppTopBar key={`top-${business?.id ?? "no-business"}`} nav={nav} />
          ) : null}
          <div className={useSpaceSidebar ? "tb-id-shell" : "contents"}>
            {useIdentitySidebar ? (
              <Suspense fallback={<div className="hidden w-[15.75rem] shrink-0 lg:block" />}>
                <IdentitySidebar />
              </Suspense>
            ) : null}
            {useInventorySidebar ? (
              <Suspense fallback={<div className="hidden w-[15.75rem] shrink-0 lg:block" />}>
                <InventorySidebar />
              </Suspense>
            ) : null}
            {useCommerceSidebar ? (
              <Suspense fallback={<div className="hidden w-[15.75rem] shrink-0 lg:block" />}>
                <CommerceSidebar />
              </Suspense>
            ) : null}
            <main className="relative min-w-0 flex-1 overflow-x-hidden px-4 py-5 sm:px-6 lg:px-8">
              <div className="relative mx-auto w-full max-w-[92rem]">
                {showVerifyBanner ? (
                  <div className="mb-5">
                    <FeedbackBanner
                      tone="warning"
                      title="Verify your email to use trading features"
                    >
                      Invites and other writes stay blocked until verified.{" "}
                      <Link
                        href={`${ROUTES.verifyEmail}?email=${encodeURIComponent(user?.email ?? "")}`}
                        className="font-semibold underline underline-offset-2"
                      >
                        Enter verification code
                      </Link>
                    </FeedbackBanner>
                  </div>
                ) : null}
                {children}
              </div>
            </main>
          </div>
        </div>
      </div>
      <ShoppingTraysHost />
    </ShellProvider>
  );
}
