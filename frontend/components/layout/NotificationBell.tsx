"use client";

import { notificationsApi, type AppNotification } from "@/lib/api/notificationsApi";
import { bumpLive } from "@/lib/live/bus";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { notificationHref } from "@/lib/notifications/href";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";

function hrefFor(n: AppNotification): string {
  return notificationHref(n);
}

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function NotificationBell() {
  const { hasPermission, isAuthenticated } = useAuth();
  const canRead = isAuthenticated && hasPermission("notifications.read");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [marking, setMarking] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const prevUnread = useRef<number | null>(null);
  const seenIds = useRef<Set<string>>(new Set());
  const primed = useRef(false);

  const refresh = useCallback(() => {
    if (!canRead) return;
    void Promise.all([
      notificationsApi.list({ page_size: 8 }),
      notificationsApi.unreadCount(),
    ])
      .then(([page, count]) => {
        const ids = page.data.map((n) => n.id).filter(Boolean);
        if (!primed.current) {
          seenIds.current = new Set(ids);
          prevUnread.current = count.count;
          primed.current = true;
          setItems(page.data);
          setUnread(count.count);
          return;
        }
        const hasFresh = ids.some((id) => !seenIds.current.has(id));
        for (const id of ids) seenIds.current.add(id);
        if (
          hasFresh ||
          (prevUnread.current != null && count.count > prevUnread.current)
        ) {
          bumpLive({ source: "notification-bell" });
        }
        prevUnread.current = count.count;
        setItems(page.data);
        setUnread(count.count);
      })
      .catch(() => {
        
      });
  }, [canRead]);

  useLivePoll(refresh, {
    intervalMs: 8_000,
    enabled: canRead,
  });

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function onOpen() {
    setOpen((v) => !v);
    if (!open) {
      setLoading(true);
      refresh();
      setLoading(false);
    }
  }

  async function markOne(n: AppNotification) {
    if (n.is_read) return;
    try {
      await notificationsApi.markRead(n.id);
      setItems((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)),
      );
      setUnread((c) => Math.max(0, c - 1));
    } catch {
      
    }
  }

  async function markAll() {
    if (marking) return;
    setMarking(true);
    try {
      await notificationsApi.markAllRead();
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
      setUnread(0);
    } catch {
      
    } finally {
      setMarking(false);
    }
  }

  if (!canRead) return null;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label="Notifications"
        aria-expanded={open}
        onClick={() => void onOpen()}
        className={cn(
          "relative flex h-10 w-10 items-center justify-center rounded-full border border-border-strong bg-muted text-foreground transition",
          open
            ? "border-[var(--tb-secondary)]"
            : "hover:border-[color-mix(in_srgb,var(--tb-secondary)_40%,var(--tb-border))]",
        )}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M6 9.5a6 6 0 1 1 12 0c0 4.2 1.4 5.5 1.4 5.5H4.6S6 13.7 6 9.5Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path
            d="M10 18.5a2 2 0 0 0 4 0"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
        {unread > 0 ? (
          <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-destructive px-1 text-[0.6rem] font-bold text-destructive-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-border-strong bg-popover shadow-[var(--tb-shadow-modal)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-foreground">
              Activity
            </p>
            {unread > 0 ? (
              <button
                type="button"
                className="text-xs font-bold text-link hover:underline disabled:opacity-50"
                disabled={marking}
                aria-busy={marking || undefined}
                onClick={() => void markAll()}
              >
                <BusyText busy={marking}>Mark all read</BusyText>
              </button>
            ) : null}
          </div>

          {loading && items.length === 0 ? (
            <LoadingEntity entity="notifications" className="px-4 py-8 justify-center" />
          ) : items.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-foreground">
                You’re all caught up
              </p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                No notifications yet.
              </p>
            </div>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {items.map((n) => {
                const href = hrefFor(n);
                return (
                  <li key={n.id} className="border-b border-border last:border-0">
                    <Link
                      href={href}
                      className={cn(
                        "block px-4 py-3 transition hover:bg-muted",
                        !n.is_read && "bg-[color-mix(in_srgb,var(--tb-secondary)_6%,transparent)]",
                      )}
                      onClick={() => {
                        void markOne(n);
                        setOpen(false);
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-semibold text-foreground">{n.title}</p>
                        {!n.is_read ? (
                          <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                        ) : null}
                      </div>
                      {n.message ? (
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {n.message}
                        </p>
                      ) : null}
                      <p className="mt-1 text-[0.65rem] text-muted-foreground">
                        {relativeTime(n.created_at)}
                      </p>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="border-t border-border px-4 py-2.5 text-center">
            <Link
              href={ROUTES.notifications}
              className="text-xs font-bold text-link hover:underline"
              onClick={() => setOpen(false)}
            >
              View all notifications
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
