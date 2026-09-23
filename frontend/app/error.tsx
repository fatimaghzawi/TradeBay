"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { ROUTES } from "@/lib/constants";

export default function RootError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="tb-app flex min-h-[70vh] items-center justify-center px-4">
      <ErrorState
        size="page"
        title="Something went wrong"
        message="TradeBay hit an unexpected error on this screen. You can try again, or head back home."
        onRetry={reset}
        homeHref={ROUTES.home}
        homeLabel="Back to home"
      />
    </div>
  );
}
