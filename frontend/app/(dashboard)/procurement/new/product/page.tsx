"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { ProductRfqForm } from "@/components/procurement/ProductRfqForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export default function ProductQuotePage() {
  return (
    <PermissionGate permission="rfqs.create">
      <Suspense fallback={<LoadingEntity entity="product" />}>
        <ProductRfqForm />
      </Suspense>
    </PermissionGate>
  );
}
