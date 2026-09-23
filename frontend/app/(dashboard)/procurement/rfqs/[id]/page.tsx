"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { RfqWorkspace } from "@/components/procurement/RfqWorkspace";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Suspense, use } from "react";

export default function RfqDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <PermissionGate permission="rfqs.read">
      <Suspense fallback={<LoadingEntity entity="RFQ" />}>
        <RfqWorkspace rfqId={id} />
      </Suspense>
    </PermissionGate>
  );
}
