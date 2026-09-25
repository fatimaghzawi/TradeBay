"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { OrderDetail } from "@/components/commerce/OrderDetail";
import { use } from "react";

export default function PurchaseOrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <PermissionGate permission="orders.read">
      <OrderDetail orderId={id} />
    </PermissionGate>
  );
}
