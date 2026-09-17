"use client";

import { BusinessSwitcher } from "@/components/layout/BusinessSwitcher";
import { Logo } from "@/components/layout/Logo";
import { UserMenu } from "@/components/layout/UserMenu";
import { Button } from "@/components/ui/Button";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-[var(--tb-topbar-height)] items-center gap-4 border-b border-border bg-surface/95 px-4 backdrop-blur">
      <Logo className="shrink-0" />
      <div className="hidden min-w-0 flex-1 md:block">
        <BusinessSwitcher />
      </div>
      <Button variant="ghost" size="sm" aria-label="Notifications placeholder">
        Notifications
      </Button>
      <UserMenu />
    </header>
  );
}
