"use client";

import { FavoritesButton } from "@/components/cart/FavoritesButton";
import { LP } from "@/lib/landingLinks";
import { ROUTES } from "@/lib/constants";
import { LANDING_NAV } from "@/lib/landing";
import { cn } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

const LOGO = "/images/TradeBay-logo-light.png";

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "tb-lp-nav fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled && "is-scrolled",
      )}
    >
      <div className="tb-lp-nav__inner">
        <Link href={LP.home} className="tb-lp-nav__brand" aria-label="TradeBay home">
          <Image
            src={LOGO}
            alt="TradeBay"
            width={160}
            height={42}
            className="tb-lp-nav__logo"
            priority
          />
          <span className="tb-lp-nav__tag">Trade Smarter. Grow Together.</span>
        </Link>

        <nav className="tb-lp-nav__links" aria-label="Primary">
          {LANDING_NAV.map((item) => (
            <Link key={item.label} href={item.href} className="tb-lp-nav__link">
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="tb-lp-nav__actions">
          <FavoritesButton
            className="tb-lp-nav__fav"
            badgeClassName="tb-lp-nav__fav-badge"
          />
          <Link href={ROUTES.login} className="tb-lp-nav__login">
            Log in
          </Link>
          <Link href={LP.register} className="tb-lp-nav__cta">
            Get Started
          </Link>
          <button
            type="button"
            className="tb-lp-nav__menu-btn"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "×" : "≡"}
          </button>
        </div>
      </div>

      {open ? (
        <div className="tb-lp-nav__drawer">
          {LANDING_NAV.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
          <Link href={ROUTES.login} onClick={() => setOpen(false)}>
            Log in
          </Link>
          <Link href={LP.register} onClick={() => setOpen(false)}>
            Get Started
          </Link>
        </div>
      ) : null}
    </header>
  );
}
