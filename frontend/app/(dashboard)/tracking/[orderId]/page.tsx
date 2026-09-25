"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { TrackingJourney } from "@/components/procurement/OrderTracking";
import { use } from "react";

export default function TrackingOrderPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = use(params);
  return (
    <PermissionGate permission="orders.read">
      <TrackingJourney orderId={orderId} />
    </PermissionGate>
  );
}
