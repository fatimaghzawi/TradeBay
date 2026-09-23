"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { ShipmentWorkspace } from "@/components/procurement/ShipmentWorkspace";
import { use } from "react";

export default function ProcurementShipmentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <PermissionGate permission="shipments.read">
      <ShipmentWorkspace shipmentId={id} />
    </PermissionGate>
  );
}
