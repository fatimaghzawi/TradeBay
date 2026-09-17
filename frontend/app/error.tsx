"use client";

import { ErrorState } from "@/components/ui/ErrorState";

export default function RootError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-lg px-6 py-16">
      <ErrorState onRetry={reset} />
    </div>
  );
}
