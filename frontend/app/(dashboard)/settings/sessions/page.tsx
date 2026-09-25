"use client";

import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { BusyText } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type SessionDevice } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { formatJoined } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

type SessionFilter = "all" | "current" | "other";

function deviceLabel(agent: string | null | undefined): string {
  if (!agent) return "Unknown device";
  if (/Mobile|Android|iPhone/i.test(agent)) return "Mobile browser";
  if (/Edg\//i.test(agent)) return "Microsoft Edge";
  if (/Chrome\//i.test(agent)) return "Chrome";
  if (/Firefox\//i.test(agent)) return "Firefox";
  if (/Safari\//i.test(agent)) return "Safari";
  return agent.slice(0, 48);
}

export default function SessionsPage() {
  const { logout } = useAuth();
  const { success, error: toastError } = useToast();
  const [sessions, setSessions] = useState<SessionDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<SessionFilter>("all");

  const reload = useCallback(() => {
    void identityApi
      .listSessions()
      .then((rows) => {
        setSessions(Array.isArray(rows) ? rows : []);
        setError(null);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load sessions."),
      );
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sessions.filter((session) => {
      if (filter === "current" && !session.is_current) return false;
      if (filter === "other" && session.is_current) return false;
      if (!q) return true;
      const haystack = [
        deviceLabel(session.user_agent),
        session.user_agent ?? "",
        session.ip_address ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [filter, query, sessions]);

  const otherCount = sessions.filter((s) => !s.is_current).length;

  return (
    <IdentityPageShell
      crumb="Account / Sessions"
      title="Active Sessions"
      lede="Devices signed into your TradeBay account. Revoke any you don’t recognize."
      action={
        <button
          type="button"
          disabled={busyId === "others" || otherCount === 0}
          className="tb-btn tb-btn--primary"
          onClick={() => {
            setBusyId("others");
            setError(null);
            void identityApi
              .revokeOtherSessions()
              .then(() => {
                success(
                  "Other sessions revoked",
                  "You’re still signed in on this device only.",
                );
                reload();
              })
              .catch((err) => {
                const message =
                  err instanceof ApiError
                    ? err.message
                    : "Couldn't revoke sessions.";
                setError(message);
                toastError("Revoke failed", message);
              })
              .finally(() => setBusyId(null));
          }}
        >
          <BusyText busy={busyId === "others"}>Revoke Other Sessions</BusyText>
        </button>
      }
      banner={{
        icon: "◉",
        title: "Keep only the desks you trust.",
        body: "If a device looks unfamiliar, revoke it immediately.",
      }}
      stats={[
        {
          icon: "◉",
          tone: "teal",
          value: sessions.length,
          label: "Total Devices",
        },
        {
          icon: "✓",
          tone: "green",
          value: sessions.some((s) => s.is_current) ? 1 : 0,
          label: "This Device",
        },
        {
          icon: "◎",
          tone: "orange",
          value: otherCount,
          label: "Other Devices",
        },
      ]}
      tabs={[
        { key: "all", label: "All Devices" },
        { key: "current", label: "This Device" },
        { key: "other", label: "Other Devices" },
      ]}
      activeTab={filter}
      onTabChange={(key) => setFilter(key as SessionFilter)}
      search={query}
      searchPlaceholder="Search by device or IP…"
      onSearchChange={setQuery}
      quote="“One trusted device is better than ten forgotten ones.”"
    >
      <p className="mb-2">
        <BackLink href={ROUTES.settings}>Account settings</BackLink>
      </p>

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

      {filtered.length === 0 ? (
        <div className="tb-empty">
          <h3>No sessions match</h3>
          <p>
            {sessions.length === 0
              ? "Sessions appear here after you sign in from a browser or device."
              : "Try a different search or filter."}
          </p>
        </div>
      ) : (
        <ul className="tb-roles-list">
          {filtered.map((session) => (
            <li key={session.id} className="tb-roles-row">
              <span
                className="tb-roles-glyph"
                data-tone={session.is_current ? "sales" : "viewer"}
                aria-hidden
              >
                {session.is_current ? "✓" : "◉"}
              </span>
              <div className="tb-roles-row-main min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="tb-roles-row-name">
                    {deviceLabel(session.user_agent)}
                  </p>
                  {session.is_current ? (
                    <span className="tb-roles-badge" data-kind="system">
                      This device
                    </span>
                  ) : null}
                </div>
                <p className="tb-roles-row-desc">
                  IP {session.ip_address ?? "—"} · Last used{" "}
                  {formatJoined(session.last_used_at)} · Signed in{" "}
                  {formatJoined(session.created_at)}
                </p>
              </div>
              <button
                type="button"
                disabled={busyId === session.id}
                className="text-sm font-bold text-destructive hover:underline disabled:opacity-50"
                onClick={() => {
                  setBusyId(session.id);
                  setError(null);
                  void identityApi
                    .revokeSession(session.id)
                    .then(() => {
                      if (session.is_current) {
                        success("Signed out", "This device session was ended.");
                        void logout();
                        return;
                      }
                      success(
                        "Session revoked",
                        `${deviceLabel(session.user_agent)} is no longer signed in.`,
                      );
                      reload();
                    })
                    .catch((err) => {
                      const message =
                        err instanceof ApiError
                          ? err.message
                          : "Couldn't revoke session.";
                      setError(message);
                      toastError("Revoke failed", message);
                    })
                    .finally(() => setBusyId(null));
                }}
              >
                <BusyText busy={busyId === session.id}>
                  {session.is_current ? "Sign out" : "Revoke"}
                </BusyText>
              </button>
            </li>
          ))}
        </ul>
      )}
    </IdentityPageShell>
  );
}
