"use client";

import { ComingSoonView } from "@/components/shared/ComingSoonView";
import { InventoryLinkBtn } from "@/components/catalog/InventoryUi";
import { ROUTES } from "@/lib/constants";

export default function AdminFinanceComingSoonPage() {
  return (
    <ComingSoonView
      kind="finance"
      title="Platform finance is coming soon"
      actions={
        <>
          <InventoryLinkBtn href={ROUTES.admin.home} tone="accent">
            Admin home →
          </InventoryLinkBtn>
          <InventoryLinkBtn href={ROUTES.admin.businesses} tone="soft">
            Businesses
          </InventoryLinkBtn>
        </>
      }
    />
  );
}
