import { DashboardGate } from "@/components/auth/DashboardGate";
import { PlatformAdminGate } from "@/components/auth/PlatformAdminGate";
import { AppShell } from "@/components/layout/AppShell";
import type { ReactNode } from "react";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <DashboardGate>
      <PlatformAdminGate>
        <AppShell>{children}</AppShell>
      </PlatformAdminGate>
    </DashboardGate>
  );
}
