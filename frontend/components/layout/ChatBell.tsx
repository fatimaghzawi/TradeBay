"use client";

import { ChatThreadRow } from "@/components/communication/ChatInbox";
import { communicationApi, type Conversation } from "@/lib/api/communicationApi";
import { ROUTES } from "@/lib/constants";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export function ChatBell() {
  const { hasPermission, isAuthenticated, business } = useAuth();
  const pathname = usePathname();
  const canRead =
    isAuthenticated &&
    business?.type !== "platform" &&
    hasPermission("conversations.read");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Conversation[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(() => {
    if (!canRead) return;
    void Promise.all([
      communicationApi.listConversations({ page_size: 8 }),
      communicationApi.unreadCount(),
    ])
      .then(([page, count]) => {
        const rows = [...page.data].sort(
          (a, b) => (b.unread_count || 0) - (a.unread_count || 0),
        );
        setItems(rows);
        setUnread(count.count);
      })
      .catch(() => {
        
      });
  }, [canRead]);

  useLivePoll(refresh, {
    intervalMs: 5_000,
    enabled: canRead,
  });

  
  useEffect(() => {
    refresh();
  }, [pathname, refresh]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function onOpen() {
    setOpen((v) => !v);
    if (!open) {
      setLoading(true);
      refresh();
      setLoading(false);
    }
  }

  if (!canRead) return null;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={unread > 0 ? `Messages, ${unread} unread` : "Messages"}
        aria-expanded={open}
        title="Messages"
        onClick={onOpen}
        className={cn(
          "relative flex h-10 w-10 items-center justify-center rounded-full border border-border-strong bg-muted text-foreground transition",
          open
            ? "border-[var(--tb-secondary)]"
            : "hover:border-[color-mix(in_srgb,var(--tb-secondary)_40%,var(--tb-border))]",
        )}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M5 6h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H10l-4 3v-3H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinejoin="round"
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
              Messages
            </p>
            {unread > 0 ? (
              <span className="text-xs font-bold text-link">
                {unread} unread
              </span>
            ) : null}
          </div>

          {loading && items.length === 0 ? (
            <LoadingEntity entity="conversations" className="px-4 py-8 justify-center" />
          ) : items.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="font-[family-name:var(--font-outfit)] text-sm font-semibold text-foreground">
                No conversations yet
              </p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                No messages yet.
              </p>
            </div>
          ) : (
            <ul className="max-h-80 overflow-y-auto p-1.5">
              {items.map((c) => (
                <li key={c.id}>
                  <ChatThreadRow conversation={c} onClick={() => setOpen(false)} />
                </li>
              ))}
            </ul>
          )}

          <div className="border-t border-border px-4 py-2.5 text-center">
            <Link
              href={ROUTES.conversations}
              className="text-xs font-bold text-link hover:underline"
              onClick={() => setOpen(false)}
            >
              Open all messages
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
