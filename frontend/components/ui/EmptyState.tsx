import { AppStateAction, AppStateFrame } from "@/components/ui/AppState";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type EmptyStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  size?: "page" | "section";
};

export function EmptyState({
  title,
  description,
  action,
  className,
  size = "section",
}: EmptyStateProps) {
  return (
    <AppStateFrame
      tone="empty"
      size={size}
      title={title}
      body={description ? <p>{description}</p> : undefined}
      actions={action}
      className={cn(className)}
    />
  );
}

export { AppStateAction };
