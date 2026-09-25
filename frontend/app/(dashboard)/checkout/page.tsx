"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { CheckoutView } from "@/components/commerce/CheckoutView";

export default function CheckoutPage() {
  return (
    <PermissionGate
      permission="quotations.accept"
      fallbackTitle="Checkout"
      fallbackDescription="Placing orders is available to buyer team members who can approve purchases."
    >
      <CheckoutView />
    </PermissionGate>
  );
}
