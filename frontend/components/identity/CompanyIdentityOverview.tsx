"use client";

import type { AuthBusiness } from "@/lib/api/authApi";
import type { AuditEvent, Member, Role } from "@/lib/api/identityApi";
import {
  auditActorLabel,
  auditHeadline,
  auditTone,
  formatAuditWhen,
} from "@/lib/identity/auditCopy";
import {
  companyLocation,
  companySetupItems,
  companyTypeLabel,
  companyVerificationLabel,
} from "@/lib/identity/companyStory";
import { ROUTES } from "@/lib/constants";
import { initials } from "@/lib/team";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

type RoleBucket = {
  roleName: string;
  members: Member[];
};

type Props = {
  business: AuthBusiness;
  firstName?: string | null;
  memberCount: number;
  roleCount: number;
  pendingInvites: number;
  sessionCount: number;
  emailVerified: boolean;
  roleBuckets: RoleBucket[];
  roles: Role[];
  recentActivity: AuditEvent[];
  canInvite: boolean;
  canManageRoles: boolean;
  canReadAudit: boolean;
  onEditCompany: () => void;
  onOpenDocuments?: () => void;
};

const DONUT_COLORS = ["#1a6b4f", "#e86f2a", "#c45b4a", "#3b82c4", "#8b6bb5", "#6a726c"];

const TIPS = [
  {
    title: "A stronger team, bigger opportunities.",
    body: "Invite your key team members to collaborate and start sourcing together.",
  },
  {
    title: "Define how your team works.",
    body: "Create roles that match real responsibilities before you invite more people.",
  },
  {
    title: "Keep your company secure.",
    body: "Review sessions and the audit trail regularly as your team grows.",
  },
];

