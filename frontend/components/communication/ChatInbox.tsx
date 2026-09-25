"use client";

import type { Conversation } from "@/lib/api/communicationApi";
import {
  chatContextHref,
  chatContextLabel,
  chatRelativeTime,
  chatTitle,
} from "@/lib/communication/chatUi";
import { dealInitials } from "@/lib/procurement/dealRoom";
import { mediaUrl } from "@/lib/media";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import type { ReactNode } from "react";

export function ChatAvatar({
  name,
  logoUrl,
  unread,
  size = "md",
}: {
  name: string;
  logoUrl?: string | null;
  unread?: boolean;
  size?: "sm" | "md";
}) {
  const src = mediaUrl(logoUrl);
  return (
    <span className="tb-chat-avatar" data-size={size} data-unread={unread || undefined} aria-hidden>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" />
      ) : (
        dealInitials(name)
      )}
    </span>
  );
}

export function ChatThreadRow({
  conversation: c,
  active,
  onClick,
}: {
  conversation: Conversation;
  active?: boolean;
  onClick?: () => void;
}) {
  const name = chatTitle(c);
  const unread = c.unread_count || 0;
  return (
    <Link
      href={ROUTES.conversation(c.id)}
      className="tb-chat-row"
      data-active={active || undefined}
      data-unread={unread > 0 || undefined}
      onClick={onClick}
    >
      <ChatAvatar name={name} logoUrl={c.counterparty_logo_url} unread={unread > 0} />
      <span className="tb-chat-row__body">
        <span className="tb-chat-row__top">
          <strong>{name}</strong>
          <time>{chatRelativeTime(c.last_message_at || c.created_at)}</time>
        </span>
        <span className="tb-chat-row__mid">
          <em>{chatContextLabel(c)}</em>
          {c.subject && c.counterparty_name ? <span>{c.subject}</span> : null}
        </span>
        <span className="tb-chat-row__preview">
          {c.last_message_preview || "No messages yet — say hello"}
        </span>
      </span>
      {unread > 0 ? (
        <span className="tb-chat-row__badge">{unread > 9 ? "9+" : unread}</span>
      ) : null}
    </Link>
  );
}

export function ChatEmptyStage() {
  return (
    <div className="tb-chat-empty">
      <div className="tb-chat-empty__orbit" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <h2>Pick a conversation</h2>
      <p>Select a thread to read and reply.</p>
      <Link href={ROUTES.procurement} className="tb-btn tb-btn--secondary">
        Open procurement
      </Link>
    </div>
  );
}

export function ChatDealChip({ conversation: c }: { conversation: Conversation }) {
  const href = chatContextHref(c);
  const label = chatContextLabel(c);
  if (!href) {
    return <span className="tb-chat-chip">{label}</span>;
  }
  return (
    <Link href={href} className="tb-chat-chip" data-link="true">
      {label} · open deal
    </Link>
  );
}

export function ChatComposer({
  children,
  hint,
}: {
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="tb-chat-composer">
      {children}
      {hint ? <p className="tb-chat-composer__hint">{hint}</p> : null}
    </div>
  );
}

export function ChatSkeletonRows() {
  return (
    <div className="tb-chat-skel">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="tb-chat-skel__row" />
      ))}
    </div>
  );
}

export function filterThreads(rows: Conversation[], query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((c) => {
    const hay = `${chatTitle(c)} ${c.subject || ""} ${c.last_message_preview || ""} ${chatContextLabel(c)}`.toLowerCase();
    return hay.includes(q);
  });
}
