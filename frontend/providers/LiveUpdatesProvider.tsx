"use client";

import { notificationsApi } from "@/lib/api/notificationsApi";
import { bumpLive } from "@/lib/live/bus";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useRef } from "react";

const POLL_MS = 8_000;

export function LiveUpdatesProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, hasPermission } = useAuth();
  const canRead = isAuthenticated && hasPermission("notifications.read");
  const seenIds = useRef<Set<string>>(new Set());
  const primed = useRef(false);
  const lastUnread = useRef<number | null>(null);

  useEffect(() => {
    if (!canRead) {
      seenIds.current = new Set();
      primed.current = false;
      lastUnread.current = null;
      return;
    }

    let cancelled = false;

    async function pulse() {
      if (cancelled) return;
      if (document.visibilityState === "hidden") return;
      try {
        const [page, count] = await Promise.all([
          notificationsApi.list({ page_size: 12 }),
          notificationsApi.unreadCount(),
        ]);
        if (cancelled) return;

        const ids = page.data.map((n) => n.id).filter(Boolean);
        const unread = count.count;

        if (!primed.current) {
          seenIds.current = new Set(ids);
          lastUnread.current = unread;
          primed.current = true;
          return;
        }

        const fresh = page.data.filter((n) => n.id && !seenIds.current.has(n.id));
        for (const id of ids) seenIds.current.add(id);

        const unreadGrew =
          lastUnread.current != null && unread > lastUnread.current;
        lastUnread.current = unread;

        if (fresh.length || unreadGrew) {
          const newest = fresh[0];
          bumpLive({
            source: "notifications",
            referenceType: newest?.reference_type ?? null,
            referenceId: newest?.reference_id ?? null,
          });
        }
      } catch {
        
      }
    }

    void pulse();
    const id = window.setInterval(() => void pulse(), POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void pulse();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [canRead]);

  return children;
}
