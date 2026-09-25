"use client";

import { AdminCreateRoleModal } from "@/components/admin/AdminCreateRoleModal";
import { AdminEditRoleModal } from "@/components/admin/AdminEditRoleModal";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Role } from "@/lib/api/identityApi";
import { roleBlurb } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import { useCallback, useEffect, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type AdminBusinessRolesPanelProps = {
  businessId: string;
  businessName: string;
};

export function AdminBusinessRolesPanel({
  businessId,
  businessName,
}: AdminBusinessRolesPanelProps) {
  const { hasPermission } = useAuth();
  const { success, error: toastError } = useToast();
  const canManage = hasPermission("roles.manage");
  const canRead = hasPermission("roles.read");

  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editRole, setEditRole] = useState<Role | null>(null);
  const [deleteRole, setDeleteRole] = useState<Role | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!canRead) {
      setRoles([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    void identityApi
      .listPlatformBusinessRoles(businessId, { page_size: 100 })
      .then((result) => {
        setRoles(result.data);
        setError(null);
      })
      .catch((err) => {
        setRoles([]);
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load roles for this company.",
        );
      })
      .finally(() => setLoading(false));
  }, [businessId, canRead]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (!canRead) {
    return (
      <FeedbackBanner tone="warning" title="Access restricted">
        You don&apos;t have access to view company roles.
      </FeedbackBanner>
    );
  }

  return (
    <section className="mt-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="tb-section-label">Roles & permissions</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Full control for {businessName}. Business Admin can be edited by platform staff.
          </p>
        </div>
        {canManage ? (
          <button
            type="button"
            className="tb-btn tb-btn--primary tb-btn--sm"
            onClick={() => setCreateOpen(true)}
          >
            + Create role
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="mt-4">
          <FeedbackBanner tone="error" title="Roles unavailable" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingEntity entity="roles" className="py-10 justify-center" />
      ) : roles.length === 0 ? (
        <div className="tb-empty mt-6">
          <h3>No roles</h3>
          <p>This company has no roles yet.</p>
        </div>
      ) : (
        <ul className="mt-5 divide-y divide-border border border-input">
          {roles.map((role) => (
            <li
              key={role.id}
              className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-foreground">{role.name}</p>
                  <span className="rounded-full bg-secondary-soft px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-heading">
                    {role.is_system_role ? "System" : "Custom"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {role.permissions.length} permissions
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {role.description || roleBlurb(role.name)}
                </p>
              </div>
              {canManage ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="border border-input px-3 py-1.5 text-sm font-semibold text-heading"
                    onClick={() => setEditRole(role)}
                  >
                    Edit permissions
                  </button>
                  {!role.is_system_role ? (
                    <button
                      type="button"
                      className="border border-destructive/30 px-3 py-1.5 text-sm font-semibold text-destructive"
                      disabled={busyId === role.id}
                      onClick={() => setDeleteRole(role)}
                    >
                      Delete
                    </button>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <AdminCreateRoleModal
        open={createOpen}
        businessId={businessId}
        onClose={() => setCreateOpen(false)}
        onCreated={reload}
      />
      <AdminEditRoleModal
        open={Boolean(editRole)}
        businessId={businessId}
        role={editRole}
        onClose={() => setEditRole(null)}
        onSaved={reload}
      />
      <ConfirmModal
        open={Boolean(deleteRole)}
        title="Delete role?"
        asideTitle="Soft-delete"
        asideBody="The role is deactivated and hidden. Members must be reassigned first."
        confirmLabel="Delete role"
        pendingLabel="Deleting…"
        onClose={() => setDeleteRole(null)}
        onConfirm={async () => {
          if (!deleteRole) return;
          setBusyId(deleteRole.id);
          try {
            await identityApi.deletePlatformBusinessRole(businessId, deleteRole.id);
            success("Role deleted", `${deleteRole.name} was soft-deleted.`);
            reload();
          } catch (err) {
            toastError(
              "Delete failed",
              err instanceof ApiError ? err.message : "Couldn't delete role.",
            );
            throw err;
          } finally {
            setBusyId(null);
          }
        }}
      >
        {deleteRole
          ? `Soft-delete “${deleteRole.name}” from ${businessName}?`
          : null}
      </ConfirmModal>
    </section>
  );
}
