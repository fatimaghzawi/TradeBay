"use client";

import { AppStateAction, AppStateFrame } from "@/components/ui/AppState";
import { BackLink } from "@/components/ui/BackLink";
import { ROUTES } from "@/lib/constants";
import type { ReactNode } from "react";

export type ErrorStateProps = {
  title?: string;
  message?: string;
  onRetry?: () => void;
  homeHref?: string;
  homeLabel?: string;
  size?: "page" | "section";
  extra?: ReactNode;
};

export function ErrorState({
  title = "Something went wrong",
  message = "We could not load this section. Try again in a moment.",
  onRetry,
  homeHref = ROUTES.home,
  homeLabel = "Back to home",
  size = "section",
  extra,
}: ErrorStateProps) {
  return (
    <AppStateFrame
      tone="error"
      size={size}
      title={title}
      body={<p>{message}</p>}
      actions={
        <>
          {onRetry ? (
            <AppStateAction onClick={onRetry} tone="primary">
              Try again
            </AppStateAction>
          ) : null}
          <BackLink href={homeHref}>{homeLabel}</BackLink>
        </>
      }
    >
      {extra}
    </AppStateFrame>
  );
}
