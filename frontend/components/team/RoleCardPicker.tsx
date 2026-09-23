"use client";

import { roleBlurb } from "@/lib/team";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/api/identityApi";
import { LoadingEntity } from "@/components/ui/LoadingState";

type RoleCardPickerProps = {
  roles: Role[];
  value: string;
  onChange: (roleId: string) => void;
  loading?: boolean;
  emptyLabel?: string;
};

export function RoleCardPicker({
  roles,
  value,
  onChange,
  loading = false,
  emptyLabel = "No roles available yet.",
}: RoleCardPickerProps) {
  if (loading) {
    return <LoadingEntity entity="roles" compact />;
  }

  if (roles.length === 0) {
    return <p className="tb-form-hint">{emptyLabel}</p>;
  }

  return (
    <div className="tb-form-role-grid" role="radiogroup" aria-label="Choose a role">
      {roles.map((role) => {
        const active = value === role.id;
        return (
          <button
            key={role.id}
            type="button"
            role="radio"
            aria-checked={active}
            className={cn("tb-form-role-card", active && "is-active")}
            onClick={() => onChange(role.id)}
          >
            <span className="tb-form-role-check" aria-hidden>
              {active ? "✓" : ""}
            </span>
            <span className="tb-form-role-name">{role.name}</span>
            <span className="tb-form-role-blurb">{roleBlurb(role.name)}</span>
            <span className="tb-form-role-meta">
              {(role.permissions ?? []).length} permissions
            </span>
          </button>
        );
      })}
    </div>
  );
}
