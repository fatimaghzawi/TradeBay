"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { canEditRolePermissions } from "@/lib/navigation";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { LoadingState, BusyText } from "@/components/ui/LoadingState";

export default function EditRolePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { hasPermission, permissions, business } = useAuth();
  const { success, error: toastError } = useToast();
  const [role, setRole] = useState<Role | null>(null);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const canManage = hasPermission("roles.manage");
  const fullControl = business?.type === "platform";
  const grantable = useMemo(() => new Set(permissions), [permissions]);

  useEffect(() => {
    if (!params.id) return;
    void identityApi
      .getRole(params.id)
      .then((row) => {
        setRole(row);
        setSelected(row.permissions);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load role."),
      );
    void identityApi
      .listPermissions()
      .then((rows) => setCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setCatalog([]));
  }, [params.id]);

  if (!canManage) {
    return (
      <div className="space-y-3">
        <Link href={ROUTES.roles} className="text-sm font-semibold text-[#0d3b2a] hover:underline">
          ← Back to roles
        </Link>
        <FeedbackBanner tone="warning" title="Access restricted">
          You don&apos;t have access to edit roles.
        </FeedbackBanner>
      </div>
    );
  }

  if (error && !role) {
    return (
      <div className="space-y-3">
        <Link href={ROUTES.roles} className="text-sm font-semibold text-[#0d3b2a] hover:underline">
          ← Back to roles
        </Link>
        <FeedbackBanner tone="error" title="Role unavailable">
          {error}
        </FeedbackBanner>
      </div>
    );
  }

  if (!role) {
    return <LoadingState variant="section" title="Loading role" message="Opening this role…" />;
  }

  if (!canEditRolePermissions(role, { fullControl })) {
    return (
      <div className="space-y-3">
        <Link
          href={`${ROUTES.roles}/${role.id}`}
          className="text-sm font-semibold text-[#0d3b2a] hover:underline"
        >
          ← Back to role
        </Link>
        <FeedbackBanner tone="info" title="Business Admin is locked">
          <strong>{role.name}</strong> always keeps full business access and cannot be
          limited from the UI.
        </FeedbackBanner>
      </div>
    );
  }

  return (
    <div className="tb-role-create">
      <p className="tb-ov-crumb">
        Company Identity <span>/</span>{" "}
        <Link href={ROUTES.roles} className="hover:underline">
          Roles
        </Link>{" "}
        <span>/</span> {role.name}
      </p>

      <DirectoryMast
        title="Edit permissions"
        size="page"
        lede={`${role.name} — choose the access this role should include.`}
      />

      <section className="tb-role-card">
        <div className="tb-role-card-head">
          <span className="tb-role-card-icon" aria-hidden>
            🔒
          </span>
          <div>
            <h2>Permissions</h2>
            <p>
              {selected.length} selected · {grantable.size} grantable for you
            </p>
          </div>
        </div>
        <ModulePermissionPicker
          catalog={catalog}
          selected={selected}
          onChange={setSelected}
          grantable={grantable}
        />
        {error ? (
          <p className="mt-3 rounded-xl bg-[#fef3f2] px-3 py-2 text-sm text-[#b42318]">
            {error}
          </p>
        ) : null}
      </section>

      <footer className="tb-role-create-foot">
        <Link href={`${ROUTES.roles}/${role.id}`} className="tb-ov-btn-ghost">
          Cancel
        </Link>
        <button
          type="button"
          className="tb-ov-btn-primary"
          disabled={selected.length === 0 || pending}
          onClick={() => {
            if (selected.length === 0) {
              setError("Keep at least one permission.");
              return;
            }
            setError(null);
            setPending(true);
            void identityApi
              .updateRole(role.id, selected)
              .then(() => {
                success("Role updated", `${role.name} permissions were saved.`);
                router.replace(`${ROUTES.roles}/${role.id}`);
              })
              .catch((err) => {
                const message =
                  err instanceof ApiError
                    ? err.message
                    : "You can only assign access you already have.";
                setError(message);
                toastError("Couldn't save", message);
              })
              .finally(() => setPending(false));
          }}
        >
          <BusyText busy={pending}>{pending ? "Saving…" : "Save changes"}</BusyText>
        </button>
      </footer>
    </div>
  );
}
