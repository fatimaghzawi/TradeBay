"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { ROUTES } from "@/lib/constants";

export default function AdminError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4 py-10">
      <ErrorState
        size="page"
        title="Admin error"
        message="This platform screen failed to load. Try again or return to the command center."
        onRetry={reset}
        homeHref={ROUTES.admin.home}
        homeLabel="Back to admin"
      />
    </div>
  );
}
