"use client";

import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { InventoryLinkBtn } from "@/components/catalog/InventoryUi";
import { ROUTES } from "@/lib/constants";
import type { ReactNode } from "react";

export type ComingSoonKind = "orders" | "finance";

const COPY: Record<ComingSoonKind, { title: string }> = {
  orders: { title: "Orders are coming soon" },
  finance: { title: "Finance tools are coming soon" },
};

export function ComingSoonView({
  kind,
  title,
  actions,
}: {
  kind: ComingSoonKind;
  
  title?: string;
  actions?: ReactNode;
}) {
  const copy = COPY[kind];

  return (
    <div className="tb-coming">
      <DirectoryMast title={title ?? copy.title} size="page" />
      <div className="tb-coming-panel">
        <div className="tb-coming-actions">
          {actions ?? (
            <>
              <InventoryLinkBtn href={ROUTES.procurement} tone="accent">
                Open procurement →
              </InventoryLinkBtn>
              <InventoryLinkBtn href={ROUTES.quotations} tone="soft">
                Quotations
              </InventoryLinkBtn>
              <InventoryLinkBtn href={ROUTES.dashboard} tone="ghost">
                Dashboard
              </InventoryLinkBtn>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
