"use client";

import { useEffect } from "react";

type Props = {
  buyerName: string;
  supplierName: string;
  headline?: string;
  detail?: string;
  onDone: () => void;
  durationMs?: number;
};

export function DealHandshake({
  buyerName,
  supplierName,
  headline = "Handshake",
  detail = "The number is locked. Opening the deal…",
  onDone,
  durationMs = 2600,
}: Props) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, durationMs);
    return () => window.clearTimeout(timer);
  }, [onDone, durationMs]);

  return (
    <div className="tb-handshake" role="dialog" aria-modal="true" aria-label={headline}>
      <div className="tb-handshake__bloom" aria-hidden />
      <div className="tb-handshake__card">
        <p className="tb-handshake__kicker">Deal sealed</p>
        <div className="tb-handshake__clasp" aria-hidden>
          <span className="tb-handshake__hand" data-side="buyer">
            {buyerName.slice(0, 1).toUpperCase()}
          </span>
          <span className="tb-handshake__spark">✦</span>
          <span className="tb-handshake__hand" data-side="supplier">
            {supplierName.slice(0, 1).toUpperCase()}
          </span>
        </div>
        <h2 className="tb-handshake__title">{headline}</h2>
        <p className="tb-handshake__detail">{detail}</p>
        <div className="tb-handshake__names">
          <span>{buyerName}</span>
          <em>×</em>
          <span>{supplierName}</span>
        </div>
      </div>
    </div>
  );
}
