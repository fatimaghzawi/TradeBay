"use client";

import { BusyText } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import {
  communicationApi,
  type Conversation,
  type ConversationMessage,
} from "@/lib/api/communicationApi";
import { dealInitials } from "@/lib/procurement/dealRoom";
import { mediaUrl } from "@/lib/media";
import { bumpLive } from "@/lib/live/bus";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { useAuth } from "@/providers/AuthProvider";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Props = {
  rfqId: string;
  counterpartyId: string;
  counterpartyName?: string | null;
  counterpartyLogoUrl?: string | null;
  myLogoUrl?: string | null;
  subject?: string;
};

const POLL_MS = 2500;

function formatTalkTime(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function RfqThread({
  rfqId,
  counterpartyId,
  counterpartyName,
  counterpartyLogoUrl,
  myLogoUrl,
  subject,
}: Props) {
  const { hasPermission, user, business } = useAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastCreatedRef = useRef<string | null>(null);

  const canRead = hasPermission("conversations.read");
  const canWrite = hasPermission("messages.create");
  const peerName = counterpartyName || "Counterparty";
  const peerLogo = mediaUrl(counterpartyLogoUrl);
  const selfLogo = mediaUrl(myLogoUrl || business?.logo_url);

  const openThread = useCallback(async () => {
    if (!canRead || !counterpartyId) return;
    setOpening(true);
    try {
      const conv = await communicationApi.openConversation({
        counterparty_business_id: counterpartyId,
        type: "RFQ",
        context_type: "rfq",
        context_id: rfqId,
        subject: subject || "Quote request",
      });
      setConversation(conv);
      const page = await communicationApi.listMessages(conv.id, { page_size: 80 });
      setMessages(page.data);
      lastCreatedRef.current = page.data.at(-1)?.created_at ?? null;
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't open this conversation");
    } finally {
      setOpening(false);
    }
  }, [canRead, counterpartyId, rfqId, subject]);

  useEffect(() => {
    void openThread();
  }, [openThread]);

  const pollMessages = useCallback(async () => {
    if (!conversation?.id) return;
    try {
      const page = await communicationApi.listMessages(conversation.id, {
        page_size: 40,
        after: lastCreatedRef.current || undefined,
      });
      if (!page.data.length) return;
      setMessages((prev) => {
        const seen = new Set(prev.map((m) => m.id));
        const next = page.data.filter((m) => !seen.has(m.id));
        return next.length ? [...prev, ...next] : prev;
      });
      lastCreatedRef.current = page.data.at(-1)?.created_at ?? lastCreatedRef.current;
    } catch {
      
    }
  }, [conversation?.id]);

  useLivePoll(pollMessages, {
    intervalMs: POLL_MS,
    enabled: Boolean(conversation?.id),
    immediate: false,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || busy || !conversation || !canWrite) return;
    setBusy(true);
    setError(null);
    try {
      const msg = await communicationApi.sendMessage(conversation.id, { body });
      setMessages((prev) => [...prev, msg]);
      lastCreatedRef.current = msg.created_at;
      setDraft("");
      bumpLive({
        source: "rfq-thread-send",
        referenceType: "conversation",
        referenceId: conversation.id,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) return null;

  const mine = (m: ConversationMessage) => Boolean(user?.id && m.sender_user_id === user.id);

  return (
    <section className="tb-deal-talk">
      <div className="tb-deal-talk__glow" aria-hidden />
      <header className="tb-deal-talk__head">
        <div className="tb-deal-talk__pair" aria-hidden>
          <span className="tb-deal-talk__avatar" data-side="me">
            {selfLogo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={selfLogo} alt="" />
            ) : (
              dealInitials(business?.name || "You")
            )}
          </span>
          <span className="tb-deal-talk__link" />
          <span className="tb-deal-talk__avatar" data-side="peer">
            {peerLogo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={peerLogo} alt="" />
            ) : (
              dealInitials(peerName)
            )}
          </span>
        </div>
        <div className="tb-deal-talk__meta">
          <p className="tb-deal-kicker">Beside the table</p>
          <h2>{peerName}</h2>
          <p>
            Quiet channel for timing, packing, and nuance — numbers still move on The table.
          </p>
        </div>
        <span className="tb-deal-talk__live">
          <i />
          Live
        </span>
      </header>

      {error ? <p className="tb-deal-talk__error">{error}</p> : null}

      <div className="tb-deal-talk__log">
        {opening && !conversation ? (
          <div className="tb-deal-talk__empty">
            <span className="tb-deal-talk__empty-mark" aria-hidden />
            <p>Opening the conversation…</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="tb-deal-talk__empty">
            <div className="tb-deal-talk__empty-orbit" aria-hidden>
              <span />
              <span />
              <span />
            </div>
            <strong>Start the aside</strong>
            <p>
              Align on lead time, packing, or a number you are not ready to put in writing. The
              quotation stays the commercial record.
            </p>
          </div>
        ) : (
          messages.map((m, idx) =>
            m.message_type === "SYSTEM" ? (
              <p
                key={m.id}
                className="tb-deal-system"
                style={{ ["--msg-i" as string]: idx }}
              >
                {m.body || m.system_event}
              </p>
            ) : (
              <article
                key={m.id}
                className="tb-deal-talk__row"
                data-mine={mine(m) || undefined}
                style={{ ["--msg-i" as string]: idx }}
              >
                <span className="tb-deal-talk__avatar" data-size="sm" aria-hidden>
                  {mine(m) ? (
                    selfLogo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={selfLogo} alt="" />
                    ) : (
                      dealInitials(business?.name || "You")
                    )
                  ) : peerLogo ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={peerLogo} alt="" />
                  ) : (
                    dealInitials(peerName)
                  )}
                </span>
                <div className="tb-deal-bubble" data-mine={mine(m) || undefined}>
                  <p className="whitespace-pre-wrap">
                    {m.is_deleted ? "Message removed" : m.body}
                  </p>
                  <time dateTime={m.created_at || undefined}>
                    {formatTalkTime(m.created_at)}
                  </time>
                </div>
              </article>
            ),
          )
        )}
        <div ref={bottomRef} />
      </div>

      {canWrite && conversation?.status !== "CLOSED" ? (
        <form onSubmit={(e) => void onSend(e)} className="tb-deal-talk__composer">
          <label className="tb-deal-talk__field">
            <span className="sr-only">Message</span>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={`Say something to ${peerName}…`}
              maxLength={8000}
              disabled={busy}
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
            />
          </label>
          <button
            type="submit"
            className="tb-btn tb-btn--primary tb-deal-talk__send"
            disabled={busy || !draft.trim()}
          >
            <BusyText busy={busy}>Send across</BusyText>
          </button>
        </form>
      ) : null}
    </section>
  );
}
