"use client";

import { CompanyIdentityOverview } from "@/components/identity/CompanyIdentityOverview";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { CompanyProfileView } from "@/components/company/CompanyProfileView";
import {
  identityApi,
  type AuditEvent,
  type Business,
  type Member,
  type Role,
} from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingState } from "@/components/ui/LoadingState";

type TabKey = "overview" | "settings" | "documents";

export default function BusinessesPage() {
  return (
    <Suspense
      fallback={
        <div className="tb-page flex min-h-[50vh] items-center justify-center px-4 py-10" data-surface="studio">
          <LoadingState
            variant="page"
            title="Loading company"
            message="Opening your company workspace…"
          />
        </div>
      }
    >
      <BusinessesPageInner />
    </Suspense>
  );
}

function BusinessesPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { business, businesses, refreshSession, user, hasPermission } = useAuth();
  const tabParam = searchParams.get("tab");
  const tab: TabKey =
    tabParam === "settings" || tabParam === "documents" ? tabParam : "overview";

  function setTab(next: TabKey) {
    if (next === "overview") router.replace(ROUTES.businesses);
    else router.replace(`${ROUTES.businesses}?tab=${next}`);
  }

  const [detail, setDetail] = useState<Business | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [memberCount, setMemberCount] = useState(0);
  const [inviteCount, setInviteCount] = useState(0);
  const [roleCount, setRoleCount] = useState(0);
  const [recentActivity, setRecentActivity] = useState<AuditEvent[]>([]);
  const [sessionCount, setSessionCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const active = detail ?? business;
  const isSupplier = (detail ?? business)?.type === "supplier";

  useEffect(() => {
    if (tabParam === "team") router.replace(ROUTES.members);
  }, [tabParam, router]);

  useEffect(() => {
    if (!business?.id) {
      setDetail(null);
      return;
    }
    void identityApi
      .getBusiness(business.id)
      .then((row) => setDetail(row))
      .catch(() => setDetail(business));
  }, [business]);

  useEffect(() => {
    if (!business?.id) return;
    void identityApi
      .listMembers({ page: 1, page_size: 100 })
      .then((result) => {
        setMembers(result.data);
        setMemberCount(result.meta.total);
      })
      .catch(() => {
        setMembers([]);
        setMemberCount(0);
      });
    void identityApi
      .listInvitations({ status: "pending", page: 1, page_size: 1 })
      .then((result) => setInviteCount(result.meta.total))
      .catch(() => setInviteCount(0));
    void identityApi
      .listRoles({ page: 1, page_size: 100 })
      .then((result) => {
        setRoles(result.data);
        setRoleCount(result.meta.total);
      })
      .catch(() => {
        setRoles([]);
        setRoleCount(0);
      });
    if (hasPermission("audit_logs.read")) {
      void identityApi
        .listAuditLogs({ page: 1, page_size: 6 })
        .then((result) => setRecentActivity(result.data))
        .catch(() => setRecentActivity([]));
    } else {
      setRecentActivity([]);
    }
    void identityApi
      .listSessions()
      .then((rows) => setSessionCount(Array.isArray(rows) ? rows.length : 0))
      .catch(() => setSessionCount(0));
  }, [business?.id, hasPermission]);

  useEffect(() => {
    if (!isSupplier && tab === "documents") setTab("settings");
  }, [isSupplier, tab]);

  useEffect(() => {
    if ((tab !== "documents" && tab !== "settings") || !business?.id) return;
    void identityApi
      .getBusiness(business.id)
      .then((row) => setDetail(row))
      .catch(() => undefined);
  }, [tab, business?.id]);

  const roleBuckets = useMemo(() => {
    const map = new Map<string, Member[]>();
    for (const member of members) {
      if (member.status === "removed") continue;
      const key = member.role_name || "Unassigned";
      const list = map.get(key) ?? [];
      list.push(member);
      map.set(key, list);
    }
    return [...map.entries()]
      .map(([roleName, rows]) => ({ roleName, members: rows }))
      .sort((a, b) => {
        if (a.roleName === "Business Admin") return -1;
        if (b.roleName === "Business Admin") return 1;
        return b.members.length - a.members.length;
      });
  }, [members]);

  if (!active) {
    return (
      <IdentityPageShell
        crumb="Company Identity / Business"
        title="Your Business"
        lede="Establish your company on TradeBay — then build your team and define access."
        action={
          <Link href={ROUTES.businessesNew} className="tb-ov-btn-primary">
            + Establish Company
          </Link>
        }
        banner={{
          icon: "+",
          title: "Your business starts here.",
          body: "Create a company workspace to invite teammates and assign roles.",
        }}
        quote="“Every trade begins with a named company.”"
      >
        <button
          type="button"
          className="tb-roles-create-card w-full text-left"
          onClick={() => router.push(ROUTES.businessesNew)}
        >
          <span className="tb-roles-create-plus" aria-hidden>
            +
          </span>
          <span>
            <strong>Establish your company</strong>
            <em>Set up profile, domain, and verification on TradeBay.</em>
          </span>
          <span className="tb-roles-create-go" aria-hidden>
            →
          </span>
        </button>
        {businesses.length > 0 ? (
          <p className="mt-4 text-xs text-[var(--tb-muted-fg)]">
            Your session opens inside one company workspace — there is no company
            switcher.
          </p>
        ) : null}
      </IdentityPageShell>
    );
  }

  const verified = isSupplier
    ? active.verification_status === "verified"
    : active.status === "verified" || active.status === "active";

  if (tab === "settings" || tab === "documents") {
    return (
      <div className="tb-page" data-surface="studio">
        {error ? (
          <FeedbackBanner tone="error" title="Couldn’t load company" className="mb-4">
            {error}
          </FeedbackBanner>
        ) : null}
        <CompanyProfileView
          key={`${active.id}-${tab}`}
          business={active}
          memberCount={memberCount}
          locked={Boolean(verified && isSupplier)}
          initialTab={tab === "documents" ? "verification" : "details"}
          onSaved={(row) => {
            setDetail(row);
            setError(null);
            void refreshSession();
          }}
          onOpenDocuments={
            isSupplier
              ? () => {
                  setTab("settings");
                }
              : undefined
          }
        />
      </div>
    );
  }

  return (
    <div className="tb-page" data-surface="studio">
      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load company" className="mt-4">
          {error}
        </FeedbackBanner>
      ) : null}

      <CompanyIdentityOverview
        business={active}
        firstName={user?.first_name}
        memberCount={memberCount}
        roleCount={roleCount}
        pendingInvites={inviteCount}
        sessionCount={sessionCount}
        emailVerified={Boolean(user?.email_verified_at)}
        roleBuckets={roleBuckets}
        roles={roles}
        recentActivity={recentActivity}
        canInvite={hasPermission("users.invite")}
        canManageRoles={hasPermission("roles.manage")}
        canReadAudit={hasPermission("audit_logs.read")}
        onEditCompany={() => setTab("settings")}
        onOpenDocuments={isSupplier ? () => setTab("documents") : undefined}
      />
    </div>
  );
}
