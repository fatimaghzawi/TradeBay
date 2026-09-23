"use client";

import { AppStateAction, AppStateFrame } from "@/components/ui/AppState";
import { LoadingState } from "@/components/ui/LoadingState";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import type { ReactNode } from "react";

type PermissionGateProps = {
  /** One or more permission codes. Any match grants access unless `requireAll`. */
  permission: string | string[];
  requireAll?: boolean;
  children: ReactNode;
  fallbackTitle?: string;
  fallbackDescription?: string;
  /** When true, signed-out visitors can still view the screen (explore mode). */
  allowGuest?: boolean;
};

export function PermissionGate({
  permission,
  requireAll = false,
  children,
  fallbackTitle = "Access restricted",
  fallbackDescription = "You don’t have access to this area. Contact your business administrator if you need access.",
  allowGuest = false,
}: PermissionGateProps) {
  const { hasPermission, isLoading, isAuthenticated } = useAuth();
  const codes = Array.isArray(permission) ? permission : [permission];
  const allowed = requireAll
    ? codes.every((code) => hasPermission(code))
    : codes.some((code) => hasPermission(code));

  if (isLoading) {
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

  if (!isAuthenticated && allowGuest) {
    return <>{children}</>;
  }

  if (!allowed) {
    return (
      <div className="flex justify-center px-4 py-10">
        <AppStateFrame
          tone="error"
          size="section"
          title={fallbackTitle}
          body={<p>{fallbackDescription}</p>}
          actions={
            <AppStateAction href={ROUTES.dashboard} tone="primary">
              Back to home →
            </AppStateAction>
          }
        />
      </div>
    );
  }

  return <>{children}</>;
}

/** Supplier inventory ops (stock, movements, pricing boards). Buyers browse products only. */
export function SupplierOnlyGate({
  children,
  fallbackTitle = "Supplier tools",
  fallbackDescription = "Stock, movements, and catalog management are available for supplier companies. Browse products in the marketplace instead.",
}: {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackDescription?: string;
}) {
  const { business, isLoading } = useAuth();

  if (isLoading) {
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

  if (business?.type !== "supplier") {
    return (
      <div className="flex justify-center px-4 py-10">
        <AppStateFrame
          tone="empty"
          size="section"
          title={fallbackTitle}
          body={<p>{fallbackDescription}</p>}
          actions={
            <AppStateAction href={ROUTES.inventoryProducts} tone="primary">
              Browse products →
            </AppStateAction>
          }
        />
      </div>
    );
  }

  return <>{children}</>;
}
