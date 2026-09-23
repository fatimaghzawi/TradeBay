"use client";

import { BusinessStepper } from "@/components/business/BusinessStepper";
import { clearBusinessDraft } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect } from "react";

/** Complete — centered celebration sheet unique to verification success. */
export default function BusinessVerificationCompletePage() {
  useEffect(() => {
    clearBusinessDraft();
  }, []);

  return (
    <div className="relative space-y-5">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-8 mx-auto h-40 max-w-lg rounded-full bg-[#e8f6ef]/80 blur-3xl"
      />
      <div className="relative flex justify-end">
        <BusinessStepper active={3} variant="supplier" />
      </div>

      <div className="relative mx-auto max-w-lg overflow-hidden rounded-[1.75rem] border border-[#e2ebe6] bg-white px-6 py-12 text-center shadow-[0_20px_50px_rgba(21,36,29,0.07)] sm:px-10">
        <svg
          aria-hidden
          className="pointer-events-none absolute -right-8 -top-6 h-32 w-32 text-[#cfe3d6]"
          viewBox="0 0 120 120"
          fill="currentColor"
        >
          <path d="M90 10c-28 16-44 46-36 82 24-10 44-2 64 18-6-42-10-76-28-100Z" />
        </svg>

        <div className="relative mx-auto flex h-28 w-28 items-center justify-center">
          <svg viewBox="0 0 120 120" className="h-full w-full" aria-hidden>
            <rect x="28" y="22" width="48" height="64" rx="6" fill="#0d3b2a" />
            <rect x="36" y="32" width="32" height="5" rx="2" fill="#e8ebe6" />
            <rect x="36" y="42" width="24" height="4" rx="2" fill="#1a6b4f" />
            <circle cx="78" cy="72" r="26" fill="#e8f6ef" />
            <circle cx="78" cy="72" r="20" fill="#1a6b4f" />
            <path
              d="M68 72.5 75 79.5 90 62"
              fill="none"
              stroke="white"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <p className="mt-5 text-[0.7rem] font-bold uppercase tracking-[0.16em] text-[#e86f2a]">
          Company identity
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-instrument)] text-3xl tracking-tight text-[#0c1612]">
          Your company is taking shape
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-[#5a6a62]">
          Documents are with TradeBay for review. Selling stays locked until
          approval — usually within 1–2 business days. Meanwhile you can build
          your team and define access.
        </p>
        <Link
          href={ROUTES.members}
          className="mt-8 inline-flex h-12 w-full items-center justify-center rounded-xl bg-[#e86f2a] text-sm font-bold text-white transition hover:bg-[#d46220]"
        >
          Build your team →
        </Link>
        <Link
          href={ROUTES.businesses}
          className="mt-3 inline-flex text-sm font-semibold text-[#0d3b2a] hover:underline"
        >
          Back to company identity
        </Link>
      </div>
    </div>
  );
}
