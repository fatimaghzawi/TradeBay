"use client";

import Link from "next/link";
import { ROUTES } from "@/lib/constants";
import { type CSSProperties, useEffect, useState } from "react";

const CONFETTI = [
  { left: "8%", delay: "0s", color: "#e86f2a", rot: 12, size: 10, x: 24 },
  { left: "18%", delay: "0.08s", color: "#0d3b2a", rot: -18, size: 8, x: -28 },
  { left: "28%", delay: "0.14s", color: "#c9a57a", rot: 28, size: 9, x: 36 },
  { left: "38%", delay: "0.05s", color: "#e86f2a", rot: -8, size: 7, x: -18 },
  { left: "48%", delay: "0.18s", color: "#1a6b4f", rot: 22, size: 10, x: 22 },
  { left: "58%", delay: "0.1s", color: "#c45b2a", rot: -24, size: 8, x: -32 },
  { left: "68%", delay: "0.22s", color: "#e86f2a", rot: 14, size: 9, x: 40 },
  { left: "78%", delay: "0.06s", color: "#0d3b2a", rot: -16, size: 7, x: -20 },
  { left: "88%", delay: "0.16s", color: "#c9a57a", rot: 30, size: 8, x: 28 },
  { left: "12%", delay: "0.28s", color: "#f0a05a", rot: -10, size: 6, x: -36 },
  { left: "72%", delay: "0.32s", color: "#2a8f6a", rot: 18, size: 6, x: 16 },
  { left: "42%", delay: "0.26s", color: "#e86f2a", rot: -22, size: 11, x: -24 },
];

export function VerificationSuccess({
  email,
}: {
  email?: string | null;
}) {
  const [burst, setBurst] = useState(false);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setBurst(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  return (
    <div className="verify-success relative mx-auto flex w-full max-w-sm flex-col items-center text-center">
      {}
      <div
        className="pointer-events-none absolute inset-x-[-20%] top-0 h-56 overflow-visible"
        aria-hidden
      >
        {CONFETTI.map((piece, i) => (
          <span
            key={i}
            className={`verify-confetti absolute top-8 rounded-sm ${burst ? "is-burst" : ""}`}
            style={
              {
                left: piece.left,
                width: piece.size,
                height: piece.size * 1.4,
                backgroundColor: piece.color,
                "--rot": `${piece.rot}deg`,
                "--delay": piece.delay,
                "--x": `${piece.x}px`,
              } as CSSProperties
            }
          />
        ))}
      </div>

      <div className={`verify-hero relative ${burst ? "is-in" : ""}`}>
        <CelebrationMark />
      </div>

      <h1
        className={`auth-display mt-6 text-[1.95rem] sm:text-[2.25rem] ${burst ? "verify-copy-in" : "opacity-0"}`}
      >
        Email verified!
      </h1>
      <p
        className={`auth-lede mt-3 max-w-[20rem] ${burst ? "verify-copy-in verify-copy-delay" : "opacity-0"}`}
      >
        Your email has been successfully verified. You can now sign in to your
        account.
        {email ? (
          <span className="mt-1 block text-xs text-subtle-foreground">{email}</span>
        ) : null}
      </p>

      <Link
        href={ROUTES.login}
        className={`mt-8 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-accent text-sm font-semibold text-white transition hover:bg-accent/90 ${burst ? "verify-copy-in verify-copy-delay-2" : "opacity-0"}`}
      >
        Continue to sign in
        <span aria-hidden>→</span>
      </Link>
    </div>
  );
}

function CelebrationMark() {
  return (
    <div className="relative flex h-[11.5rem] w-[11.5rem] items-center justify-center" aria-hidden>
      {}
      <span className="verify-glow absolute inset-[18%] rounded-full bg-accent/15 blur-2xl" />

      {}
      <svg
        className="verify-petals absolute inset-0 h-full w-full"
        viewBox="0 0 184 184"
        fill="none"
      >
        <path
          d="M92 28c-10 18-8 36 4 52 8-14 20-24 36-28-14-8-24-16-40-24Z"
          fill="#e8c4a8"
        />
        <path
          d="M108 46c-8 16-4 34 10 50 6-14 16-24 30-28-12-6-22-12-40-22Z"
          fill="#e86f2a"
          opacity="0.85"
        />
        <path
          d="M72 52c-10 16-8 34 4 50 4-14 14-24 26-28-10-6-18-12-30-22Z"
          fill="#d4a574"
          opacity="0.9"
        />
        <path
          d="M118 58c-6 14-2 30 12 44 6-12 14-20 26-24-10-6-20-10-38-20Z"
          fill="#c45b2a"
          opacity="0.7"
        />
        <path
          d="M64 70c-8 14-6 30 4 44 4-12 12-20 22-24-8-6-16-10-26-20Z"
          fill="#e8c4a8"
          opacity="0.75"
        />
      </svg>

      {}
      <svg
        className="verify-sparks absolute left-1/2 top-2 h-16 w-28 -translate-x-1/2"
        viewBox="0 0 112 64"
        fill="none"
      >
        <path d="M56 4v18" stroke="#e86f2a" strokeWidth="3" strokeLinecap="round" className="verify-ray" />
        <path d="M34 12 44 24" stroke="#e86f2a" strokeWidth="3" strokeLinecap="round" className="verify-ray verify-ray-2" />
        <path d="M78 12 68 24" stroke="#e86f2a" strokeWidth="3" strokeLinecap="round" className="verify-ray verify-ray-3" />
        <path d="M18 24 34 30" stroke="#c45b2a" strokeWidth="2.5" strokeLinecap="round" className="verify-ray verify-ray-4" />
        <path d="M94 24 78 30" stroke="#c45b2a" strokeWidth="2.5" strokeLinecap="round" className="verify-ray verify-ray-5" />
      </svg>

      {}
      <svg
        className="verify-envelope relative z-[1] h-[5.75rem] w-[6.75rem] drop-shadow-[0_14px_28px_rgba(13,59,42,0.18)]"
        viewBox="0 0 108 90"
        fill="none"
      >
        <rect
          x="6"
          y="28"
          width="96"
          height="56"
          rx="6"
          fill="#ffffff"
          stroke="#1c2b24"
          strokeWidth="2.2"
        />
        <path
          d="M8 30 54 58 100 30"
          stroke="#1c2b24"
          strokeWidth="2.2"
          strokeLinejoin="round"
          fill="none"
        />
        <path
          d="M8 82 40 52M100 82 68 52"
          stroke="#1c2b24"
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.35"
        />
      </svg>

      {}
      <span className="verify-badge absolute left-1/2 top-[48%] z-[2] flex h-[3.6rem] w-[3.6rem] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_10px_24px_-6px_rgba(13,59,42,0.55)] ring-[5px] ring-border">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <path
            d="M5 12.5 9.5 17 19 7.5"
            className="verify-check"
            stroke="currentColor"
            strokeWidth="2.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </div>
  );
}
