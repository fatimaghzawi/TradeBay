"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
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
import { LoadingState } from "@/components/ui/LoadingState";

type Layer = "all" | "system" | "custom";

function roleTone(name: string): string {
  const key = name.toLowerCase();
  if (key.includes("admin")) return "admin";
  if (key.includes("sales manager") || key.includes("manager")) return "manager";
  if (key.includes("sales") || key.includes("rep")) return "sales";
  if (key.includes("finance")) return "finance";
  if (key.includes("view")) return "viewer";
  return "custom";
}

function roleGlyph(name: string): string {
  const tone = roleTone(name);
  if (tone === "admin") return "★";
  if (tone === "manager") return "📈";
  if (tone === "sales") return "◎";
  if (tone === "finance") return "$";
  if (tone === "viewer") return "◉";
  return "+";
}

function RolesPageInner() {
  const { hasPermission, business } = useAuth();
  const { success, error: toastError } = useToast();
  const [roles, setRoles] = useState<Role[]>([]);
  const [memberByRole, setMemberByRole] = useState<Record<string, number>>({});
  const [memberTotal, setMemberTotal] = useState(0);
  const [permissionCatalogSize, setPermissionCatalogSize] = useState(0);
  const [layer, setLayer] = useState<Layer>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteRole, setDeleteRole] = useState<Role | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const canManage = hasPermission("roles.manage");
  const fullControl = business?.type === "platform";

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

  useEffect(() => {
    void identityApi
      .listMembers({ page: 1, page_size: 100 })
      .then((result) => {
        const counts: Record<string, number> = {};
        for (const member of result.data) {
          if (member.status === "removed") continue;
          counts[member.role_id] = (counts[member.role_id] ?? 0) + 1;
        }
        setMemberByRole(counts);
        setMemberTotal(result.meta.total);
      })
      .catch(() => {
        setMemberByRole({});
        setMemberTotal(0);
      });
    void identityApi
      .listPermissions()
      .then((rows) => setPermissionCatalogSize(Array.isArray(rows) ? rows.length : 0))
      .catch(() => setPermissionCatalogSize(0));
  }, []);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const filtered = useMemo(() => {
    if (layer === "system") return roles.filter((r) => r.is_system_role);
    if (layer === "custom") return roles.filter((r) => !r.is_system_role);
    return roles;
  }, [roles, layer]);

  const customCount = useMemo(
    () => roles.filter((r) => !r.is_system_role).length,
    [roles],
  );

  const ordered = useMemo(() => {
    const admin = filtered.filter((r) => r.name === "Business Admin");
    const rest = filtered
      .filter((r) => r.name !== "Business Admin")
      .sort((a, b) => a.name.localeCompare(b.name));
    return [...admin, ...rest];
  }, [filtered]);

  return (
    <IdentityPageShell
      crumb="Company Identity / Roles"
      title="Roles"
      lede="Define business roles and manage permissions for your team."
      action={
        canManage ? (
          <Link href={ROUTES.rolesNew} className="tb-btn tb-btn--primary">
            + Create Role
          </Link>
        ) : null
      }
      banner={{
        icon: "👥",
        title: "Organize your team for success.",
        body: "Roles help you control what your team can do and keep your business secure.",
      }}
      stats={[
        {
          icon: "◈",
          tone: "orange",
          value: total || roles.length,
          label: "Total Roles",
        },
        {
          icon: "⛨",
          tone: "green",
          value: permissionCatalogSize,
          label: "Total Permissions",
        },
        {
          icon: "☺",
          tone: "teal",
          value: memberTotal,
          label: "Team Members",
        },
        {
          icon: "+",
          tone: "rose",
          value: customCount,
          label: "Custom Roles",
        },
      ]}
      tabs={[
        { key: "all", label: "All Roles" },
        { key: "system", label: "System Roles" },
        { key: "custom", label: "Custom Roles" },
      ]}
      activeTab={layer}
      onTabChange={(key) => setLayer(key as Layer)}
      search={query}
      searchPlaceholder="Search roles…"
      onSearchChange={setQuery}
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Couldn’t complete action"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingState variant="section" title="Loading roles" message="Loading your company roles…" />
      ) : ordered.length === 0 ? (
        <div className="tb-empty">
          <h3>No roles here yet</h3>
          <p>
            Create a role when someone needs a responsibility that the default
            roles don’t cover.
          </p>
          {canManage ? (
            <Link href={ROUTES.rolesNew} className="tb-btn tb-btn--primary mt-4">
              + Create Role
            </Link>
          ) : null}
        </div>
      ) : (
        <ul className="tb-roles-list">
          {ordered.map((role) => {
            const members = memberByRole[role.id] ?? 0;
            return (
              <li key={role.id} className="tb-roles-row">
                <span
                  className="tb-roles-glyph"
                  data-tone={roleTone(role.name)}
                  aria-hidden
                >
                  {roleGlyph(role.name)}
                </span>
                <div className="tb-roles-row-main min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`${ROUTES.roles}/${role.id}`}
                      className="tb-roles-row-name"
                    >
                      {role.name}
                    </Link>
                    <span
                      className="tb-roles-badge"
                      data-kind={role.is_system_role ? "system" : "custom"}
                    >
                      {role.is_system_role ? "System Role" : "Custom Role"}
                      {role.name === "Business Admin" && !fullControl ? " · Locked" : ""}
                    </span>
                  </div>
                  <p className="tb-roles-row-desc">
                    {role.description || roleBlurb(role.name)}
                  </p>
                </div>
                <div className="tb-roles-row-meta">
                  <div>
                    <strong>{members}</strong>
                    <span>Members</span>
                  </div>
                  <div>
                    <strong>{role.permissions?.length ?? 0}</strong>
                    <span>Permissions</span>
                  </div>
                </div>
                <StatusBadge status="active" />
                <div className="relative">
                  <button
                    type="button"
                    className="tb-roles-menu-btn"
                    aria-label="Role actions"
                    onClick={() =>
                      setMenuId((id) => (id === role.id ? null : role.id))
                    }
                  >
                    ···
                  </button>
                  {menuId === role.id ? (
                    <div className="tb-roles-menu">
                      <Link
                        href={`${ROUTES.roles}/${role.id}`}
                        onClick={() => setMenuId(null)}
                      >
                        View role
                      </Link>
                      {canManage && canEditRolePermissions(role, { fullControl }) ? (
                        <Link
                          href={`${ROUTES.roles}/${role.id}/edit`}
                          onClick={() => setMenuId(null)}
                        >
                          Edit permissions
                        </Link>
                      ) : null}
                      {canManage && !role.is_system_role ? (
                        <button
                          type="button"
                          className="is-danger"
                          disabled={busyId === role.id}
                          onClick={() => {
                            setMenuId(null);
                            setDeleteRole(role);
                          }}
                        >
                          Delete role
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {canManage ? (
        <Link href={ROUTES.rolesNew} className="tb-roles-create-card">
          <span className="tb-roles-create-plus" aria-hidden>
            +
          </span>
          <span>
            <strong>Create a New Role</strong>
            <em>Define a custom role with specific permissions for your team.</em>
          </span>
          <span className="tb-roles-create-go" aria-hidden>
            →
          </span>
        </Link>
      ) : null}

      {total > 0 && layer === "all" ? (
        <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
          <p className="tb-meta">{total} roles</p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <ConfirmModal
        open={Boolean(deleteRole)}
        title="Delete Role?"
        asideTitle="Soft-delete"
        asideBody="The role is deactivated and hidden. Active members must be reassigned first. You can create a new role with the same name afterward."
        confirmLabel="Delete Role"
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
            const message =
              err instanceof ApiError ? err.message : "Role could not be deleted.";
            setError(message);
            toastError("Delete failed", message);
            throw err;
          } finally {
            setBusyId(null);
          }
        }}
      >
        <p className="text-sm text-muted-foreground">
          Soft-delete role{" "}
          <span className="font-semibold text-heading">{deleteRole?.name}</span>?
        </p>
      </ConfirmModal>
    </IdentityPageShell>
  );
}

export default function RolesPage() {
  return (
    <PermissionGate permission="roles.read">
      <RolesPageInner />
    </PermissionGate>
  );
}
