"use client";

import { AdminCreateUserModal } from "@/components/admin/AdminCreateUserModal";
import { AdminIdentityNav } from "@/components/admin/AdminIdentityNav";
import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { SuspendAccountModal } from "@/components/admin/SuspendAccountModal";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/useConfirm";
import {
  platformUserName,
  statusTone,
} from "@/lib/admin/identityDirectory";
import { downloadPdf } from "@/lib/admin/downloadPdf";
import { ApiError } from "@/lib/api/client";
import { identityApi, type PlatformUser } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { formatJoined, initials } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type StatusFilter = "all" | "active" | "pending" | "suspended" | "deactivated";
type VerifiedFilter = "all" | "verified" | "unverified";
type MembershipFilter = "all" | "with_company" | "orphan" | "platform_only";
type SortKey = "newest" | "name" | "email" | "companies";

function AdminUsersPageInner() {
  const { hasPermission, user: currentUser } = useAuth();
  const { success, error: toastError } = useToast();
  const { confirm, dialog } = useConfirm();
  const searchParams = useSearchParams();
  const qFromUrl = searchParams.get("q") ?? "";
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState(qFromUrl);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [verifiedFilter, setVerifiedFilter] = useState<VerifiedFilter>("all");
  const [membershipFilter, setMembershipFilter] = useState<MembershipFilter>("all");
  const [companyNeedle, setCompanyNeedle] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const [selected, setSelected] = useState<PlatformUser | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<PlatformUser | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [statActive, setStatActive] = useState<number | null>(null);
  const [statPending, setStatPending] = useState<number | null>(null);
  const [statSuspended, setStatSuspended] = useState<number | null>(null);

  const canUpdate = hasPermission("users.update");
  const canInvite = hasPermission("users.invite");
  const [createOpen, setCreateOpen] = useState(false);

  const reload = useCallback(() => {
    setError(null);
    setLoading(true);
    void identityApi
      .listPlatformUsers({
        status: statusFilter === "all" ? undefined : statusFilter,
        q: query.trim() || undefined,
        email_verified:
          verifiedFilter === "all"
            ? undefined
            : verifiedFilter === "verified",
        page,
        page_size: pageSize,
      })
      .then((result) => {
        setUsers(result.data);
        setTotal(result.meta.total);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load users.",
        ),
      )
      .finally(() => setLoading(false));
  }, [page, pageSize, query, statusFilter, verifiedFilter]);

  useEffect(() => {
    setQuery(qFromUrl);
    setPage(1);
  }, [qFromUrl]);

  useEffect(() => {
    const handle = window.setTimeout(() => reload(), query ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [reload, query]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, verifiedFilter, query, pageSize]);

  useEffect(() => {
    void Promise.all([
      identityApi.listPlatformUsers({ status: "active", page: 1, page_size: 1 }),
      identityApi.listPlatformUsers({ status: "pending", page: 1, page_size: 1 }),
      identityApi.listPlatformUsers({ status: "suspended", page: 1, page_size: 1 }),
    ])
      .then(([a, p, s]) => {
        setStatActive(a.meta.total);
        setStatPending(p.meta.total);
        setStatSuspended(s.meta.total);
      })
      .catch(() => {
        
      });
  }, []);

  const filteredSorted = useMemo(() => {
    let rows = [...users];
    const companyQ = companyNeedle.trim().toLowerCase();
    if (membershipFilter === "orphan") {
      rows = rows.filter((u) => u.businesses.length === 0);
    } else if (membershipFilter === "with_company") {
      rows = rows.filter((u) =>
        u.businesses.some((b) => b.business_type && b.business_type !== "platform"),
      );
    } else if (membershipFilter === "platform_only") {
      rows = rows.filter(
        (u) =>
          u.businesses.length > 0 &&
          u.businesses.every((b) => b.business_type === "platform"),
      );
    }
    if (companyQ) {
      rows = rows.filter((u) =>
        u.businesses.some((b) =>
          (b.business_name || "").toLowerCase().includes(companyQ),
        ),
      );
    }
    rows.sort((a, b) => {
      if (sortKey === "name") {
        return platformUserName(a).localeCompare(platformUserName(b));
      }
      if (sortKey === "email") {
        return (a.email || "").localeCompare(b.email || "");
      }
      if (sortKey === "companies") {
        return b.businesses.length - a.businesses.length;
      }
      return 0;
    });
    return rows;
  }, [companyNeedle, membershipFilter, sortKey, users]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  function exportPage() {
    downloadPdf(
      `tradebay-users-page-${page}.pdf`,
      [
        "id",
        "name",
        "email",
        "status",
        "email_verified",
        "companies",
        "created_at",
        "suspension_reason",
      ],
      filteredSorted.map((u) => [
        u.id,
        platformUserName(u),
        u.email || "",
        u.status,
        u.email_verified_at ? "yes" : "no",
        u.businesses
          .map((b) => `${b.business_name || "?"} (${b.business_type || "?"})`)
          .join("; "),
        u.created_at || "",
        u.suspension_reason || "",
      ]),
      { title: "TradeBay users", subtitle: `Page ${page} · ${filteredSorted.length} row(s)` },
    );
    success("PDF exported", `${filteredSorted.length} users`);
  }

  return (
    <AdminPage>
      {dialog}
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.home} className="hover:underline">
          Admin
        </Link>{" "}
        / Identity / Users
      </p>
      <DirectoryMast
        title="Users"
        mark="Platform"
        size="page"
        actions={
          <div className="flex flex-wrap gap-2">
            {canInvite ? (
              <AdminAct tone="go" arrow onClick={() => setCreateOpen(true)}>
                Add user
              </AdminAct>
            ) : null}
            <AdminAct
              tone="ghost"
              onClick={exportPage}
              disabled={filteredSorted.length === 0}
            >
              Export PDF
            </AdminAct>
          </div>
        }
      />

      <AdminIdentityNav />

      {error ? (
        <div className="mt-4">
          <FeedbackBanner
            tone="error"
            title="Action couldn’t be completed"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      <div className="tb-summary">
        {[
          { label: "Matching", value: total },
          { label: "Active", value: statActive ?? "—" },
          { label: "Pending", value: statPending ?? "—" },
          { label: "Suspended", value: statSuspended ?? "—" },
        ].map((stat) => (
          <div key={stat.label} className="tb-summary-item">
            <p className="tb-summary-label">{stat.label}</p>
            <p className="tb-summary-value tb-num">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="tb-toolbar flex-wrap gap-y-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or email…"
          className="h-9 w-full max-w-sm border-0 border-b border-input bg-transparent px-0 text-sm outline-none focus:border-ring"
        />
        {(
          [
            ["all", "All"],
            ["active", "Active"],
            ["pending", "Pending"],
            ["suspended", "Suspended"],
            ["deactivated", "Deactivated"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className="tb-filter"
            data-active={statusFilter === key}
            onClick={() => setStatusFilter(key)}
          >
            {label}
          </button>
        ))}
        <select
          className="h-9 rounded-lg border border-input bg-card px-2 text-sm text-heading"
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          aria-label="Sort"
        >
          <option value="newest">Sort: newest</option>
          <option value="name">Sort: name</option>
          <option value="email">Sort: email</option>
          <option value="companies">Sort: companies</option>
        </select>
        <select
          className="h-9 rounded-lg border border-input bg-card px-2 text-sm text-heading"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="Page size"
        >
          {[10, 20, 50, 100].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      <div className="tb-cc-filters mt-0 sm:grid-cols-3">
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Email verification
            <select
              className="mt-1.5 h-10 w-full rounded-lg border border-input bg-card px-3 text-sm font-medium text-heading"
              value={verifiedFilter}
              onChange={(e) => setVerifiedFilter(e.target.value as VerifiedFilter)}
            >
              <option value="all">Any</option>
              <option value="verified">Verified only</option>
              <option value="unverified">Unverified only</option>
            </select>
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Membership (this page)
            <select
              className="mt-1.5 h-10 w-full rounded-lg border border-input bg-card px-3 text-sm font-medium text-heading"
              value={membershipFilter}
              onChange={(e) => setMembershipFilter(e.target.value as MembershipFilter)}
            >
              <option value="all">Any</option>
              <option value="with_company">Has trading company</option>
              <option value="orphan">No companies</option>
              <option value="platform_only">Platform staff only</option>
            </select>
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Company name contains
            <input
              value={companyNeedle}
              onChange={(e) => setCompanyNeedle(e.target.value)}
              placeholder="Filter memberships on this page…"
              className="mt-1.5 h-10 w-full rounded-lg border border-input bg-card px-3 text-sm text-heading outline-none focus:border-ring"
            />
          </label>
        </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)]">
        <div className="tb-data min-w-0">
          {loading ? (
            <LoadingEntity entity="accounts" className="py-12 justify-center" />
          ) : filteredSorted.length === 0 ? (
            <div className="tb-empty">
              <h3>No accounts match</h3>
              <p>Widen filters or clear search. Membership filters apply to the current page only.</p>
            </div>
          ) : (
            filteredSorted.map((user) => {
              const name = platformUserName(user);
              const isSelf = currentUser?.id === user.id;
              const open = selected?.id === user.id;
              return (
                <article
                  key={user.id}
                  className="tb-data-row grid-cols-1 gap-3 lg:grid-cols-[3rem_minmax(0,1.2fr)_minmax(0,1fr)_auto_auto]"
                  data-active={open || undefined}
                >
                  <button
                    type="button"
                    className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-primary text-xs font-bold text-primary-foreground"
                    onClick={() => setSelected(open ? null : user)}
                    aria-label={`Inspect ${name}`}
                  >
                    {user.avatar_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(user.avatar_url)} alt="" className="h-full w-full object-cover" />
                    ) : (
                      initials(name)
                    )}
                  </button>
                  <div className="min-w-0">
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 text-left font-semibold text-heading hover:underline"
                      onClick={() => setSelected(open ? null : user)}
                    >
                      <span>{name}</span>
                      <VerifiedBadge
                        verified={Boolean(user.email_verified_at)}
                        label={
                          user.email_verified_at
                            ? "Email verified"
                            : "Email not verified"
                        }
                      />
                    </button>
                    <p className="tb-meta truncate">{user.email}</p>
                    <p className="tb-meta mt-0.5">Joined {formatJoined(user.created_at)}</p>
                  </div>
                  <div className="min-w-0">
                    {user.businesses.length === 0 ? (
                      <p className="tb-meta">No businesses</p>
                    ) : (
                      <ul className="space-y-1">
                        {user.businesses.slice(0, 3).map((biz) => (
                          <li key={biz.membership_id} className="text-sm">
                            {biz.business_type && biz.business_type !== "platform" ? (
                              <Link
                                href={ROUTES.admin.businessDetail(biz.business_id)}
                                className="font-semibold text-link hover:underline"
                              >
                                {biz.business_name || "Business"}
                              </Link>
                            ) : (
                              <span className="font-semibold text-heading">
                                {biz.business_name || "Platform"}
                              </span>
                            )}
                            <span className="tb-meta">
                              {" "}
                              · {biz.role_name || "role"} · {biz.membership_status}
                            </span>
                          </li>
                        ))}
                        {user.businesses.length > 3 ? (
                          <li className="tb-meta">+{user.businesses.length - 3} more</li>
                        ) : null}
                      </ul>
                    )}
                  </div>
                  <div>
                    <span className="tb-status" data-tone={statusTone(user.status)}>
                      {user.status}
                    </span>
                    {user.suspension_reason ? (
                      <p className="mt-1 max-w-[12rem] text-xs text-destructive">
                        {user.suspension_reason}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <AdminAct
                      tone="go"
                      onClick={() => setSelected(open ? null : user)}
                    >
                      {open ? "Hide" : "Inspect"}
                    </AdminAct>
                    {canUpdate && !isSelf ? (
                      user.status !== "suspended" ? (
                        <AdminAct tone="danger" onClick={() => setSuspendTarget(user)}>
                          Suspend
                        </AdminAct>
                      ) : (
                        <AdminAct
                          tone="ok"
                          onClick={async () => {
                            const ok = await confirm({
                              title: `Reactivate ${name}?`,
                              body: "They will be able to sign in again.",
                              confirmLabel: "Reactivate",
                            });
                            if (!ok) return;
                            void identityApi
                              .reactivatePlatformUser(user.id)
                              .then(() => {
                                success("Reactivated", `${name} can sign in again.`);
                                reload();
                              })
                              .catch((err) => {
                                const message =
                                  err instanceof ApiError
                                    ? err.message
                                    : "Reactivate failed.";
                                setError(message);
                                toastError("Reactivate failed", message);
                              });
                          }}
                        >
                          Reactivate
                        </AdminAct>
                      )
                    ) : (
                      <span className="tb-meta">{isSelf ? "You" : "—"}</span>
                    )}
                  </div>
                </article>
              );
            })
          )}
        </div>

        <aside className="tb-panel h-fit p-4 lg:sticky lg:top-4">
          {selected ? (
            <div className="space-y-3 text-sm">
              <p className="tb-section-label">Account</p>
              <p className="font-[family-name:var(--font-outfit)] text-lg font-bold text-heading inline-flex items-center gap-2">
                {platformUserName(selected)}
                <VerifiedBadge
                  verified={Boolean(selected.email_verified_at)}
                  size="md"
                  label={
                    selected.email_verified_at
                      ? "Email verified"
                      : "Email not verified"
                  }
                />
              </p>
              <p className="text-muted-foreground">{selected.email}</p>
              <p>
                <span className="tb-status" data-tone={statusTone(selected.status)}>
                  {selected.status}
                </span>
              </p>
              <dl className="space-y-2 border-t border-border pt-3">
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground">Email</dt>
                  <dd>
                    <VerifiedBadge
                      verified={Boolean(selected.email_verified_at)}
                      label={
                        selected.email_verified_at
                          ? "Email verified"
                          : "Email not verified"
                      }
                    />
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Joined</dt>
                  <dd>{formatJoined(selected.created_at)}</dd>
                </div>
              </dl>
              <div className="border-t border-border pt-3">
                <p className="tb-section-label">Memberships ({selected.businesses.length})</p>
                {selected.businesses.length === 0 ? (
                  <p className="mt-2 text-muted-foreground">No company memberships.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {selected.businesses.map((biz) => (
                      <li key={biz.membership_id} className="rounded-lg bg-muted px-3 py-2">
                        {biz.business_type !== "platform" ? (
                          <Link
                            href={ROUTES.admin.businessDetail(biz.business_id)}
                            className="font-semibold text-heading hover:underline"
                          >
                            {biz.business_name || "Business"}
                          </Link>
                        ) : (
                          <span className="font-semibold">{biz.business_name || "Platform"}</span>
                        )}
                        <p className="tb-meta">
                          {biz.business_type} · {biz.role_name} · {biz.membership_status}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {canUpdate && currentUser?.id !== selected.id ? (
                <div className="border-t border-border pt-3">
                  {selected.status !== "suspended" ? (
                    <AdminAct
                      tone="danger"
                      className="w-full"
                      onClick={() => setSuspendTarget(selected)}
                    >
                      Suspend account
                    </AdminAct>
                  ) : (
                    <AdminAct
                      tone="ok"
                      className="w-full"
                      onClick={() => {
                        void identityApi
                          .reactivatePlatformUser(selected.id)
                          .then(() => {
                            success("Reactivated", "User can sign in again.");
                            reload();
                          })
                          .catch((err) => {
                            toastError(
                              "Failed",
                              err instanceof ApiError ? err.message : "Reactivate failed",
                            );
                          });
                      }}
                    >
                      Reactivate account
                    </AdminAct>
                  )}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Select <strong>Inspect</strong> on a row to see full memberships and take
              account actions.
            </p>
          )}
        </aside>
      </div>

      {total > 0 ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-input pt-4">
          <p className="tb-meta">
            {total} accounts · showing {filteredSorted.length} after page filters
          </p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <AdminCreateUserModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={async (payload) => {
          try {
            const created = await identityApi.createPlatformUser(payload);
            success("User created", created.email);
            reload();
          } catch (err) {
            throw new Error(
              err instanceof ApiError ? err.message : "Could not create user.",
            );
          }
        }}
      />

      <SuspendAccountModal
        open={Boolean(suspendTarget)}
        title="Suspend account"
        subjectLabel={suspendTarget ? platformUserName(suspendTarget) : "user"}
        confirmLabel="Suspend account"
        onClose={() => setSuspendTarget(null)}
        onConfirm={async (reason) => {
          if (!suspendTarget) return;
          try {
            const label = platformUserName(suspendTarget);
            await identityApi.suspendPlatformUser(suspendTarget.id, reason);
            success("Suspended", label);
            setSuspendTarget(null);
            setSelected(null);
            reload();
          } catch (err) {
            throw new Error(
              err instanceof ApiError ? err.message : "Suspension failed.",
            );
          }
        }}
        />
    </AdminPage>
  );
}

export default function AdminUsersPage() {
  return (
    <PermissionGate
      permission="users.read"
      fallbackTitle="User administration is restricted"
      fallbackDescription="Platform staff access is required to manage users."
    >
      <Suspense fallback={<LoadingEntity entity="users" className="p-8" />}>
        <AdminUsersPageInner />
      </Suspense>
    </PermissionGate>
  );
}
