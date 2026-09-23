"use client";

import { AppStateAction, AppStateFrame } from "@/components/ui/AppState";
import { LoadingState } from "@/components/ui/LoadingState";
import { isGuestAllowedPath } from "@/lib/guestAccess";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

export function DashboardGate({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const guestOk = isGuestAllowedPath(pathname);

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !guestOk) {
      const next = `${window.location.pathname}${window.location.search}`;
      const login =
        next && next !== ROUTES.login
          ? `${ROUTES.login}?next=${encodeURIComponent(next)}`
          : ROUTES.login;
      router.replace(login);
    }
  }, [guestOk, isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="tb-app flex min-h-screen items-center justify-center px-4">
        <LoadingState
          variant="page"
          title="Loading TradeBay"
          message="Signing you into the workspace…"
        />
      </div>
    );
  }

  if (!isAuthenticated && guestOk) {
    return <>{children}</>;
  }

  if (!isAuthenticated) {
    const next =
      typeof window !== "undefined"
        ? `${window.location.pathname}${window.location.search}`
        : "";
    const loginHref =
      next && next !== ROUTES.login
        ? `${ROUTES.login}?next=${encodeURIComponent(next)}`
        : ROUTES.login;
    return (
      <div className="tb-app flex min-h-screen items-center justify-center px-4">
        <AppStateFrame
          tone="empty"
          size="page"
          title="Sign in required"
          body={<p>Redirecting you to login. If nothing happens, continue manually.</p>}
          actions={
            <AppStateAction href={loginHref} tone="primary">
              Go to login
            </AppStateAction>
          }
        />
      </div>
    );
  }

  return <>{children}</>;
}
