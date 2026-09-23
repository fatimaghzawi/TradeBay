import { ShoppingTraysHost } from "@/components/cart/ShoppingTrays";
import { FeaturedProductsRail } from "@/components/landing/FeaturedProductsRail";
import { LandingCategoriesGrid } from "@/components/landing/LandingCategoriesGrid";
import { LandingHero } from "@/components/landing/LandingHero";
import { LandingNav } from "@/components/landing/LandingNav";
import { LandingNewsletterForm } from "@/components/landing/LandingNewsletterForm";
import {
  LandingStoryChrome,
  StoryBridge,
} from "@/components/landing/LandingStoryChrome";
import {
  LANDING_FOOTER,
  LANDING_PATHS,
  LANDING_PROOF_STATS,
} from "@/lib/landing";
import { LP } from "@/lib/landingLinks";
import Image from "next/image";
import Link from "next/link";

const LOGO = "/images/TradeBay-logo-light.png";

const STORY_CHAPTERS = [
  { id: "hero-video", label: "Arrive" },
  { id: "trade-story", label: "The road" },
  { id: "categories", label: "Browse" },
  { id: "paths", label: "Choose" },
  { id: "featured", label: "Discover" },
  { id: "proof", label: "Why" },
  { id: "site-footer", label: "Stay" },
] as const;

function ChapterMark({ step, title }: { step: string; title: string }) {
  return (
    <p className="tb-lp-chapter-mark">
      <span>{step}</span>
      {title}
    </p>
  );
}

function WaveDivider({ flip = false }: { flip?: boolean }) {
  return (
    <div className={`tb-lp-wave${flip ? " is-flip" : ""}`} aria-hidden>
      <svg viewBox="0 0 1440 80" preserveAspectRatio="none">
        <path
          d="M0,48 C240,88 480,0 720,32 C960,64 1200,80 1440,24 L1440,80 L0,80 Z"
          fill="currentColor"
        />
      </svg>
    </div>
  );
}

function PathIcon({ name }: { name: "buyers" | "suppliers" | "planner" }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  if (name === "buyers") {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden {...common}>
        <circle cx="9" cy="8" r="2.4" />
        <circle cx="15.5" cy="8.5" r="2.1" />
        <path d="M4.5 18c.6-2.4 2.4-3.6 4.5-3.6S13 15.6 13.5 18" />
        <path d="M12.5 18c.4-1.8 1.6-2.8 3.2-2.8 1.7 0 2.9 1 3.3 2.8" />
      </svg>
    );
  }
  if (name === "suppliers") {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden {...common}>
        <path d="M4 10.5 12 5l8 5.5V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8.5Z" />
        <path d="M10 20v-5h4v5" />
        <path d="M4 10.5h16" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden {...common}>
      <path d="M12 4.5 13.2 8H17l-3 2.2L15.2 14 12 11.6 8.8 14l1.2-3.8L7 8h3.8L12 4.5Z" />
      <path d="M18.5 5.5 19 7l1.5.5L19 8l-.5 1.5L18 8l-1.5-.5L18 7l.5-1.5Z" />
      <path d="M6 14.5 6.4 15.6 7.5 16 6.4 16.4 6 17.5 5.6 16.4 4.5 16l1.1-.4L6 14.5Z" />
    </svg>
  );
}

