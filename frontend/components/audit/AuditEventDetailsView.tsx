"use client";

import { ApiError } from "@/lib/api/client";
import { identityApi, type AuditEvent } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import {
  auditActorLabel,
  auditHeadline,
  auditTargetLabel,
} from "@/lib/identity/auditCopy";
import { formatJoined } from "@/lib/team";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type AuditDetailProps = {
  mode?: "business" | "platform";
};

export function AuditEventDetailsView({ mode = "business" }: AuditDetailProps) {
  const params = useParams<{ id: string }>();
  const [event, setEvent] = useState<AuditEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const backHref = mode === "platform" ? ROUTES.admin.audit : ROUTES.audit;

  useEffect(() => {
    if (!params.id) return;
    const request =
      mode === "platform"
        ? identityApi.getPlatformAuditLog(params.id)
        : identityApi.getAuditLog(params.id);
    void request
      .then(setEvent)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load event."),
      );
  }, [mode, params.id]);

  if (error && !event) {
    return (
      <div className="space-y-3">
        <Link href={backHref} className="text-sm font-semibold text-[#0d3b2a] hover:underline">
          ← Back to audit logs
        </Link>
        <p className="rounded-xl bg-[#fef3f2] px-3.5 py-2.5 text-sm text-[#b42318]">{error}</p>
      </div>
    );
  }

  if (!event) {
    return <LoadingEntity entity="event" />;
  }

  const rows: { label: string; value: string }[] = [
    { label: "Summary", value: auditHeadline(event) },
    { label: "Action", value: event.action ?? "—" },
    { label: "Actor", value: auditActorLabel(event) },
    { label: "Subject", value: auditTargetLabel(event) },
    { label: "Entity type", value: event.resource_type ?? "—" },
    { label: "IP address", value: event.ip_address ?? "—" },
    { label: "Timestamp", value: formatJoined(event.created_at) },
  ];

  const metadata = Object.fromEntries(
    Object.entries(event.metadata ?? {}).filter(
      ([key]) => !/(^id$|_id$)/i.test(key),
    ),
  );

  return (
    <div className="space-y-5">
      <div>
        <Link href={backHref} className="text-sm font-semibold text-[#0d3b2a] hover:underline">
          ← Back to audit logs
        </Link>
        <h1 className="mt-2 font-[family-name:var(--font-syne)] text-2xl font-bold text-[#0c1612]">
          {auditHeadline(event)}
        </h1>
      </div>

      <div className="tb-card p-5" data-kind="info">
        <dl className="relative z-[1] grid gap-3 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label}>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--tb-card-muted)]">
                {row.label}
              </dt>
              <dd className="mt-1 break-all text-sm font-medium text-[var(--tb-card-fg)]">
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {Object.keys(metadata).length > 0 ? (
        <div className="tb-card overflow-hidden" data-kind="info">
          <div className="relative z-[1] px-5 pt-5">
            <h2 className="font-semibold text-[var(--tb-card-fg)]">Details</h2>
            <pre className="mt-3 overflow-x-auto rounded-xl bg-[#f3f7f5] p-3 text-xs text-[var(--tb-card-fg)]">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </div>
          <div className="tb-card-footer">
            <Link href={backHref} className="tb-card-action">
              Back to logs →
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
