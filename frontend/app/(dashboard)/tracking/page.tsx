"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { TrackingHub } from "@/components/procurement/OrderTracking";

export default function TrackingPage() {
  return (
    <PermissionGate permission="orders.read">
      <TrackingHub />
    </PermissionGate>
  );
}
