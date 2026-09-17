"use client";

import { Button } from "@/components/ui/Button";
import { Dropdown } from "@/components/ui/Dropdown";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
export function UserMenu() {
  const { user, logout } = useAuth();
  const label = user
    ? `${user.first_name} ${user.last_name}`.trim() || user.email
    : "Account";

  return (
    <Dropdown
      trigger={
        <Button variant="outline" size="sm">
          {label}
        </Button>
      }
      items={[
        {
          key: "settings",
          label: "Settings",
          onSelect: () => {
            window.location.href = ROUTES.settings;
          },
        },
        { key: "logout", label: "Sign out", onSelect: () => void logout() },
      ]}
    />
  );
}
