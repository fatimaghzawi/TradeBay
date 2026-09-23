"use client";

import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";

export function DashboardImpact() {
  const { business } = useAuth();
  if (business?.type === "supplier") return null;

  return (
    <section className="tb-desk-impact" aria-labelledby="tb-desk-impact-title">
      <div className="tb-desk-impact__media" aria-hidden>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/images/landing/hero-scene.jpg" alt="" />
      </div>
      <div className="tb-desk-impact__veil" aria-hidden />
      <p className="tb-desk-impact__pill">Local Impact</p>
      <h2 id="tb-desk-impact-title" className="tb-desk-impact__title">
        Stronger Businesses, A Brighter Lebanon
      </h2>
      <Link href={ROUTES.suppliersDirectory} className="tb-desk-impact__cta">
        Explore Opportunities
        <span aria-hidden>→</span>
      </Link>
    </section>
  );
}

export function DashboardBanner() {
  return (
    <aside className="tb-desk-banner" aria-label="TradeBay mission">
      <p className="tb-desk-banner__left">
        <span className="tb-desk-banner__leaf" aria-hidden>
          ❦
        </span>
        Source locally. Grow globally.
      </p>
      <span className="tb-desk-banner__cedar" aria-hidden title="Cedar of Lebanon">
        <svg viewBox="0 0 24 28" width="22" height="26">
          <path
            d="M12 2c1.2 2.4 2 4.2 2 6.2 0 1.2-.3 2.2-.8 3.1 1.8-.4 3.3-1 4.5-1.8-1.2 2.4-3.1 4-5.3 5 1.5.2 2.8.8 3.8 1.6-2 .9-4.1 1.3-6.2 1.3s-4.2-.4-6.2-1.3c1-.8 2.3-1.4 3.8-1.6-2.2-1-4.1-2.6-5.3-5 1.2.8 2.7 1.4 4.5 1.8-.5-.9-.8-1.9-.8-3.1 0-2 .8-3.8 2-6.2 1.2 2.4 2 4.2 2 6.2S12.5 12.2 12 13c-.5-.8-.8-1.8-.8-2.8 0-2 .8-3.8 2-6.2zM11 18h2v8h-2z"
            fill="currentColor"
          />
        </svg>
      </span>
      <p className="tb-desk-banner__right">
        Together for a stronger Lebanon
        <span aria-hidden>→</span>
      </p>
    </aside>
  );
}
