"use client";

import { AdminPage } from "@/components/admin/AdminUi";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { AuditLogsView } from "@/components/audit/AuditLogsView";

export default function AdminAuditPage() {
  return (
    <PermissionGate
      permission="audit_logs.read"
      fallbackTitle="Platform audit is restricted"
      fallbackDescription="Platform staff access is required to view audit events."
    >
      <AdminPage>
        <AuditLogsView mode="platform" />
      </AdminPage>
    </PermissionGate>
  );
}
