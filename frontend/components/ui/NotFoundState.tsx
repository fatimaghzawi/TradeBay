import { AppStateAction, AppStateFrame } from "@/components/ui/AppState";
import { ROUTES } from "@/lib/constants";
import type { ReactNode } from "react";

export type NotFoundStateProps = {
  title?: string;
  message?: string;
  homeHref?: string;
  homeLabel?: string;
  size?: "page" | "section";
  actions?: ReactNode;
};

/**
 * Consistent 404 / missing-resource moment.
 */
export function NotFoundState({
  title = "Page not found",
  message = "This route isn’t on the bay — it may have moved, or the link is incomplete.",
  homeHref = ROUTES.home,
  homeLabel = "Back to home",
  size = "page",
  actions,
}: NotFoundStateProps) {
  return (
    <AppStateFrame
      tone="not-found"
      size={size}
      title={title}
      body={<p>{message}</p>}
      actions={
        actions ?? (
          <>
            <AppStateAction href={homeHref} tone="primary">
              {homeLabel}
            </AppStateAction>
            <AppStateAction href={ROUTES.marketplace} tone="soft">
              Browse products
            </AppStateAction>
          </>
        )
      }
    />
  );
}
