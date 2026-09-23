"use client";

import { ApiError } from "@/lib/api/client";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { canEditRolePermissions } from "@/lib/navigation";
import { permissionTitle } from "@/lib/identity/permissionCopy";
import { roleBlurb } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingState, BusyText } from "@/components/ui/LoadingState";

export default function RoleDetailsPage() {
  const params = useParams<{ id: string }>();
  const { hasPermission, permissions, business } = useAuth();
  const [role, setRole] = useState<Role | null>(null);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canManage = hasPermission("roles.manage");
  const fullControl = business?.type === "platform";

  const reload = useCallback(() => {
    if (!params.id) return;
    void identityApi
      .getRole(params.id)
      .then(setRole)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load role."),
      );
    void identityApi
      .listPermissions()
      .then((rows) => setCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setCatalog([]));
  }, [params.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  const byResource = useMemo(() => {
    if (!role) return [];
    const selected = new Set(role.permissions);
    const map = new Map<string, Permission[]>();
    for (const permission of catalog) {
      if (!selected.has(permission.code)) continue;
      const list = map.get(permission.resource) ?? [];
      list.push(permission);
      map.set(permission.resource, list);
    }
    // Include any codes not in catalog
    for (const code of role.permissions) {
      if (catalog.some((p) => p.code === code)) continue;
      const [resource = "other", action = code] = code.split(".");
      const list = map.get(resource) ?? [];
      list.push({
        resource,
        action,
        code,
        description: "",
      });
      map.set(resource, list);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [role, catalog]);

  if (error && !role) {
    return (
      <div className="space-y-3">
        <Link href={ROUTES.roles} className="text-sm font-semibold text-[#0d3b2a] hover:underline">
          ← Back to roles
        </Link>
        <p className="rounded-xl bg-[#fef3f2] px-3.5 py-2.5 text-sm text-[#b42318]">{error}</p>
      </div>
    );
  }

  if (!role) {
    return <LoadingState variant="section" title="Loading role" message="Opening this role…" />;
  }

  return (
    <div className="tb-page">
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.roles} className="hover:underline">
          Roles
        </Link>{" "}
        / {role.name}
      </p>

      <DirectoryMast
        title={role.name}
        size="page"
        lede={
          <>
            {role.description || roleBlurb(role.name)}
            <span className="mt-2 block text-sm text-[#4a5f55]">
              {role.permissions.length} permission
              {role.permissions.length === 1 ? "" : "s"} assigned
              {" · "}
              {role.is_system_role
                ? role.name === "Business Admin" && !fullControl
                  ? "System · locked"
                  : "System · editable"
                : "Custom role"}
            </span>
          </>
        }
        actions={
          <div className="flex flex-wrap justify-center gap-2">
            {canManage && canEditRolePermissions(role, { fullControl }) ? (
              <Link
                href={`${ROUTES.roles}/${role.id}/edit`}
                className="inline-flex h-10 items-center rounded-xl bg-[#0d3b2a] px-4 text-sm font-semibold text-white"
              >
                Edit permissions
              </Link>
            ) : null}
            {canManage && !role.is_system_role ? (
              <button
                type="button"
                disabled={deleting}
                className="h-10 rounded-xl border border-[#f3c1bb] px-4 text-sm font-semibold text-[#b42318] hover:bg-[#fef3f2] disabled:opacity-50"
                onClick={() => {
                  setDeleting(true);
                  setError(null);
                  void identityApi
                    .deleteRole(role.id)
                    .then(() => {
                      window.location.href = ROUTES.roles;
                    })
                    .catch((err) =>
                      setError(
                        err instanceof ApiError
                          ? err.message
                          : "Role could not be deleted.",
                      ),
                    )
                    .finally(() => setDeleting(false));
                }}
              >
                <BusyText busy={deleting}>Delete</BusyText>
              </button>
            ) : null}
            {role.name === "Business Admin" && !fullControl ? (
              <p className="self-center text-xs text-[#5a6a62]">
                Business Admin always has full access and cannot be limited.
              </p>
            ) : null}
          </div>
        }
      />

      {error ? (
        <p className="rounded-xl bg-[#fef3f2] px-3.5 py-2.5 text-sm text-[#b42318]">{error}</p>
      ) : null}

      {canManage && canEditRolePermissions(role, { fullControl }) ? (
        <p className="text-xs text-[#5a6a62]">
          You currently hold {permissions.length} permission
          {permissions.length === 1 ? "" : "s"} — edits must stay within that set.
        </p>
      ) : null}

      <section className="mt-8">
        <h2 className="tb-section-label">Permissions</h2>
        {byResource.length === 0 ? (
          <div className="tb-empty px-0">
            <h3>No permissions on this role</h3>
            <p>Assign permissions so this role can access the right features.</p>
          </div>
        ) : (
          byResource.map(([resource, items]) => (
            <div key={resource} className="mt-5 border-t border-[#d4e0da] pt-4">
              <p className="text-[0.7rem] font-bold uppercase tracking-[0.1em] text-[#6b7a72]">
                {resource.replace(/_/g, " ")}
              </p>
              <ul className="tb-data mt-1">
                {items.map((permission) => (
                  <li key={permission.code} className="tb-data-row grid-cols-1">
                    <p className="font-medium text-[#0d3b2a]">{permissionTitle(permission)}</p>
                    {permission.description ? (
                      <p className="tb-meta">{permission.description}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
