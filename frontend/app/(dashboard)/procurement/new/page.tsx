"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { CreateRfqWizard } from "@/components/procurement/CreateRfqWizard";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Suspense } from "react";

/** Create RFQ from listed catalog / marketplace products. */
export default function NewRfqPage() {
  return (
    <PermissionGate permission="rfqs.create">
      <Suspense fallback={<LoadingEntity entity="RFQ" />}>
        <CreateRfqWizard mode="catalog" />
      </Suspense>
    </PermissionGate>
  );
}