function formatMemberSince(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function MiniBars({ tone = "green" }: { tone?: "green" | "gray" | "orange" }) {
  const heights = [40, 55, 35, 70, 50, 85, 60];
  return (
    <div className="tb-ov-spark" data-tone={tone} aria-hidden>
      {heights.map((h, i) => (
        <span
          key={i}
          style={{
            height: `${h}%`,
            opacity: 0.35 + i * 0.08,
          }}
        />
      ))}
    </div>
  );
}

function TeamDonut({
  buckets,
  total,
}: {
  buckets: RoleBucket[];
  total: number;
}) {
  const slices = useMemo(() => {
    if (total <= 0) return [] as { name: string; count: number; color: string; pct: number }[];
    return buckets.map((b, i) => ({
      name: b.roleName,
      count: b.members.length,
      color: DONUT_COLORS[i % DONUT_COLORS.length],
      pct: (b.members.length / total) * 100,
    }));
  }, [buckets, total]);

  const gradient = useMemo(() => {
    if (slices.length === 0) return undefined;
    let cursor = 0;
    const parts = slices.map((s) => {
      const start = cursor;
      cursor += s.pct;
      return `${s.color} ${start}% ${cursor}%`;
    });
    return `conic-gradient(${parts.join(", ")})`;
  }, [slices]);

  return (
    <div className="tb-ov-donut-wrap">
      <div
        className="tb-ov-donut"
        data-empty={slices.length === 0 ? "true" : undefined}
        style={gradient ? { background: gradient } : undefined}
      >
        <div className="tb-ov-donut-hole">
          <strong>{total}</strong>
          <span>Members</span>
        </div>
      </div>
      <ul className="tb-ov-donut-legend">
        {slices.map((s) => (
          <li key={s.name}>
            <i style={{ background: s.color }} />
            <span>{s.name}</span>
            <strong>{s.count}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CompanyIdentityOverview({
  business,
  firstName,
  memberCount,
  roleCount,
  pendingInvites,
  sessionCount,
  emailVerified,
  roleBuckets,
  roles: _roles,
  recentActivity,
  canInvite,
  canManageRoles,
  canReadAudit,
  onEditCompany,
  onOpenDocuments,
}: Props) {
  const verification = companyVerificationLabel(business);
  const location = companyLocation(business);
  const isSupplier = business.type === "supplier";
  const verified = verification.tone === "ok";
  const memberSince = formatMemberSince(business.created_at);
  const name = firstName?.trim() || "there";
  const [tipIndex, setTipIndex] = useState(0);
  const [tipHidden, setTipHidden] = useState(false);

  const setup = companySetupItems({
    business,
    memberCount,
    roleCount,
    pendingInvites,
    emailVerified,
    routes: {
      members: ROUTES.members,
      roles: ROUTES.roles,
      invitations: ROUTES.invitations,
      verify: `${ROUTES.businesses}?tab=documents`,
      profile: `${ROUTES.businesses}?tab=settings`,
    },
  });

  const doneCount = setup.filter((s) => s.done).length;
  const tip = TIPS[tipIndex % TIPS.length];

  const typePill = isSupplier
    ? `${companyTypeLabel(business.type)}`
    : companyTypeLabel(business.type);

  return (
    <article className="tb-ov">
      <p className="tb-ov-crumb">
        Company Identity <span>/</span> Overview
      </p>

      <header className="tb-ov-hero">
        <div className="tb-ov-hero-copy">
          <p className="tb-ov-hello">
            Good to see you, {name}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2.5">
            <h1 className="tb-ov-title">{business.name}</h1>
            <span className="tb-ov-verified" data-tone={verification.tone}>
              {verification.label}
            </span>
          </div>
          <p className="tb-ov-lede">
            Your company workspace on TradeBay. Build your team, manage access,
            and grow your opportunities.
          </p>
          <div className="tb-ov-actions">
            <button type="button" onClick={onEditCompany} className="tb-ov-btn-primary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
                <path
                  d="M12 3.5v2.2M12 18.3v2.2M4.9 6.5l1.6 1.6M17.5 15.9l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.9 17.5l1.6-1.6M17.5 8.1l1.6-1.6"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
              Manage Company
            </button>
            <button
              type="button"
              onClick={onEditCompany}
              className="tb-ov-btn-ghost"
            >
              View Company Profile
              <span aria-hidden>→</span>
            </button>
            {isSupplier && !verified && onOpenDocuments ? (
              <button
                type="button"
                onClick={onOpenDocuments}
                className="tb-ov-btn-accent"
              >
                {business.verification_status === "pending"
                  ? "View verification"
                  : "Complete verification"}
              </button>
            ) : null}
          </div>
          <div className="tb-ov-meta">
            {location ? <span className="tb-ov-chip">{location}</span> : null}
            <span className="tb-ov-chip">{typePill}</span>
            {memberSince ? (
              <span className="tb-ov-chip">Member since {memberSince}</span>
            ) : null}
          </div>
        </div>
        <div className="tb-ov-hero-visual">
          <Image
            src="/images/tradebay-port-banner.jpg"
            alt=""
            fill
            priority
            className="object-cover object-[center_40%]"
            sizes="420px"
          />
          <div className="tb-ov-hero-visual-wash" />
          <p className="tb-ov-hero-script">Local Roots. Bigger Opportunities.</p>
        </div>
      </header>

      <section className="tb-ov-stats">
        <Link href={ROUTES.members} className="tb-ov-stat">
          <span className="tb-ov-stat-icon" data-tone="green">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.7" />
              <path d="M3.5 19a5.5 5.5 0 0 1 11 0" stroke="currentColor" strokeWidth="1.7" />
              <circle cx="17" cy="9" r="2.4" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </span>
          <div>
            <p className="tb-ov-stat-label">Team Members</p>
            <p className="tb-ov-stat-value">{memberCount}</p>
          </div>
          <MiniBars tone="green" />
        </Link>
        <Link href={ROUTES.roles} className="tb-ov-stat">
          <span className="tb-ov-stat-icon" data-tone="forest">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M4 20V7l8-3 8 3v13" stroke="currentColor" strokeWidth="1.7" />
              <path d="M9 20v-5h6v5" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </span>
          <div>
            <p className="tb-ov-stat-label">Roles</p>
            <p className="tb-ov-stat-value">{roleCount}</p>
          </div>
          <MiniBars tone="gray" />
        </Link>
        <Link href={ROUTES.invitations} className="tb-ov-stat">
          <span className="tb-ov-stat-icon" data-tone="orange">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M4 7h16v10H4V7Z" stroke="currentColor" strokeWidth="1.7" />
              <path d="m4 7 8 6 8-6" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </span>
          <div>
            <p className="tb-ov-stat-label">Pending Invitations</p>
            <p className="tb-ov-stat-value">{pendingInvites}</p>
          </div>
          <MiniBars tone="orange" />
        </Link>
        <Link href={ROUTES.sessions} className="tb-ov-stat">
          <span className="tb-ov-stat-icon" data-tone="green">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                d="M12 3 5 6v5c0 4.5 3 7.8 7 9 4-1.2 7-4.5 7-9V6l-7-3Z"
                stroke="currentColor"
                strokeWidth="1.7"
              />
            </svg>
          </span>
          <div>
            <p className="tb-ov-stat-label">Active Sessions</p>
            <p className="tb-ov-stat-value">{sessionCount}</p>
          </div>
          <MiniBars tone="green" />
        </Link>
      </section>

      <section className="tb-ov-mid">
        <div className="tb-ov-card">
          <div className="tb-ov-card-head">
            <h2>Team Structure</h2>
          </div>
          {memberCount === 0 || roleBuckets.length === 0 ? (
            <p className="tb-ov-empty">No members yet. Invite people to build your team.</p>
          ) : (
            <TeamDonut
              buckets={roleBuckets}
              total={roleBuckets.reduce((n, b) => n + b.members.length, 0)}
            />
          )}
          <Link href={ROUTES.members} className="tb-ov-card-link">
            View All Members →
          </Link>
        </div>

        <div className="tb-ov-card">
          <div className="tb-ov-card-head">
            <h2>Recent Activity</h2>
            {canReadAudit ? (
              <Link href={ROUTES.audit} className="tb-ov-view-all">
                View All →
              </Link>
            ) : null}
          </div>
          {recentActivity.length === 0 ? (
            <p className="tb-ov-empty">
              Company activity will appear here as your team works.
            </p>
          ) : (
            <ul className="tb-ov-activity">
              {recentActivity.slice(0, 5).map((event) => {
                const tone = auditTone(event);
                const who = auditActorLabel(event);
                return (
                  <li key={event.id}>
                    <span className="tb-ov-activity-mark" data-tone={tone} aria-hidden>
                      {tone === "warn" ? "!" : tone === "ok" ? "✓" : "•"}
                    </span>
                    <span className="tb-ov-activity-avatar" aria-hidden>
                      {initials(who)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p>{auditHeadline(event)}</p>
                      <time>{formatAuditWhen(event.created_at)}</time>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="tb-ov-card">
          <div className="tb-ov-card-head">
            <h2>Quick Actions</h2>
          </div>
          <div className="tb-ov-actions-stack">
            {canInvite ? (
              <Link href={ROUTES.invitations} className="tb-ov-qaction" data-tone="green">
                <span className="tb-ov-qaction-icon">+</span>
                <span>
                  <strong>Invite a Member</strong>
                  <em>Bring someone to your team</em>
                </span>
              </Link>
            ) : null}
            {canManageRoles ? (
              <Link href={ROUTES.rolesNew} className="tb-ov-qaction" data-tone="orange">
                <span className="tb-ov-qaction-icon">◎</span>
                <span>
                  <strong>Create a Role</strong>
                  <em>Define a responsibility</em>
                </span>
              </Link>
            ) : null}
            <Link href={ROUTES.permissions} className="tb-ov-qaction" data-tone="amber">
              <span className="tb-ov-qaction-icon">☰</span>
              <span>
                <strong>Manage Permissions</strong>
                <em>Review what roles can do</em>
              </span>
            </Link>
            {canReadAudit ? (
              <Link href={ROUTES.audit} className="tb-ov-qaction" data-tone="rose">
                <span className="tb-ov-qaction-icon">◷</span>
                <span>
                  <strong>View Audit Log</strong>
                  <em>See who changed what</em>
                </span>
              </Link>
            ) : (
              <Link href={ROUTES.sessions} className="tb-ov-qaction" data-tone="rose">
                <span className="tb-ov-qaction-icon">◷</span>
                <span>
                  <strong>Manage Sessions</strong>
                  <em>Review signed-in devices</em>
                </span>
              </Link>
            )}
          </div>
        </div>
      </section>

      <section className="tb-ov-bottom">
        <div className="tb-ov-card tb-ov-complete">
          <div className="tb-ov-card-head">
            <h2>Company Completion</h2>
            <span className="tb-ov-complete-count">
              {doneCount} of {setup.length} completed
            </span>
          </div>
          <div className="tb-ov-progress">
            <div
              className="tb-ov-progress-fill"
              style={{ width: `${(doneCount / Math.max(setup.length, 1)) * 100}%` }}
            />
          </div>
          <ol className="tb-ov-steps">
            {setup.map((item, index) => (
              <li key={item.key} data-done={item.done} data-current={!item.done && setup.slice(0, index).every((s) => s.done)}>
                <span className="tb-ov-step-dot" aria-hidden>
                  {item.done ? "✓" : index + 1}
                </span>
                <span className="tb-ov-step-label">{item.label}</span>
              </li>
            ))}
          </ol>
        </div>

        {!tipHidden ? (
          <div className="tb-ov-card tb-ov-tip">
            <div className="tb-ov-card-head">
              <h2>Tips for Your Business</h2>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="tb-ov-tip-nav"
                  aria-label="Previous tip"
                  onClick={() => setTipIndex((i) => (i + TIPS.length - 1) % TIPS.length)}
                >
                  ‹
                </button>
                <button
                  type="button"
                  className="tb-ov-tip-nav"
                  aria-label="Next tip"
                  onClick={() => setTipIndex((i) => (i + 1) % TIPS.length)}
                >
                  ›
                </button>
                <button
                  type="button"
                  className="tb-ov-tip-nav"
                  aria-label="Dismiss tip"
                  onClick={() => setTipHidden(true)}
                >
                  ×
                </button>
              </div>
            </div>
            <div className="tb-ov-tip-body">
              <span className="tb-ov-tip-bulb" aria-hidden>
                ✦
              </span>
              <div>
                <p className="tb-ov-tip-title">{tip?.title}</p>
                <p className="tb-ov-tip-copy">{tip?.body}</p>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </article>
  );
}
