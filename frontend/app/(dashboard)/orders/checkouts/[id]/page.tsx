"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { CheckoutDetail } from "@/components/commerce/CheckoutDetail";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Suspense, use } from "react";

export default function CheckoutDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <PermissionGate permission="orders.read">
      <Suspense fallback={<LoadingEntity entity="checkout" className="py-8" />}>
        <CheckoutDetail checkoutId={id} />
      </Suspense>
    </PermissionGate>
  );
}
