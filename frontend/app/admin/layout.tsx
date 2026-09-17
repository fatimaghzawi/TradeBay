import { DashboardGate } from "@/components/auth/DashboardGate";
import { AppShell } from "@/components/layout/AppShell";
import type { ReactNode } from "react";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <DashboardGate>
      <AppShell>{children}</AppShell>
    </DashboardGate>
  );
}
