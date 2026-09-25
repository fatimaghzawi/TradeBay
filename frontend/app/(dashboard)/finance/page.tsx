"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { FinanceHub } from "@/components/commerce/FinanceHub";

export default function FinancePage() {
  return (
    <PermissionGate permission={["invoices.read", "payables.read"]}>
      <FinanceHub />
    </PermissionGate>
  );
}
