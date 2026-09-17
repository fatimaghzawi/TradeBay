"use client";

import { LoadingState } from "@/components/ui/LoadingState";
import { useAuth } from "@/providers/AuthProvider";
import type { ReactNode } from "react";

export function DashboardGate({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl py-12">
        <LoadingState rows={4} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
