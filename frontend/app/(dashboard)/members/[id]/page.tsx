"use client";

import { SuspendAccountModal } from "@/components/admin/SuspendAccountModal";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { ChangeMemberRoleModal } from "@/components/team/ChangeMemberRoleModal";
import { StatusBadge } from "@/components/team/StatusBadge";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/useConfirm";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Member, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { canEditRolePermissions } from "@/lib/navigation";
import {
  memberDisplayName,
  roleBlurb,
} from "@/lib/team";
import { accessModulesFromCodes } from "@/lib/identity/permissionCopy";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { LoadingState } from "@/components/ui/LoadingState";
import { BackLink } from "@/components/ui/BackLink";

export default function MemberDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { hasPermission, business } = useAuth();
  const { success, error: toastError } = useToast();
  const { confirm, dialog } = useConfirm();
  const [member, setMember] = useState<Member | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [tab, setTab] = useState<"overview" | "activity">("overview");
  const [error, setError] = useState<string | null>(null);
  const [roleOpen, setRoleOpen] = useState(false);
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [removing, setRemoving] = useState(false);

  const canUpdate = hasPermission("users.update");
  const canRemove = hasPermission("users.remove");
  const canManageRoles = hasPermission("roles.manage");

  const reload = useCallback(() => {
    if (!params.id) return;
    void identityApi
      .getMember(params.id)
      .then(async (row) => {
        setMember(row);
        setError(null);
        try {
          if (row.role_id) {
            const roleRow = await identityApi.getRole(row.role_id);
            setRole(roleRow);
          } else {
            setRole(null);
          }
        } catch {
          setRole(null);
        }
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load member."),
      );
  }, [params.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (error && !member) {
    return (
      <div className="space-y-3">
        <BackLink href={ROUTES.members}>Back to team</BackLink>
        <FeedbackBanner tone="error" title="Member not found">
          {error}
        </FeedbackBanner>
      </div>
    );
  }

  if (!member) {
    return <LoadingState variant="section" title="Loading member" message="Opening this teammate…" />;
  }

  const name = memberDisplayName(member);
  const roleEditable = role ? canEditRolePermissions(role) : false;
  const businessName = business?.name;

  return (
    <div className="tb-page">
      {dialog}
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.members} className="hover:underline">
          Team
        </Link>{" "}
        / {name}
      </p>

      <DirectoryMast
        title={name}
        size="page"
        lede={
          <>
            {member.role_name ?? "No role"} · {member.email}
            {businessName ? ` · ${businessName}` : ""}
          </>
        }
        meta={
          <div className="flex flex-wrap items-center justify-center gap-3">
            <StatusBadge status={member.status} />
            {member.user_status ? <StatusBadge status={member.user_status} /> : null}
          </div>
        }
        actions={
          <div className="flex flex-wrap justify-center gap-2">
            {canUpdate && member.status === "active" ? (
              <button
                type="button"
                className="tb-btn tb-btn--primary"
                onClick={() => setRoleOpen(true)}
              >
                Change role
              </button>
            ) : null}
            {canManageRoles && role && roleEditable ? (
              <Link
                href={`${ROUTES.roles}/${role.id}/edit`}
                className="tb-btn tb-btn--outline"
              >
                Edit role permissions
              </Link>
            ) : null}
            {canUpdate && member.status === "active" ? (
              <button
                type="button"
                className="tb-btn tb-btn--outline"
                onClick={() => setSuspendOpen(true)}
              >
                Suspend
              </button>
            ) : null}
            {canUpdate && member.status === "suspended" ? (
              <button
                type="button"
                className="tb-btn tb-btn--outline"
                onClick={() => {
                  setError(null);
                  void identityApi
                    .reactivateMember(member.id)
                    .then(() => {
                      success(
                        "Membership reactivated",
                        `${name} can access this business again.`,
                      );
                      reload();
                    })
                    .catch((err) => {
                      const message =
                        err instanceof ApiError ? err.message : "Could not reactivate.";
                      setError(message);
                      toastError("Reactivate failed", message);
                    });
                }}
              >
                Reactivate
              </button>
            ) : null}
            {canRemove && member.status === "active" ? (
              <button
                type="button"
                disabled={removing}
                className="tb-btn tb-btn--danger"
                onClick={async () => {
                  const ok = await confirm({
                    title: `Remove ${name} from this business?`,
                    body: "They will lose access immediately.",
                    confirmLabel: "Remove member",
                    destructive: true,
                  });
                  if (!ok) return;
                  setError(null);
                  setRemoving(true);
                  void identityApi
                    .removeMember(member.id)
                    .then(() => {
                      success("Member removed", `${name} no longer has access.`);
                      router.replace(ROUTES.members);
                    })
                    .catch((err) => {
                      const message =
                        err instanceof ApiError ? err.message : "Could not remove member.";
                      setError(message);
                      toastError("Remove failed", message);
                    })
                    .finally(() => setRemoving(false));
                }}
              >
                {removing ? "Removing…" : "Remove"}
              </button>
            ) : null}
          </div>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t complete action" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      {!canUpdate && !canRemove && !canManageRoles ? (
        <FeedbackBanner tone="info" title="View-only access">
          Your role can review this member but cannot change their role or permissions.
        </FeedbackBanner>
      ) : null}

      <p className="mt-6 border-l-2 border-accent pl-4 text-sm leading-relaxed text-muted-foreground">
        Permissions come from the member&apos;s <strong className="text-heading">role</strong>,
        not from individual toggles. Use <strong className="text-heading">Change role</strong> to
        assign a different role, or <strong className="text-heading">Edit role permissions</strong>{" "}
        to change what everyone with that role can do.
      </p>

      <div className="flex gap-1 border-b border-border">
        {(
          [
            ["overview", "Overview"],
            ["activity", "Activity"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn(
              "border-b-2 px-3 py-2.5 text-sm font-semibold",
              tab === key
                ? "border-primary text-heading"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <section className="mt-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="tb-section-label">Assigned role</p>
              <p className="mt-2 font-[family-name:var(--font-outfit)] text-xl font-bold text-heading">
                {member.role_name ?? "—"}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">{roleBlurb(member.role_name)}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {canUpdate && member.status === "active" ? (
                <button
                  type="button"
                  onClick={() => setRoleOpen(true)}
                  className="tb-btn tb-btn--primary tb-btn--sm"
                >
                  Change role
                </button>
              ) : null}
              {canManageRoles && role && roleEditable ? (
                <Link
                  href={`${ROUTES.roles}/${role.id}/edit`}
                  className="border border-input px-3 py-2 text-sm font-semibold text-heading"
                >
                  Edit permissions
                </Link>
              ) : null}
              {role?.name === "Business Admin" ? (
                <p className="self-center text-xs text-muted-foreground">
                  Business Admin access is full and locked.
                </p>
              ) : null}
            </div>
          </div>

          {role?.permissions?.length ? (
            <div className="mt-6">
              <p className="tb-section-label">Access</p>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {accessModulesFromCodes(role.permissions).map((mod) => (
                  <li
                    key={mod.label}
                    className="flex items-center justify-between rounded-xl border border-[var(--tb-line-soft)] px-3.5 py-2.5 text-sm"
                  >
                    <span className="font-semibold text-foreground">{mod.label}</span>
                    <span
                      className={
                        mod.allowed
                          ? "font-bold text-success"
                          : "font-semibold text-muted-foreground"
                      }
                    >
                      {mod.allowed ? "✓ Access" : "No access"}
                    </span>
                  </li>
                ))}
              </ul>
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-semibold text-[var(--tb-secondary)]">
                  View permission codes ({role.permissions.length})
                </summary>
                <ul className="mt-2 divide-y divide-border border-y border-border">
                  {role.permissions.map((code) => (
                    <li key={code} className="py-2 font-mono text-xs text-ink-soft">
                      {code}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              No permissions loaded for this role.
            </p>
          )}
        </section>
      ) : (
        <div className="tb-empty mt-6 px-0">
          <h3>No activity yet</h3>
          <p>Member activity for this person will appear here when audit logs are available.</p>
        </div>
      )}

      <ChangeMemberRoleModal
        open={roleOpen}
        member={member}
        onClose={() => setRoleOpen(false)}
        onUpdated={reload}
      />
      <SuspendAccountModal
        open={suspendOpen}
        title="Suspend membership"
        subjectLabel={name}
        confirmLabel="Suspend membership"
        onClose={() => setSuspendOpen(false)}
        onConfirm={async (reason) => {
          try {
            await identityApi.suspendMember(member.id, reason);
            success("Membership suspended", `${name} lost access to this business.`);
            reload();
          } catch (err) {
            const message =
              err instanceof ApiError ? err.message : "Could not suspend membership.";
            setError(message);
            toastError("Suspend failed", message);
            throw err;
          }
        }}
      />
    </div>
  );
}
