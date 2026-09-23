"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { GuestExploreBanner } from "@/components/auth/GuestExploreBanner";
import { SupplierExplorer } from "@/components/suppliers/SupplierExplorer";

export default function SuppliersPage() {
  return (
    <PermissionGate permission="products.read" allowGuest>
      <GuestExploreBanner action="sync shortlists and message suppliers" />
      <SupplierExplorer />
    </PermissionGate>
  );
}
