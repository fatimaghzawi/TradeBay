"use client";

import { AppStateFrame } from "@/components/ui/AppState";
import { BackLink } from "@/components/ui/BackLink";
import { LoadingState } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

export function PlatformAdminGate({ children }: { children: ReactNode }) {
  const { isLoading: authLoading, business } = useAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [allowed, setAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    if (business?.type === "platform") {
      setAllowed(true);
      setChecking(false);
      return;
    }

    let cancelled = false;
    setChecking(true);
    void identityApi
      .platformMe()
      .then((ctx) => {
        if (cancelled) return;
        if (ctx.platform_business && (ctx.membership_id || ctx.active_is_platform)) {
          setAllowed(true);
        } else {
          setAllowed(false);
          router.replace(ROUTES.dashboard);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setAllowed(false);
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn’t confirm staff access. Please try again.",
        );
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, business?.type, router]);

  if (authLoading || checking) {
    return (
      <div className="flex justify-center px-4 py-12">
        <LoadingState
          variant="section"
          title="Checking access"
          message="One moment…"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center px-4 py-10">
        <AppStateFrame
          tone="error"
          size="section"
          title="Access restricted"
          body={<p>{error}</p>}
          actions={
            <BackLink href={ROUTES.dashboard}>Back to dashboard</BackLink>
          }
        />
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="flex justify-center px-4 py-10">
        <AppStateFrame
          tone="empty"
          size="section"
          title="Platform admin only"
          body={
            <p>
              This area is for TradeBay staff. Switch to the platform business or use a
              staff account.
            </p>
          }
          actions={
            <BackLink href={ROUTES.dashboard}>Back to dashboard</BackLink>
          }
        />
      </div>
    );
  }

  return <>{children}</>;
}
