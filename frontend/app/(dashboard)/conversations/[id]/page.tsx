"use client";

import { ChatAvatar, ChatDealChip } from "@/components/communication/ChatInbox";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { BusyText, LoadingEntity } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import {
  communicationApi,
  type Conversation,
  type ConversationMessage,
} from "@/lib/api/communicationApi";
import { chatClock, chatTitle } from "@/lib/communication/chatUi";
import { ROUTES } from "@/lib/constants";
import { bumpLive } from "@/lib/live/bus";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

export default function ConversationThreadPage() {
  const params = useParams<{ id: string | string[] }>();
  const rawId = Array.isArray(params.id) ? params.id[0] : params.id;
  const conversationId = rawId ?? "";
  const { hasPermission, user, business } = useAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<ConversationMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastCreatedRef = useRef<string | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  const loadedRef = useRef(false);

  const reload = useCallback(async () => {
    if (!hasPermission("conversations.read") || !conversationId) return;
    try {
      const [conv, page] = await Promise.all([
        communicationApi.getConversation(conversationId),
        communicationApi.listMessages(conversationId, { page_size: 100 }),
      ]);
      setConversation(conv);
      setMessages(page.data);
      lastCreatedRef.current = page.data.at(-1)?.created_at ?? null;
      loadedRef.current = true;
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this conversation");
    } finally {
      setLoading(false);
    }
  }, [conversationId, hasPermission]);

  useEffect(() => {
    loadedRef.current = false;
    lastCreatedRef.current = null;
    setMessages([]);
    setConversation(null);
    setLoading(true);
    void reload();
  }, [reload]);

  const pollMessages = useCallback(async () => {
    if (!conversationId || !hasPermission("conversations.read")) return;
    if (!loadedRef.current) return;
    try {
      const page = await communicationApi.listMessages(conversationId, {
        page_size: 100,
        after: lastCreatedRef.current || undefined,
      });
      if (!page.data.length) return;
      setMessages((prev) => {
        const seen = new Set(prev.map((m) => m.id));
        const next = page.data.filter((m) => m.id && !seen.has(m.id));
        if (!next.length) return prev;
        return lastCreatedRef.current ? [...prev, ...next] : page.data;
      });
      lastCreatedRef.current = page.data.at(-1)?.created_at ?? lastCreatedRef.current;
    } catch {
      /* keep the last good thread */
    }
  }, [conversationId, hasPermission]);

  useLivePoll(pollMessages, {
    intervalMs: 2_000,
    enabled: Boolean(conversationId) && hasPermission("conversations.read"),
    immediate: false,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function onSend(e?: FormEvent) {
    e?.preventDefault();
    const body = draft.trim();
    if (!body || busy || !hasPermission("messages.create")) return;
    setBusy(true);
    setError(null);
    try {
      const msg = await communicationApi.sendMessage(conversationId, {
        body,
        reply_to_message_id: replyTo?.id,
      });
      setMessages((prev) => [...prev, msg]);
      lastCreatedRef.current = msg.created_at;
      setDraft("");
      setReplyTo(null);
      bumpLive({ source: "chat-send", referenceType: "conversation", referenceId: conversationId });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  if (!conversationId) {
    return (
      <div className="tb-chat-empty">
        <h2>Conversation not found</h2>
        <p>Missing conversation id.</p>
      </div>
    );
  }

  if (!hasPermission("conversations.read")) {
    return (
      <div className="tb-chat-empty">
        <h2>Access restricted</h2>
        <p>
          You don&apos;t have access to messages. Contact your business administrator if
          you need access.
        </p>
      </div>
    );
  }

  const mine = (m: ConversationMessage) => Boolean(user?.id && m.sender_user_id === user.id);
  const byId = Object.fromEntries(messages.map((m) => [m.id, m]));
  const title = conversation ? chatTitle(conversation) : "Conversation";
  const status = (conversation?.status || "").toUpperCase();
  const canWrite = hasPermission("messages.create") && status === "ACTIVE";
  const peerLogo = conversation?.counterparty_logo_url;
  const myLogo = business?.logo_url;

  return (
    <div className="tb-chat-room">
      <header className="tb-chat-room__head">
        <Link href={ROUTES.conversations} className="tb-chat-back" aria-label="Back to inbox">
          ←
        </Link>
        <div className="tb-chat-room__pair" aria-hidden>
          <ChatAvatar name={business?.name || "You"} logoUrl={myLogo} size="sm" />
          <span className="tb-chat-room__link" />
          <ChatAvatar name={title} logoUrl={peerLogo} />
        </div>
        <div className="tb-chat-room__who">
          <strong>{title}</strong>
          <span>{conversation?.subject || "Company-to-company chat"}</span>
        </div>
        {conversation ? <ChatDealChip conversation={conversation} /> : null}
        <span className="tb-chat-room__live">
          <i />
          Live
        </span>
      </header>

      {error ? (
        <div className="tb-chat-banner">
          <FeedbackBanner tone="error" title="Chat">
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      <div className="tb-chat-log" ref={logRef}>
        {loading && !conversation ? (
          <LoadingEntity entity="conversation" className="py-16 justify-center" />
        ) : messages.length === 0 ? (
          <div className="tb-chat-log__empty">
            <div className="tb-chat-empty__orbit" aria-hidden>
              <span />
              <span />
              <span />
            </div>
            <p>No messages yet</p>
            <span>Say hello to start the conversation.</span>
          </div>
        ) : (
          messages.map((m, idx) => {
            if (m.message_type === "SYSTEM") {
              return (
                <p
                  key={m.id}
                  className="tb-chat-system"
                  style={{ ["--msg-i" as string]: idx }}
                >
                  {m.body || m.system_event}
                  {m.created_at ? ` · ${chatClock(m.created_at)}` : ""}
                </p>
              );
            }
            const isMine = mine(m);
            const parent = m.reply_to_message_id ? byId[m.reply_to_message_id] : null;
            return (
              <article
                key={m.id}
                className="tb-chat-msg"
                data-mine={isMine || undefined}
                style={{ ["--msg-i" as string]: idx }}
              >
                <ChatAvatar
                  name={isMine ? business?.name || "You" : title}
                  logoUrl={isMine ? myLogo : peerLogo}
                  size="sm"
                />
                <div className="tb-chat-bubble" data-mine={isMine || undefined}>
                  {parent ? (
                    <p className="tb-chat-bubble__quote">
                      {(parent.body || "Message").slice(0, 80)}
                    </p>
                  ) : null}
                  {m.message_type === "REFERENCE" ? (
                    <p>
                      Shared {m.reference_type}
                      {m.body ? ` — ${m.body}` : ""}
                    </p>
                  ) : m.is_deleted ? (
                    <p className="tb-chat-bubble__gone">Message removed</p>
                  ) : (
                    <p className="whitespace-pre-wrap">{m.body}</p>
                  )}
                  <footer>
                    <time>{chatClock(m.created_at)}</time>
                    {m.edited_at ? <span>edited</span> : null}
                    {!m.is_deleted && m.message_type === "TEXT" ? (
                      <button type="button" onClick={() => setReplyTo(m)}>
                        Reply
                      </button>
                    ) : null}
                    {isMine && !m.is_deleted && m.message_type !== "SYSTEM" ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void (async () => {
                            setBusy(true);
                            try {
                              await communicationApi.deleteMessage(conversationId, m.id);
                              setMessages((prev) =>
                                prev.map((row) =>
                                  row.id === m.id
                                    ? { ...row, is_deleted: true, body: null }
                                    : row,
                                ),
                              );
                            } catch (err) {
                              setError(
                                err instanceof ApiError ? err.message : "Delete failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          })()
                        }
                      >
                        Remove
                      </button>
                    ) : null}
                  </footer>
                </div>
              </article>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      {canWrite ? (
        <form onSubmit={(e) => void onSend(e)} className="tb-chat-composer">
          {replyTo ? (
            <div className="tb-chat-reply">
              <span>Replying to {(replyTo.body || "message").slice(0, 72)}</span>
              <button type="button" onClick={() => setReplyTo(null)}>
                Cancel
              </button>
            </div>
          ) : null}
          <div className="tb-chat-composer__row">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={`Message ${title}…`}
              maxLength={8000}
              disabled={busy}
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void onSend();
                }
              }}
            />
            <button
              type="submit"
              className="tb-chat-send"
              disabled={busy || !draft.trim()}
              aria-label="Send"
            >
              <BusyText busy={busy}>Send across</BusyText>
            </button>
          </div>
        </form>
      ) : conversation ? (
        <p className="tb-chat-closed">
          {status !== "ACTIVE"
            ? "This conversation is closed."
            : "Messaging is read-only for your role."}
        </p>
      ) : null}
    </div>
  );
}
