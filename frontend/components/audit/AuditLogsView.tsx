"use client";

import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { ApiError } from "@/lib/api/client";
import { identityApi, type AuditEvent } from "@/lib/api/identityApi";
import {
  auditHeadline,
  auditTone,
  formatAuditWhen,
} from "@/lib/identity/auditCopy";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type AuditListProps = {
  mode?: "business" | "platform";
};

const ACTION_PRESETS = [
  { value: "", label: "All actions" },
  { value: "USER_INVITED", label: "Invitations sent" },
  { value: "INVITATION_ACCEPTED", label: "Invitations accepted" },
  { value: "INVITATION_REVOKED", label: "Invitations revoked" },
  { value: "INVITATION_RESENT", label: "Invitations resent" },
  { value: "MEMBER_ROLE_CHANGED", label: "Role changes" },
  { value: "MEMBER_REMOVED", label: "Members removed" },
  { value: "MEMBERSHIP_SUSPENDED", label: "Members suspended" },
  { value: "MEMBERSHIP_REACTIVATED", label: "Members reactivated" },
  { value: "ROLE_CREATED", label: "Roles created" },
  { value: "ROLE_UPDATED", label: "Roles updated" },
  { value: "ROLE_DELETED", label: "Roles deleted" },
  { value: "BUSINESS_UPDATED", label: "Company updates" },
];

const ENTITY_PRESETS = [
  { value: "", label: "All entities" },
  { value: "invitation", label: "Invitation" },
  { value: "membership", label: "Membership" },
  { value: "role", label: "Role" },
  { value: "user", label: "User" },
  { value: "session", label: "Session" },
  { value: "business", label: "Business" },
];

export function AuditLogsView({ mode = "business" }: AuditListProps) {
  const { hasPermission } = useAuth();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const canRead = hasPermission("audit_logs.read");

  const reload = useCallback(() => {
    if (!canRead) return;
    setLoading(true);
    setError(null);
    const params = {
      action: action.trim() || undefined,
      resource_type: resourceType.trim() || undefined,
      page,
      page_size: pageSize,
    };
    const request =
      mode === "platform"
        ? identityApi.listPlatformAuditLogs(params)
        : identityApi.listAuditLogs(params);
    void request
      .then((result) => {
        setEvents(result.data);
        setTotal(result.meta.total);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Couldn't load audit logs.",
        ),
      )
      .finally(() => setLoading(false));
  }, [action, canRead, mode, page, resourceType]);

  useEffect(() => {
    const handle = window.setTimeout(
      () => reload(),
      action || resourceType ? 250 : 0,
    );
    return () => window.clearTimeout(handle);
  }, [reload, action, resourceType]);

  useEffect(() => {
    setPage(1);
  }, [action, resourceType, query]);

  const detailBase = mode === "platform" ? ROUTES.admin.audit : ROUTES.audit;
  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const visibleEvents = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return events;
    return events.filter((event) => {
      const meta = JSON.stringify(event.metadata ?? {}).toLowerCase();
      const haystack = [
        auditHeadline(event),
        event.action ?? "",
        event.resource_type ?? "",
        event.resource_id ?? "",
        event.ip_address ?? "",
        event.user_id ?? "",
        meta,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [events, query]);

  const warnCount = useMemo(
    () => events.filter((e) => auditTone(e) === "warn").length,
    [events],
  );
  const okCount = useMemo(
    () => events.filter((e) => auditTone(e) === "ok").length,
    [events],
  );

  if (!canRead) {
    return (
      <FeedbackBanner tone="warning" title="Access restricted">
        You don&apos;t have access to view audit events. Contact your business
        administrator if you need access.
      </FeedbackBanner>
    );
  }

  return (
    <IdentityPageShell
      crumb={
        mode === "platform"
          ? "Platform / Audit"
          : "Company Identity / Audit"
      }
      title={mode === "platform" ? "Platform Audit" : "Audit Trail"}
      mark={mode === "platform" ? "Platform" : "TradeBay"}
      lede={
        mode === "platform"
          ? "Who did what across TradeBay — in plain language."
          : "Who changed what in this company — invitations, roles, and access."
      }
      banner={{
        icon: "◎",
        title: "Every change leaves a mark.",
        body: "Filter by action or entity, then open an event for the full forensic detail.",
      }}
      stats={[
        { icon: "☰", tone: "teal", value: total, label: "Events" },
        { icon: "✓", tone: "green", value: okCount, label: "On Page · OK" },
        { icon: "!", tone: "orange", value: warnCount, label: "On Page · Warn" },
        {
          icon: "⌕",
          tone: "rose",
          value: visibleEvents.length,
          label: "Showing",
        },
      ]}
      search={query}
      searchPlaceholder="Search events…"
      onSearchChange={setQuery}
      searchExtra={
        <>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value)}
            className="tb-roles-search !w-auto min-w-[11rem]"
            aria-label="Filter by action"
          >
            {ACTION_PRESETS.map((preset) => (
              <option key={preset.value || "all"} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
          <select
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            className="tb-roles-search !w-auto min-w-[10rem]"
            aria-label="Filter by entity"
          >
            {ENTITY_PRESETS.map((preset) => (
              <option key={preset.value || "all"} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
          {action || resourceType || query ? (
            <button
              type="button"
              onClick={() => {
                setAction("");
                setResourceType("");
                setQuery("");
              }}
              className="text-sm font-semibold text-muted-foreground hover:text-heading"
            >
              Clear
            </button>
          ) : null}
        </>
      }
      quote="“Trust is built in quiet records.”"
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Couldn’t load audit logs"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingEntity entity="trail" className="py-12 justify-center" />
      ) : visibleEvents.length === 0 ? (
        <div className="tb-empty">
          <h3>No events in this filter</h3>
          <p>
            Try clearing filters, or wait for team and security actions to
            produce entries.
          </p>
        </div>
      ) : (
        <ul className="tb-roles-list">
          {visibleEvents.map((event) => {
            const tone = auditTone(event);
            return (
              <li key={event.id} className="tb-roles-row">
                <span
                  className="tb-roles-glyph"
                  data-tone={
                    tone === "warn"
                      ? "admin"
                      : tone === "ok"
                        ? "sales"
                        : "viewer"
                  }
                  aria-hidden
                >
                  {tone === "warn" ? "!" : tone === "ok" ? "✓" : "·"}
                </span>
                <div className="tb-roles-row-main min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`${detailBase}/${event.id}`}
                      className="tb-roles-row-name"
                    >
                      {auditHeadline(event)}
                    </Link>
                    {event.resource_type ? (
                      <span className="tb-roles-badge" data-kind="custom">
                        {event.resource_type}
                      </span>
                    ) : null}
                  </div>
                  <p className="tb-roles-row-desc">
                    {event.action ?? "Event"}
                    {event.ip_address ? ` · ${event.ip_address}` : ""}
                  </p>
                </div>
                <div className="tb-roles-row-meta">
                  <div>
                    <strong>{formatAuditWhen(event.created_at)}</strong>
                    <span>When</span>
                  </div>
                </div>
                <Link
                  href={`${detailBase}/${event.id}`}
                  className="text-sm font-bold text-accent hover:underline"
                >
                  Open →
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      {total > 0 ? (
        <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
          <p className="tb-meta">{total} events</p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}
    </IdentityPageShell>
  );
}
