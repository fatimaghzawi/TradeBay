"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { OrdersHub } from "@/components/commerce/OrdersHub";

export default function OrdersPage() {
  return (
    <PermissionGate permission="orders.read">
      <OrdersHub />
    </PermissionGate>
  );
}
