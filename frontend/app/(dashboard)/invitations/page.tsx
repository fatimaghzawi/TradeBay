"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { InviteMemberModal } from "@/components/team/InviteMemberModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Invitation } from "@/lib/api/identityApi";
import { formatJoined, initials } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import { useCallback, useEffect, useState } from "react";
import { LoadingState, BusyText } from "@/components/ui/LoadingState";

type Stage = "awaiting" | "closed";

function InvitationsPageInner() {
  const { hasPermission } = useAuth();
  const { success, error: toastError } = useToast();
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [stage, setStage] = useState<Stage>("awaiting");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [revokeInvite, setRevokeInvite] = useState<Invitation | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [acceptedCount, setAcceptedCount] = useState(0);
  const [closedCount, setClosedCount] = useState(0);
  const pageSize = 20;

  const canInvite = hasPermission("users.invite");

  const reload = useCallback(() => {
    setLoading(true);
    void identityApi
      .listInvitations({
        status:
          stage === "awaiting"
            ? "pending"
            : statusFilter !== "all"
              ? statusFilter
              : undefined,
        q: query.trim() || undefined,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        const rows =
          stage === "closed" && statusFilter === "all"
            ? result.data.filter((i) => i.status !== "pending")
            : result.data;
        setInvites(rows);
        setTotal(result.meta.total);
        setError(null);
      })
      .catch((err) => {
        setInvites([]);
        setTotal(0);
        setError(
          err instanceof ApiError ? err.message : "Couldn't load invitations.",
        );
      })
      .finally(() => setLoading(false));
  }, [page, query, stage, statusFilter]);

  useEffect(() => {
    const handle = window.setTimeout(() => reload(), query ? 250 : 0);
    return () => window.clearTimeout(handle);
  }, [reload, query]);

  useEffect(() => {
    setPage(1);
  }, [stage, query, statusFilter]);

  useEffect(() => {
    void identityApi
      .listInvitations({ status: "pending", page: 1, page_size: 1 })
      .then((result) => setPendingCount(result.meta.total))
      .catch(() => setPendingCount(0));
    void identityApi
      .listInvitations({ status: "accepted", page: 1, page_size: 1 })
      .then((result) => setAcceptedCount(result.meta.total))
      .catch(() => setAcceptedCount(0));
    void identityApi
      .listInvitations({ page: 1, page_size: 1 })
      .then((result) => setClosedCount(Math.max(0, result.meta.total)))
      .catch(() => setClosedCount(0));
  }, [stage, invites]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  return (
    <IdentityPageShell
      crumb="Company Identity / Invitations"
      title="Invitations"
      lede="Invite teammates, choose their responsibility, and track who still needs to join."
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
        icon: "✉",
        title: "Grow your team carefully.",
        body: "Every invite carries a role. Track who accepted, who is waiting, and who needs a fresh link.",
      }}
      stats={[
        { icon: "◎", tone: "orange", value: pendingCount, label: "Awaiting" },
        { icon: "✓", tone: "green", value: acceptedCount, label: "Accepted" },
        { icon: "◈", tone: "teal", value: closedCount, label: "All Invites" },
        {
          icon: "×",
          tone: "rose",
          value: Math.max(0, closedCount - pendingCount - acceptedCount),
          label: "Closed Other",
        },
      ]}
      tabs={[
        { key: "awaiting", label: `Awaiting (${pendingCount})` },
        { key: "closed", label: "Accepted & Closed" },
      ]}
      activeTab={stage}
      onTabChange={(key) => {
        setStage(key as Stage);
        setStatusFilter("all");
      }}
      search={query}
      searchPlaceholder="Search by email…"
      onSearchChange={setQuery}
      searchExtra={
        stage === "closed" ? (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="tb-roles-search !w-auto min-w-[9rem]"
            aria-label="Filter by status"
          >
            <option value="all">All statuses</option>
            <option value="accepted">Accepted</option>
            <option value="declined">Declined</option>
            <option value="revoked">Revoked</option>
            <option value="expired">Expired</option>
          </select>
        ) : null
      }
      quote="“An invitation is the first handshake of trust.”"
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Something went wrong"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingState variant="section" title="Loading invitations" message="Loading company invitations…" />
      ) : invites.length === 0 ? (
        <div className="tb-empty">
          <h3>
            {stage === "awaiting"
              ? "No pending invitations"
              : "No past invitations"}
          </h3>
          <p>
            {stage === "awaiting"
              ? "When you invite someone, they’ll appear here until they accept, decline, or the link expires."
              : "Accepted, declined, revoked, and expired invitations will appear here."}
          </p>
          {canInvite && stage === "awaiting" ? (
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
          {invites.map((invite) => (
            <li key={invite.id} className="tb-roles-row">
              <span className="tb-roles-glyph" data-tone="custom" aria-hidden>
                {initials(invite.invited_email)}
              </span>
              <div className="tb-roles-row-main min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="tb-roles-row-name">{invite.invited_email}</p>
                  <span
                    className="tb-roles-badge"
                    data-kind={
                      invite.status === "accepted" ? "system" : "custom"
                    }
                  >
                    {invite.role_name ?? "Role pending"}
                  </span>
                </div>
                <p className="tb-roles-row-desc">
                  {invite.delivery_email &&
                  invite.delivery_email !== invite.invited_email
                    ? `Sent to ${invite.delivery_email} · `
                    : ""}
                  Sent {formatJoined(invite.created_at)}
                  {invite.inviter_name ? ` · by ${invite.inviter_name}` : ""}
                </p>
              </div>
              <div className="tb-roles-row-meta">
                <div>
                  <strong>{invite.role_name ?? "—"}</strong>
                  <span>Role</span>
                </div>
              </div>
              <span className="tb-roles-status">{invite.status}</span>
              <div className="relative flex flex-wrap items-center gap-2">
                {canInvite &&
                (invite.status === "pending" || invite.status === "expired") ? (
                  <>
                    <button
                      type="button"
                      disabled={busyId === invite.id}
                      className="text-sm font-bold text-[var(--tb-accent)] hover:underline disabled:opacity-50"
                      onClick={() => {
                        setBusyId(invite.id);
                        void identityApi
                          .resendInvitation(invite.id)
                          .then(() => {
                            success(
                              "Invitation resent",
                              `Fresh link emailed to ${
                                invite.delivery_email ?? invite.invited_email
                              }.`,
                            );
                            setStage("awaiting");
                            reload();
                          })
                          .catch((err) => {
                            const message =
                              err instanceof ApiError
                                ? err.message
                                : "Could not resend invitation.";
                            setError(message);
                            toastError("Resend failed", message);
                          })
                          .finally(() => setBusyId(null));
                      }}
                    >
                      <BusyText busy={busyId === invite.id}>Resend</BusyText>
                    </button>
                    {invite.status === "pending" ? (
                      <button
                        type="button"
                        disabled={busyId === invite.id}
                        className="text-sm font-bold text-[#b42318] hover:underline disabled:opacity-50"
                        onClick={() => setRevokeInvite(invite)}
                      >
                        Revoke
                      </button>
                    ) : null}
                  </>
                ) : (
                  <span className="tb-meta">—</span>
                )}
              </div>
            </li>
          ))}
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
            <strong>Send a New Invitation</strong>
            <em>Choose a role and email a secure join link.</em>
          </span>
          <span className="tb-roles-create-go" aria-hidden>
            →
          </span>
        </button>
      ) : null}

      {total > 0 ? (
        <div className="mt-4 flex items-center justify-between border-t border-[var(--tb-line)] pt-4">
          <p className="tb-meta">
            {total} invitation{total === 1 ? "" : "s"}
          </p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <ConfirmModal
        open={Boolean(revokeInvite)}
        title="Revoke invitation?"
        asideTitle="They will lose the link"
        asideBody="This person can no longer accept this invite."
        confirmLabel="Revoke"
        pendingLabel="Revoking…"
        onClose={() => setRevokeInvite(null)}
        onConfirm={async () => {
          if (!revokeInvite) return;
          setBusyId(revokeInvite.id);
          try {
            await identityApi.revokeInvitation(revokeInvite.id);
            success(
              "Invitation revoked",
              `${revokeInvite.invited_email} can no longer accept.`,
            );
            reload();
          } catch (err) {
            const message =
              err instanceof ApiError
                ? err.message
                : "Could not revoke invitation.";
            setError(message);
            toastError("Revoke failed", message);
            throw err;
          } finally {
            setBusyId(null);
          }
        }}
      >
        <p className="text-sm text-[#5c574e]">
          Invitation:{" "}
          <span className="font-semibold text-[#0d3b2a]">
            {revokeInvite?.invited_email}
          </span>
        </p>
      </ConfirmModal>

      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onSent={reload}
      />
    </IdentityPageShell>
  );
}

export default function InvitationsPage() {
  return (
    <PermissionGate permission={["users.read", "users.invite"]}>
      <InvitationsPageInner />
    </PermissionGate>
  );
}
