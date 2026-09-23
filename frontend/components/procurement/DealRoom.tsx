"use client";

import { mediaUrl } from "@/lib/media";
import { dealBeat, dealInitials, type DealBeat } from "@/lib/procurement/dealRoom";
import { statusLabel } from "@/lib/procurement/rfqLifecycle";
import Link from "next/link";
import type { ReactNode } from "react";

export function ProductThumb({
  name,
  imageUrl,
}: {
  name: string;
  imageUrl?: string | null;
}) {
  const src = mediaUrl(imageUrl);
  return (
    <span className="tb-rfq-item__thumb" aria-hidden>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" />
      ) : (
        <span>{dealInitials(name)}</span>
      )}
    </span>
  );
}

export function DealSeat({
  name,
  role,
  you,
  logoUrl,
  href,
}: {
  name: string;
  role: string;
  you?: boolean;
  logoUrl?: string | null;
  href?: string | null;
}) {
  const src = mediaUrl(logoUrl);
  const body = (
    <>
      <span className="tb-deal-seat__mark" aria-hidden>
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" />
        ) : (
          dealInitials(name)
        )}
      </span>
      <span className="tb-deal-seat__copy">
        <em>{you ? "You · " + role : role}</em>
        <strong>{name}</strong>
      </span>
      {you ? <span className="tb-deal-seat__pulse" aria-hidden /> : null}
    </>
  );
  if (href) {
    return (
      <Link href={href} className="tb-deal-seat" data-you={you || undefined} data-role={role.toLowerCase()}>
        {body}
      </Link>
    );
  }
  return (
    <div className="tb-deal-seat" data-you={you || undefined} data-role={role.toLowerCase()}>
      {body}
    </div>
  );
}

export function DealMoveWho({
  side,
  name,
  you,
  logoUrl,
}: {
  side: "buyer" | "supplier";
  name: string;
  you?: boolean;
  logoUrl?: string | null;
}) {
  const role = side === "supplier" ? "Supplier" : "Buyer";
  const src = mediaUrl(logoUrl);
  return (
    <div className="tb-deal-who" data-side={side} data-you={you || undefined}>
      <span className="tb-deal-who__mark" aria-hidden>
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" />
        ) : (
          dealInitials(name)
        )}
      </span>
      <span className="tb-deal-who__copy">
        <strong>{you ? "You" : name}</strong>
        {you ? <span className="tb-deal-who__name">{name}</span> : null}
      </span>
      <span className="tb-deal-who__badge">{role}</span>
    </div>
  );
}

const BEATS: { id: DealBeat; label: string; hint: string }[] = [
  { id: "brief", label: "Request", hint: "Brief on the table" },
  { id: "quote", label: "Quotation", hint: "Offer is in" },
  { id: "table", label: "Bargain", hint: "Numbers moving" },
  { id: "close", label: "Handshake", hint: "Deal sealed" },
];

export function DealStageRail({
  status,
  hasQuote,
  negotiating,
}: {
  status: string;
  hasQuote: boolean;
  negotiating: boolean;
}) {
  const beat = dealBeat(status, hasQuote, negotiating);
  const order: DealBeat[] = ["brief", "quote", "table", "close"];
  const active = order.indexOf(beat);
  return (
    <ol className="tb-deal-rail" aria-label="Deal progress">
      {BEATS.map((step, idx) => (
        <li
          key={step.id}
          data-state={idx < active ? "done" : idx === active ? "now" : "next"}
          style={{ ["--deal-step" as string]: idx }}
        >
          <i className="tb-deal-rail__dot" aria-hidden />
          <span>{step.label}</span>
          {idx === active ? <em>{step.hint}</em> : null}
        </li>
      ))}
    </ol>
  );
}

export function DealHero({
  number,
  title,
  status,
  hasQuote,
  negotiating,
  left,
  right,
  actions,
}: {
  number: string;
  title: string;
  status: string;
  hasQuote: boolean;
  negotiating: boolean;
  left: ReactNode;
  right: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="tb-deal-hero">
      <div className="tb-deal-hero__glow" aria-hidden />
      <div className="tb-deal-hero__top">
        <p className="tb-deal-stamp">{number}</p>
        <p className="tb-deal-status">{statusLabel(status)}</p>
        {actions ? <div className="tb-deal-hero__actions">{actions}</div> : null}
      </div>
      <h1 className="tb-deal-title">{title}</h1>
      <DealStageRail status={status} hasQuote={hasQuote} negotiating={negotiating} />
      <div className="tb-deal-table" aria-label="Parties at the table">
        <div className="tb-deal-table__felt" aria-hidden />
        <div className="tb-deal-table__edge" aria-hidden />
        <div className="tb-deal-table__row">
          {left}
          <div className="tb-deal-cloth" aria-hidden>
            <span className="tb-deal-cloth__ring" />
            <span className="tb-deal-cloth__label">Deal table</span>
          </div>
          {right}
        </div>
      </div>
    </header>
  );
}
