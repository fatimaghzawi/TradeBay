"use client";

import {
  InventoryEmpty,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
} from "@/components/catalog/InventoryUi";
import { BackLink } from "@/components/ui/BackLink";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { notificationsApi, type AppNotification } from "@/lib/api/notificationsApi";
import { notificationHref } from "@/lib/notifications/href";
import { ROUTES } from "@/lib/constants";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useState } from "react";

function linkFor(n: AppNotification): string {
  return notificationHref(n);
}

export default function NotificationsPage() {
  const { hasPermission } = useAuth();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const reload = useCallback(
    async (opts?: { soft?: boolean }) => {
      if (!hasPermission("notifications.read")) {
        setLoading(false);
        return;
      }
      if (!opts?.soft) setLoading(true);
      try {
        const page = await notificationsApi.list({
          page_size: 50,
          unread_only: unreadOnly,
        });
        setItems(page.data);
        setError(null);
      } catch (err) {
        if (!opts?.soft) {
          setError(err instanceof ApiError ? err.message : "Couldn't load notifications");
        }
      } finally {
        setLoading(false);
      }
    },
    [hasPermission, unreadOnly],
  );

  useLivePoll(() => reload({ soft: true }), {
    intervalMs: 6_000,
    enabled: hasPermission("notifications.read"),
  });

  async function markAll() {
    await notificationsApi.markAllRead();
    reload();
  }

  async function markOne(id: string) {
    await notificationsApi.markRead(id);
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
  }

  if (!hasPermission("notifications.read")) {
    return (
      <div className="tb-inv-page">
        <InventoryPageHeader
          title="Notifications"
          description="You don't have access to notifications. Contact your business administrator if you need access."
        />
      </div>
    );
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="Notifications"
        description={undefined}
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="tb-btn tb-btn--outline"
              onClick={() => setUnreadOnly((v) => !v)}
            >
              {unreadOnly ? "Show all" : "Unread only"}
            </button>
            <button type="button" className="tb-btn tb-btn--secondary" onClick={() => void markAll()}>
              Mark all read
            </button>
          </div>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load">
          {error}
        </FeedbackBanner>
      ) : null}

      <InventoryPanel title="Activity feed" subtitle="Newest first">
        {loading ? (
          <InventorySkeleton entity="notifications" />
        ) : items.length === 0 ? (
          <InventoryEmpty
            mark="◎"
            title={unreadOnly ? "You're all caught up" : "No notifications yet"}
            body={
              unreadOnly
                ? "You're all caught up."
                : "Nothing here yet."
            }
            action={
              <BackLink href={ROUTES.dashboard}>Back to dashboard</BackLink>
            }
          />
        ) : (
          <ul className="tb-inv-entity-list px-5 pb-4">
            {items.map((n) => (
              <li key={n.id} className="tb-inv-entity-row">
                <Link
                  href={linkFor(n)}
                  className="min-w-0 flex-1"
                  onClick={() => {
                    if (!n.is_read) void markOne(n.id);
                  }}
                >
                  <strong className={!n.is_read ? "text-heading" : undefined}>{n.title}</strong>
                  {n.message ? <span className="tb-inv-entity-sub">{n.message}</span> : null}
                  <span className="tb-inv-entity-sub">
                    {n.created_at
                      ? new Date(n.created_at).toLocaleString()
                      : ""}
                    {!n.is_read ? (n.created_at ? " · unread" : "Unread") : ""}
                  </span>
                </Link>
                {!n.is_read ? (
                  <button
                    type="button"
                    className="text-xs font-bold text-link hover:underline"
                    onClick={() => void markOne(n.id)}
                  >
                    Mark read
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </InventoryPanel>
    </div>
  );
}
