"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { AuditLogsView } from "@/components/audit/AuditLogsView";

export default function AuditLogsPage() {
  return (
    <PermissionGate permission="audit_logs.read">
      <AuditLogsView mode="business" />
    </PermissionGate>
  );
}
