"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { ROUTES } from "@/lib/constants";

export default function DashboardError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4 py-10">
      <ErrorState
        size="page"
        title="Workspace error"
        message="This screen failed to load. Try again, or return to your dashboard."
        onRetry={reset}
        homeHref={ROUTES.dashboard}
        homeLabel="Back to dashboard"
      />
    </div>
  );
}