/** Landing — continuous scroll story from hero to footer. */
export function LandingPageView() {
  return (
    <div className="landing-root tb-lp tb-lp--story">
      <LandingNav />
      <ShoppingTraysHost />
      <LandingStoryChrome chapters={[...STORY_CHAPTERS]} />

      <LandingHero />

      <StoryBridge from="The road" to="Browse" />

      <section id="categories" className="tb-lp-cats">
        <div className="tb-lp-wrap">
          <ChapterMark step="03" title="What Lebanon trades" />
          <div className="tb-lp-section-head">
            <h2>Shop by Category</h2>
            <Link href={LP.categories} className="tb-lp-section-link">
              Explore All Categories →
            </Link>
          </div>
          <div className="tb-lp-cats__grid-wrap">
            <LandingCategoriesGrid />
          </div>
        </div>
      </section>

      <StoryBridge from="Browse" to="Choose your path" />

      <section id="paths" className="tb-lp-paths">
        <div className="tb-lp-wrap">
          <ChapterMark step="04" title="Pick how you enter the bay" />
          <div className="tb-lp-paths__stage">
            <svg
              className="tb-lp-paths__bg"
              viewBox="0 0 1200 480"
              preserveAspectRatio="none"
              aria-hidden
            >
              <path
                className="tb-lp-paths__bg-cream"
                d="M340 0 H1200 V480 H300
                   C360 430 330 380 355 320
                   C380 260 330 210 360 150
                   C385 100 345 50 340 0 Z"
              />
              <path
                className="tb-lp-paths__bg-green"
                d="M0 0 H340
                   C345 50 385 100 360 150
                   C330 210 380 260 355 320
                   C330 380 360 430 300 480
                   H0 Z"
              />
              <path
                className="tb-lp-paths__bg-split"
                d="M760 24
                   C742 90 778 150 755 220
                   C732 290 770 350 748 420
                   C742 445 750 465 755 480"
                fill="none"
              />
            </svg>

            <div className="tb-lp-paths__grid">
              {LANDING_PATHS.map((path, i) => (
                <div key={path.id} className="tb-lp-path-slot">
                  {i === 2 ? (
                    <div className="tb-lp-path-divider" aria-hidden>
                      <svg viewBox="0 0 24 320" preserveAspectRatio="none">
                        <path
                          d="M12 0
                             C4 40 20 80 10 120
                             C0 160 18 200 8 240
                             C2 270 14 300 12 320"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                      </svg>
                    </div>
                  ) : null}
                  <article
                    id={path.id}
                    className="tb-lp-path"
                    data-tone={path.tone}
                  >
                    <span className="tb-lp-path__icon" aria-hidden>
                      <PathIcon name={path.icon} />
                    </span>
                    <p className="tb-lp-path__kicker">{path.kicker}</p>
                    <h3>{path.title}</h3>
                    <p className="tb-lp-path__body">{path.body}</p>
                    <Link href={path.href} className="tb-lp-path__cta">
                      {path.cta}
                      <span aria-hidden>→</span>
                    </Link>
                  </article>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <StoryBridge from="Choose" to="Products in motion" />

      <FeaturedProductsRail />

      <StoryBridge from="Discover" to="Why here" />

      <WaveDivider />
      <section id="proof" className="tb-lp-proof">
        <div className="tb-lp-wrap">
          <ChapterMark step="05" title="Why trade on this bay" />
          <div className="tb-lp-proof__grid">
            <blockquote className="tb-lp-proof__quote">
              <p>
                Wholesale in Lebanon moves fast, local, and relationship-first.
                TradeBay keeps that rhythm — open catalogues, clear plans, and
                deals that stay on one bay from first look to signed RFQ.
              </p>
              <footer>
                <span className="tb-lp-proof__avatar" aria-hidden>
                  LB
                </span>
                <div>
                  <strong>Built for Lebanon</strong>
                  <span>B2B trade, end to end</span>
                </div>
              </footer>
            </blockquote>

            <ul className="tb-lp-proof__stats">
              {LANDING_PROOF_STATS.map((stat) => (
                <li key={stat.label}>
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                </li>
              ))}
            </ul>

            <div className="tb-lp-proof__cedar" aria-hidden>
              <svg viewBox="0 0 120 140" className="tb-lp-cedar">
                <path
                  d="M60 12c-6 14-18 22-18 34 0 8 5 14 12 18-10 2-18 10-18 20 0 10 8 16 20 18-12 4-20 12-20 24h52c0-12-8-20-20-24 12-2 20-8 20-18 0-10-8-18-18-20 7-4 12-10 12-18 0-12-12-20-18-34-2 18-8 28-16 34Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                />
                <path d="M60 96v32" fill="none" stroke="currentColor" strokeWidth="2.2" />
              </svg>
              <p>Local Business · Stronger Lebanon</p>
            </div>
          </div>
        </div>
      </section>
      <WaveDivider flip />

      <StoryBridge from="Why here" to="Stay with the bay" />

      <footer id="site-footer" className="tb-lp-footer">
        <div className="tb-lp-wrap">
          <ChapterMark step="06" title="Stay with the bay" />
          <div className="tb-lp-footer__grid">
            <div className="tb-lp-footer__brand">
              <Image
                src={LOGO}
                alt="TradeBay"
                width={150}
                height={40}
                className="tb-lp-footer__logo"
              />
              <p>
                Lebanon&apos;s B2B marketplace for verified suppliers, smarter
                sourcing, and stronger local trade.
              </p>
              <div className="tb-lp-footer__social">
                {LANDING_FOOTER.social.map((item) => (
                  <Link key={item.label} href={item.href} aria-label={item.label}>
                    {item.short}
                  </Link>
                ))}
              </div>
            </div>

            <div>
              <h4>Marketplace</h4>
              <ul>
                {LANDING_FOOTER.marketplace.map((item) => (
                  <li key={item.label}>
                    <Link href={item.href}>{item.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4>For Businesses</h4>
              <ul>
                {LANDING_FOOTER.businesses.map((item) => (
                  <li key={item.label}>
                    <Link href={item.href}>{item.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Resources</h4>
              <ul>
                {LANDING_FOOTER.resources.map((item) => (
                  <li key={item.label}>
                    <Link href={item.href}>{item.label}</Link>
                  </li>
                ))}
              </ul>
            </div>

            <LandingNewsletterForm />
          </div>

          <div className="tb-lp-footer__bar">
            <p>© {new Date().getFullYear()} TradeBay. All rights reserved.</p>
            <div>
              <Link href={LP.privacy}>Privacy Policy</Link>
              <Link href={LP.terms}>Terms of Service</Link>
              <Link href={LP.privacy}>Cookie Policy</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
