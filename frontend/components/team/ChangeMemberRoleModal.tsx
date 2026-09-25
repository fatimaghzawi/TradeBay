"use client";

import { RoleCardPicker } from "@/components/team/RoleCardPicker";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Member, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { canEditRolePermissions } from "@/lib/navigation";
import { memberDisplayName } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type ChangeMemberRoleModalProps = {
  open: boolean;
  member: Member | null;
  onClose: () => void;
  onUpdated: () => void;
  
  businessId?: string;
};

export function ChangeMemberRoleModal({
  open,
  member,
  onClose,
  onUpdated,
  businessId,
}: ChangeMemberRoleModalProps) {
  const { success, error: toastError } = useToast();
  const { hasPermission } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [roleId, setRoleId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);

  const canManageRoles = hasPermission("roles.manage");
  const platformMode = Boolean(businessId);
  const fullControl = platformMode;

  useEffect(() => {
    if (!open || !member) return;
    setRoleId(member.role_id);
    setError(null);
    setLoading(true);
    const load = businessId
      ? identityApi.listPlatformBusinessRoles(businessId, { page_size: 100 })
      : identityApi.listRoles({ page_size: 100 });
    void load
      .then((result) => setRoles(result.data))
      .catch((err) => {
        setRoles([]);
        setError(
          err instanceof ApiError ? err.message : "Couldn't load roles for this business.",
        );
      })
      .finally(() => setLoading(false));
  }, [open, member, businessId]);

  const selected = roles.find((r) => r.id === roleId);
  const name = member ? memberDisplayName(member) : "";
  const canCustomizeSelected = Boolean(
    canManageRoles && selected && canEditRolePermissions(selected, { fullControl }),
  );
  const unchanged = Boolean(member && roleId === member.role_id);

  return (
    <Modal
      open={open && Boolean(member)}
      onClose={onClose}
      mark="user"
      kicker={platformMode ? "Platform control" : "Team access"}
      title="Change role"
      asideTitle="Update what they can do"
      asideBody={
        platformMode
          ? "Platform staff can assign any company role, including Business Admin."
          : "Pick a new responsibility card. Their day-to-day access updates immediately."
      }
      footer={
        <>
          <button type="button" className="tb-btn tb-btn--outline" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-btn tb-btn--primary"
            disabled={!member || !roleId || pending || unchanged}
            aria-busy={pending || undefined}
            onClick={() => {
              if (!member || pending) return;
              setError(null);
              setPending(true);
              const save = businessId
                ? identityApi.updatePlatformBusinessMemberRole(
                    businessId,
                    member.id,
                    roleId,
                  )
                : identityApi.updateMemberRole(member.id, roleId);
              void save
                .then(() => {
                  success("Role updated", `${name} is now ${selected?.name ?? "updated"}.`);
                  onUpdated();
                  onClose();
                })
                .catch((err) => {
                  const message =
                    err instanceof ApiError
                      ? err.message
                      : "Role change rejected. The last admin cannot be demoted, and you can only assign permissions you already have.";
                  setError(message);
                  toastError("Role not changed", message);
                })
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Saving…" : unchanged ? "Same role" : "Save new role"}</BusyText>
          </button>
        </>
      }
    >
      {member ? (
        <div className="tb-form-stack">
          <div className="tb-form-preview">
            <p className="tb-form-preview-kicker">Teammate</p>
            <ul>
              <li>
                <span>Name</span>
                <strong>{name}</strong>
              </li>
              <li>
                <span>Email</span>
                <strong>{member.email || "—"}</strong>
              </li>
              <li>
                <span>Current</span>
                <strong>{member.role_name ?? "—"}</strong>
              </li>
            </ul>
          </div>

          <div className="tb-form-block" data-tone="role">
            <div className="tb-form-block-head">
              <span className="tb-form-index">→</span>
              <div>
                <p className="tb-form-label">New role</p>
                <p className="tb-form-hint">Choose one card below</p>
              </div>
            </div>
            <RoleCardPicker
              roles={roles}
              value={roleId}
              onChange={(id) => {
                setRoleId(id);
                setError(null);
              }}
              loading={loading}
            />
          </div>

          {canCustomizeSelected && selected && !platformMode ? (
            <p className="tb-form-hint">
              Need finer control?{" "}
              <Link
                href={`${ROUTES.roles}/${selected.id}/edit`}
                className="font-semibold text-[var(--tb-secondary)] underline underline-offset-2"
                onClick={onClose}
              >
                Edit {selected.name} permissions
              </Link>
            </p>
          ) : null}
          {error ? <p className="tb-form-alert">{error}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}
