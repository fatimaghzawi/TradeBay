"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { ChangeMemberRoleModal } from "@/components/team/ChangeMemberRoleModal";
import { InviteMemberModal } from "@/components/team/InviteMemberModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  identityApi,
  type Invitation,
  type Member,
} from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import {
  formatJoined,
  initials,
  memberDisplayName,
} from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingState } from "@/components/ui/LoadingState";

type TabKey = "all" | "active" | "pending" | "removed";

type TeamRow =
  | { kind: "member"; member: Member }
  | { kind: "invite"; invite: Invitation };

function MembersPageInner() {
  const { hasPermission, business } = useAuth();
  const { success, error: toastError } = useToast();
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [tab, setTab] = useState<TabKey>("all");
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [roleOptions, setRoleOptions] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [roleMember, setRoleMember] = useState<Member | null>(null);
  const [removeMember, setRemoveMember] = useState<Member | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [activeTotal, setActiveTotal] = useState(0);
  const [removedTotal, setRemovedTotal] = useState(0);
  const [allTotal, setAllTotal] = useState(0);
  const pageSize = 20;

  const canInvite = hasPermission("users.invite");
  const canUpdate = hasPermission("users.update");
  const canRemove = hasPermission("users.remove");

  const reload = useCallback(() => {
    setError(null);
    setLoading(true);
    const q = query.trim() || undefined;

    if (tab === "pending") {
      void identityApi
        .listInvitations({ status: "pending", q, page, page_size: pageSize })
        .then((result) => {
          setInvites(result.data);
          setMembers([]);
          setTotal(result.meta.total);
          setPendingTotal(result.meta.total);
        })
        .catch((err) => {
          setInvites([]);
          setMembers([]);
          setTotal(0);
          setError(
            err instanceof ApiError ? err.message : "Couldn't load invitations.",
          );
        })
        .finally(() => setLoading(false));
      return;
    }

    void identityApi
      .listMembers({
        status: tab === "all" ? undefined : tab,
        q,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        setMembers(result.data);
        setTotal(result.meta.total);
      })
      .catch((err) => {
        setMembers([]);
        setTotal(0);
        setError(err instanceof ApiError ? err.message : "Couldn't load members.");
      })
      .finally(() => setLoading(false));

    void identityApi
      .listMembers({ page: 1, page_size: 1 })
      .then((result) => setAllTotal(result.meta.total))
      .catch(() => undefined);
    void identityApi
      .listMembers({ status: "active", page: 1, page_size: 1 })
      .then((result) => setActiveTotal(result.meta.total))
      .catch(() => undefined);
    void identityApi
      .listMembers({ status: "removed", page: 1, page_size: 1 })
      .then((result) => setRemovedTotal(result.meta.total))
      .catch(() => undefined);

    void identityApi
      .listInvitations({ status: "pending", page: 1, page_size: page === 1 ? 20 : 1 })
      .then((result) => {
        setPendingTotal(result.meta.total);
        if (tab === "all" && page === 1) {
          setInvites(result.data);
        } else {
          setInvites([]);
        }
      })
      .catch(() => {
        setPendingTotal(0);
        setInvites([]);
      });
  }, [page, query, tab]);

  useEffect(() => {
    const handle = window.setTimeout(() => reload(), query ? 250 : 0);
    return () => window.clearTimeout(handle);
  }, [reload, query]);

  useEffect(() => {
    void identityApi
      .listRoles({ page: 1, page_size: 100 })
      .then((result) =>
        setRoleOptions(
          result.data.map((role) => ({ id: role.id, name: role.name })),
        ),
      )
      .catch(() => setRoleOptions([]));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [tab, query, roleFilter]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const rows = useMemo(() => {
    const matchesRole = (roleId: string | null | undefined, roleName: string | null | undefined) => {
      if (roleFilter === "all") return true;
      return roleId === roleFilter || roleName === roleFilter;
    };

    if (tab === "pending") {
      return invites
        .filter((invite) => matchesRole(invite.role_id, invite.role_name))
        .map((invite) => ({ kind: "invite" as const, invite }));
    }
    const memberRows: TeamRow[] = members
      .filter((member) => matchesRole(member.role_id, member.role_name))
      .map((member) => ({
        kind: "member",
        member,
      }));
    if (tab === "all" && page === 1 && invites.length > 0) {
      const inviteRows: TeamRow[] = invites
        .filter((invite) => matchesRole(invite.role_id, invite.role_name))
        .map((invite) => ({
          kind: "invite",
          invite,
        }));
      return [...inviteRows, ...memberRows];
    }
    return memberRows;
  }, [invites, members, page, roleFilter, tab]);

  return (
    <IdentityPageShell
      crumb="Company Identity / Team"
      title="Team"
      lede="See who has access, at what responsibility, and who still needs to join."
      action={
        canInvite ? (
          <button
            type="button"
            onClick={() => setInviteOpen(true)}
            className="tb-ov-btn-primary"
          >
            + Invite Member
          </button>
        ) : null
      }
      banner={{
        icon: "☺",
        title: "Build the right team.",
        body: "Invite colleagues, assign roles, and keep access clear as you grow.",
      }}
      stats={[
        { icon: "☺", tone: "teal", value: allTotal, label: "Members" },
        { icon: "✓", tone: "green", value: activeTotal, label: "Active" },
        { icon: "◎", tone: "orange", value: pendingTotal, label: "Pending Invites" },
        { icon: "×", tone: "rose", value: removedTotal, label: "Removed" },
      ]}
      tabs={[
        { key: "all", label: "All" },
        { key: "active", label: `Active (${activeTotal})` },
        { key: "pending", label: `Pending (${pendingTotal})` },
        { key: "removed", label: `Removed (${removedTotal})` },
      ]}
      activeTab={tab}
      onTabChange={(key) => setTab(key as TabKey)}
      search={query}
      searchPlaceholder="Search team…"
      onSearchChange={setQuery}
      searchExtra={
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="tb-roles-search !w-auto min-w-[10rem]"
          aria-label="Filter by role"
        >
          <option value="all">All roles</option>
          {roleOptions.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
      }
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner tone="error" title="Couldn’t load team" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingState variant="section" title="Loading team" message="Loading your company members…" />
      ) : rows.length === 0 ? (
        <div className="tb-empty">
          <h3>{tab === "pending" ? "No open invitations" : "No one in this view yet"}</h3>
          <p>
            {canInvite
              ? "Invite a colleague into your company. Choose their responsibility and the access they need."
              : "When someone is invited or joins, they’ll appear here with their role."}
          </p>
          {canInvite ? (
            <button
              type="button"
              onClick={() => setInviteOpen(true)}
              className="tb-ov-btn-primary mt-4 inline-flex"
            >
              + Invite Member
            </button>
          ) : null}
        </div>
      ) : (
        <ul className="tb-roles-list">
          {rows.map((row) => {
            if (row.kind === "invite") {
              const { invite } = row;
              return (
                <li key={`invite-${invite.id}`} className="tb-roles-row">
                  <span className="tb-roles-glyph" data-tone="custom" aria-hidden>
                    {initials(invite.invited_email)}
                  </span>
                  <div className="tb-roles-row-main min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="tb-roles-row-name">{invite.invited_email}</p>
                      <span className="tb-roles-badge" data-kind="custom">
                        Invitation
                      </span>
                    </div>
                    <p className="tb-roles-row-desc">
                      {invite.role_name ?? "Role pending"} · waiting to join
                    </p>
                  </div>
                  <div className="tb-roles-row-meta">
                    <div>
                      <strong>—</strong>
                      <span>Joined</span>
                    </div>
                  </div>
                  <span className="tb-roles-status">Pending</span>
                  <Link
                    href={ROUTES.invitations}
                    className="text-sm font-bold text-[var(--tb-accent)] hover:underline"
                  >
                    Track →
                  </Link>
                </li>
              );
            }

            const { member } = row;
            const name = memberDisplayName(member);
            const logoSrc = mediaUrl(business?.logo_url || member.avatar_url);
            return (
              <li key={member.id} className="tb-roles-row">
                <span
                  className="tb-roles-glyph"
                  data-tone="sales"
                  data-logo={logoSrc ? "true" : undefined}
                  aria-hidden
                >
                  {logoSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={logoSrc} alt="" />
                  ) : (
                    initials(name)
                  )}
                </span>
                <div className="tb-roles-row-main min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`${ROUTES.members}/${member.id}`}
                      className="tb-roles-row-name"
                    >
                      {name}
                    </Link>
                    <span
                      className="tb-roles-badge"
                      data-kind={member.status === "active" ? "system" : "custom"}
                    >
                      {member.role_name ?? "Unassigned"}
                    </span>
                  </div>
                  <p className="tb-roles-row-desc">{member.email}</p>
                </div>
                <div className="tb-roles-row-meta">
                  <div>
                    <strong>{formatJoined(member.joined_at)}</strong>
                    <span>Joined</span>
                  </div>
                </div>
                <span className="tb-roles-status">{member.status}</span>
                <div className="relative">
                  <button
                    type="button"
                    className="tb-roles-menu-btn"
                    aria-label="Member actions"
                    onClick={() =>
                      setMenuId((id) => (id === member.id ? null : member.id))
                    }
                  >
                    ···
                  </button>
                  {menuId === member.id ? (
                    <div className="tb-roles-menu">
                      <Link
                        href={`${ROUTES.members}/${member.id}`}
                        onClick={() => setMenuId(null)}
                      >
                        Open profile
                      </Link>
                      {canUpdate && member.status === "active" ? (
                        <button
                          type="button"
                          onClick={() => {
                            setRoleMember(member);
                            setMenuId(null);
                          }}
                        >
                          Change role
                        </button>
                      ) : null}
                      {canRemove && member.status === "active" ? (
                        <button
                          type="button"
                          className="is-danger"
                          onClick={() => {
                            setMenuId(null);
                            setRemoveMember(member);
                          }}
                        >
                          Remove
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

      {canInvite ? (
        <button
          type="button"
          className="tb-roles-create-card w-full text-left"
          onClick={() => setInviteOpen(true)}
        >
          <span className="tb-roles-create-plus" aria-hidden>
            +
          </span>
          <span>
            <strong>Invite a New Member</strong>
            <em>Send an invite and choose their starting role.</em>
          </span>
          <span className="tb-roles-create-go" aria-hidden>
            →
          </span>
        </button>
      ) : null}

      {total > 0 ? (
        <div className="mt-4 flex items-center justify-between border-t border-[var(--tb-line)] pt-4">
          <p className="tb-meta">
            {total} result{total === 1 ? "" : "s"}
          </p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onSent={reload}
      />
      <ChangeMemberRoleModal
        open={Boolean(roleMember)}
        member={roleMember}
        onClose={() => setRoleMember(null)}
        onUpdated={reload}
      />
      <ConfirmModal
        open={Boolean(removeMember)}
        title="Remove member?"
        asideTitle="They lose access immediately"
        asideBody="This person will no longer be able to act in this company."
        confirmLabel="Remove"
        pendingLabel="Removing…"
        onClose={() => setRemoveMember(null)}
        onConfirm={async () => {
          if (!removeMember) return;
          const name = memberDisplayName(removeMember);
          try {
            await identityApi.removeMember(removeMember.id);
            success("Member removed", `${name} no longer has access.`);
            reload();
          } catch (err) {
            const message =
              err instanceof ApiError ? err.message : "Member could not be removed.";
            setError(message);
            toastError("Remove failed", message);
            throw err;
          }
        }}
      >
        <p className="text-sm text-[#5c574e]">
          Member:{" "}
          <span className="font-semibold text-[#0d3b2a]">
            {removeMember ? memberDisplayName(removeMember) : ""}
          </span>
        </p>
      </ConfirmModal>
    </IdentityPageShell>
  );
}

export default function MembersPage() {
  return (
    <PermissionGate permission="users.read">
      <MembersPageInner />
    </PermissionGate>
  );
}
