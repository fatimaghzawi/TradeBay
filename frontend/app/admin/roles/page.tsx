"use client";

import { AdminIdentityNav } from "@/components/admin/AdminIdentityNav";
import { AdminAct, AdminCards, AdminPage } from "@/components/admin/AdminUi";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { canEditRolePermissions } from "@/lib/navigation";
import { roleBlurb } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type Layer = "all" | "system" | "custom";

/**
 * Platform staff roles — full control for Platform Admin (ALL_CODES).
 * Trading-company roles are managed from each company profile.
 */
function AdminRolesPageInner() {
  const { hasPermission } = useAuth();
  const { success, error: toastError } = useToast();
  const [roles, setRoles] = useState<Role[]>([]);
  const [layer, setLayer] = useState<Layer>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteRole, setDeleteRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;
  const canManage = hasPermission("roles.manage");
  const fullControl = true;

  const reload = useCallback(() => {
    setLoading(true);
    void identityApi
      .listRoles({
        q: query.trim() || undefined,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        setRoles(result.data);
        setTotal(result.meta.total);
        setError(null);
      })
      .catch((err) => {
        setRoles([]);
        setTotal(0);
        setError(err instanceof ApiError ? err.message : "Couldn't load roles.");
      })
      .finally(() => setLoading(false));
  }, [page, query]);

  useEffect(() => {
    const handle = window.setTimeout(() => reload(), query ? 250 : 0);
    return () => window.clearTimeout(handle);
  }, [reload, query]);

  useEffect(() => {
    setPage(1);
  }, [query, layer]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const filtered = useMemo(() => {
    if (layer === "system") return roles.filter((r) => r.is_system_role);
    if (layer === "custom") return roles.filter((r) => !r.is_system_role);
    return roles;
  }, [roles, layer]);

  const ordered = useMemo(
    () => [...filtered].sort((a, b) => a.name.localeCompare(b.name)),
    [filtered],
  );

  return (
    <AdminPage>
      <AdminIdentityNav />
      <DirectoryMast
        title="Roles"
        mark="Platform"
        size="page"
        lede="Full control over TradeBay staff roles. Open a buyer or supplier to manage that company’s roles."
        actions={
          canManage ? (
            <AdminAct href={ROUTES.rolesNew} tone="go" arrow>
              Create role
            </AdminAct>
          ) : undefined
        }
      />

      <div className="tb-toolbar flex-wrap gap-y-2">
        {(
          [
            ["all", "All"],
            ["system", "System"],
            ["custom", "Custom"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className="tb-filter"
            data-active={layer === key}
            onClick={() => setLayer(key)}
          >
            {label}
          </button>
        ))}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search roles…"
          className="h-9 w-full max-w-xs rounded-lg border border-[#d4e0da] px-3 text-sm outline-none focus:border-[#e86f2a]"
        />
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Roles unavailable" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <LoadingEntity entity="roles" className="py-12 justify-center" />
      ) : ordered.length === 0 ? (
        <div className="tb-empty">
          <h3>No roles</h3>
          <p>Create a custom staff role when someone needs a narrower desk.</p>
        </div>
      ) : (
        <AdminCards>
          {ordered.map((role) => (
            <li key={role.id}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`${ROUTES.roles}/${role.id}`}
                    className="font-semibold text-[#0c1612] hover:underline"
                  >
                    {role.name}
                  </Link>
                  <span className="tb-status" data-tone={role.is_system_role ? "ok" : "wait"}>
                    {role.is_system_role ? "System" : "Custom"}
                  </span>
                  <span className="tb-meta">
                    {role.permissions.length} permissions
                  </span>
                </div>
                <p className="tb-meta">
                  {role.description || roleBlurb(role.name)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <AdminAct href={`${ROUTES.roles}/${role.id}`} tone="ghost" arrow>
                  View
                </AdminAct>
                {canManage && canEditRolePermissions(role, { fullControl }) ? (
                  <AdminAct href={`${ROUTES.roles}/${role.id}/edit`} tone="go">
                    Edit
                  </AdminAct>
                ) : null}
                {canManage && !role.is_system_role ? (
                  <AdminAct
                    tone="danger"
                    disabled={busyId === role.id}
                    onClick={() => setDeleteRole(role)}
                  >
                    Delete
                  </AdminAct>
                ) : null}
              </div>
            </li>
          ))}
        </AdminCards>
      )}

      {total > 0 && layer === "all" ? (
        <div className="flex items-center justify-between border-t border-[#d4e0da] pt-4">
          <p className="text-sm text-[#6b7a72]">{total} roles</p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <ConfirmModal
        open={Boolean(deleteRole)}
        title="Delete role?"
        asideTitle="Soft-delete"
        asideBody="The role is deactivated and hidden. Staff assigned to this role must be moved first."
        confirmLabel="Delete role"
        pendingLabel="Deleting…"
        onClose={() => setDeleteRole(null)}
        onConfirm={async () => {
          if (!deleteRole) return;
          setBusyId(deleteRole.id);
          try {
            await identityApi.deleteRole(deleteRole.id);
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
        {deleteRole ? `Soft-delete “${deleteRole.name}” from the platform tenant?` : null}
      </ConfirmModal>
    </AdminPage>
  );
}

export default function AdminRolesPage() {
  return (
    <PermissionGate
      permission="roles.read"
      fallbackTitle="Roles locked"
      fallbackDescription="Platform staff access is required to manage staff roles."
    >
      <AdminRolesPageInner />
    </PermissionGate>
  );
}
