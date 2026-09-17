import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-muted">
      <TopBar />
      <div className="flex">
        <Sidebar />
        <main className="min-h-[calc(100vh-var(--tb-topbar-height))] flex-1 p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
