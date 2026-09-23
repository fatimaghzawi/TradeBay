"use client";

import {
  ChatSkeletonRows,
  ChatThreadRow,
  filterThreads,
} from "@/components/communication/ChatInbox";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { communicationApi, type Conversation } from "@/lib/api/communicationApi";
import { chatActiveId } from "@/lib/communication/chatUi";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { useAuth } from "@/providers/AuthProvider";
import { usePathname } from "next/navigation";
import { useCallback, useMemo, useState, type ReactNode } from "react";

export default function ConversationsLayout({ children }: { children: ReactNode }) {
  const { hasPermission } = useAuth();
  const pathname = usePathname();
  const activeId = chatActiveId(pathname);
  const [items, setItems] = useState<Conversation[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!hasPermission("conversations.read")) {
      setLoading(false);
      return;
    }
    void communicationApi
      .listConversations({ page_size: 80 })
      .then((page) => {
        setItems(page.data);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load conversations");
      })
      .finally(() => setLoading(false));
  }, [hasPermission]);

  useLivePoll(reload, {
    intervalMs: 5_000,
    enabled: hasPermission("conversations.read"),
  });

  const unreadTotal = items.reduce((n, c) => n + (c.unread_count || 0), 0);
  const visible = useMemo(() => filterThreads(items, query), [items, query]);

  if (!hasPermission("conversations.read")) {
    return <div className="tb-inv-page">{children}</div>;
  }

  return (
    <div className="tb-chat" data-pane={activeId ? "thread" : "list"}>
      <aside className="tb-chat-rail">
        <header className="tb-chat-rail__head">
          <p className="tb-deal-kicker">Desk phone</p>
          <h1>Messages</h1>
          <p>
            {items.length} {items.length === 1 ? "line open" : "lines open"}
            {unreadTotal > 0 ? ` · ${unreadTotal} ringing` : " · quiet for now"}
          </p>
          <label className="tb-chat-search">
            <span className="sr-only">Search conversations</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a company or last line…"
            />
          </label>
        </header>
        {error ? (
          <div className="px-3 pb-2">
            <FeedbackBanner tone="error" title="Inbox">
              {error}
            </FeedbackBanner>
          </div>
        ) : null}
        <div className="tb-chat-rail__list">
          {loading && items.length === 0 ? (
            <ChatSkeletonRows />
          ) : visible.length === 0 ? (
            <p className="tb-chat-rail__empty">
              {query
                ? "Nothing matches that search."
                : "No threads yet."}
            </p>
          ) : (
            visible.map((c) => (
              <ChatThreadRow key={c.id} conversation={c} active={c.id === activeId} />
            ))
          )}
        </div>
      </aside>
      <section className="tb-chat-stage">{children}</section>
    </div>
  );
}
