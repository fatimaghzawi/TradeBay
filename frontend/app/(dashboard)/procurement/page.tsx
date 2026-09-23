"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { ProcurementDashboardView } from "@/components/procurement/ProcurementDashboardView";

export default function ProcurementPage() {
  return (
    <PermissionGate permission="rfqs.read">
      <ProcurementDashboardView />
    </PermissionGate>
  );
}
