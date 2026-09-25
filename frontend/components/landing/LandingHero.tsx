"use client";

import { StoryBridge } from "@/components/landing/LandingStoryChrome";
import { LP } from "@/lib/landingLinks";
import Link from "next/link";
import { useEffect, useRef } from "react";

const HERO_VIDEO = "/videos/hero-workers-buses.mp4";
const HERO_POSTER = "/images/landing/hero-mock.jpg";
const NEXT_SECTION_ID = "trade-story";

export function LandingHero() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const advancedRef = useRef(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (reduceMotion) return;

    let timer: ReturnType<typeof setTimeout> | null = null;

    const cancel = () => {
      cancelledRef.current = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const onWheel = () => cancel();
    const onTouch = () => cancel();
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === "ArrowDown" ||
        e.key === "PageDown" ||
        e.key === " " ||
        e.key === "Escape"
      ) {
        cancel();
      }
    };

    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("keydown", onKey);

    const advance = () => {
      if (advancedRef.current || cancelledRef.current) return;
      if (window.scrollY > 48) {
        cancelledRef.current = true;
        return;
      }
      advancedRef.current = true;
      document
        .getElementById(NEXT_SECTION_ID)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const armTimer = () => {
      if (timer || advancedRef.current || cancelledRef.current) return;
      const duration = video.duration;
      if (!Number.isFinite(duration) || duration <= 0) return;
      
      const delayMs = Math.max(2500, (duration - 0.6) * 1000);
      timer = setTimeout(advance, delayMs);
    };

    if (video.readyState >= 1) armTimer();
    video.addEventListener("loadedmetadata", armTimer);

    return () => {
      if (timer) clearTimeout(timer);
      video.removeEventListener("loadedmetadata", armTimer);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <>
      <section id="hero-video" className="tb-lp-hero">
        <div className="tb-lp-hero__media">
          <video
            ref={videoRef}
            className="tb-lp-hero__video"
            src={HERO_VIDEO}
            poster={HERO_POSTER}
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            aria-label="TradeBay workers and logistics animation"
          />
          <div className="tb-lp-hero__shade" aria-hidden />
          <div className="tb-lp-hero__glass" aria-hidden />
          <div className="tb-lp-hero__frame" aria-hidden>
            <span className="tb-lp-hero__corner is-tl" />
            <span className="tb-lp-hero__corner is-tr" />
            <span className="tb-lp-hero__corner is-bl" />
            <span className="tb-lp-hero__corner is-br" />
            <span className="tb-lp-hero__edge is-top" />
            <span className="tb-lp-hero__edge is-bottom" />
            <span className="tb-lp-hero__edge is-left" />
            <span className="tb-lp-hero__edge is-right" />
          </div>
        </div>

        <div className="tb-lp-wrap tb-lp-hero__content landing-reveal">
          <p className="tb-lp-hero__brand">TradeBay</p>
          <h1 className="tb-lp-hero__title">Lebanon&apos;s B2B marketplace</h1>
          <div className="tb-lp-hero__actions">
            <Link href={LP.marketplace} className="tb-lp-btn tb-lp-btn--primary">
              Explore marketplace
            </Link>
            <Link
              href={LP.register}
              className="tb-lp-btn tb-lp-btn--ghost tb-lp-btn--on-media"
            >
              Get started
            </Link>
          </div>
        </div>

        <a href={`#${NEXT_SECTION_ID}`} className="tb-lp-hero__continue">
          Continue
          <span aria-hidden>↓</span>
        </a>
      </section>

      <StoryBridge from="Arrive" to="The road" />

      <section id={NEXT_SECTION_ID} className="tb-lp-story">
        <div className="tb-lp-wrap tb-lp-story__grid">
          <div className="tb-lp-story__copy">
            <p className="tb-lp-chapter-mark">
              <span>02</span>
              The story continues
            </p>
            <p className="tb-lp-eyebrow">From the road to the shelf</p>
            <h2>Trade keeps moving across Lebanon</h2>
            <p>
              The same energy in that film — workers, routes, and reliable
              delivery — is what TradeBay organizes online: find suppliers,
              request quotes, and move goods with clarity.
            </p>
            <Link href="#categories" className="tb-lp-section-link">
              Browse categories →
            </Link>
          </div>
          <ul className="tb-lp-story__beats">
            <li>
              <Link href={LP.marketplace}>
                <strong>Source</strong>
                <span>Verified products from local suppliers</span>
              </Link>
            </li>
            <li>
              <Link href={LP.procurement}>
                <strong>Request</strong>
                <span>Send RFQs without leaving the bay</span>
              </Link>
            </li>
            <li>
              <Link href={LP.suppliers}>
                <strong>Deliver</strong>
                <span>Partner with suppliers across Lebanon</span>
              </Link>
            </li>
          </ul>
        </div>
      </section>
    </>
  );
}
