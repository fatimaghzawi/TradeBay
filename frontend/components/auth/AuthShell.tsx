"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const AUTH_VIDEO = "/videos/auth-hero.mp4";
const AUTH_LOGO = "/images/TradeBay-logo-light.png";

export type AuthScene =
  | "harbor"
  | "dock"
  | "coast"
  | "desk"
  | "celebrate";

type AuthShellProps = {
  children: ReactNode;
  scene?: AuthScene;
  
  variant?: "split" | "centered";
  compact?: boolean;
  plain?: boolean;
};

export function AuthShell({
  children,
  scene,
  variant = "split",
  compact = false,
  plain = false,
}: AuthShellProps) {
  const resolved: AuthScene =
    scene ??
    (variant === "centered" || plain ? "celebrate" : compact ? "dock" : "harbor");

  if (resolved === "celebrate") {
    return <CelebrateStage plain={plain}>{children}</CelebrateStage>;
  }

  return (
    <div
      className={cn(
        "auth-root min-h-svh bg-muted",
        "lg:grid lg:h-svh lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)] lg:overflow-hidden",
      )}
    >
      {resolved === "harbor" ? (
        <HarborPanel />
      ) : resolved === "dock" ? (
        <DockPanel />
      ) : resolved === "coast" ? (
        <CoastPanel />
      ) : (
        <DeskPanel />
      )}

      <main
        className={cn(
          "auth-panel relative flex min-h-svh flex-col px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-8 lg:h-full lg:min-h-0 lg:overflow-hidden lg:px-12 xl:px-16",
          compact ? "py-3 sm:py-4" : "py-4 sm:py-6",
        )}
      >
        <div
          className={cn(
            "mb-2 flex shrink-0 items-center justify-between lg:hidden",
            compact && "mb-1",
          )}
        >
          <Link href="/" aria-label="TradeBay home">
            <Image
              src={AUTH_LOGO}
              alt="TradeBay"
              width={140}
              height={36}
              priority
              className="h-8 w-auto object-contain object-left sm:h-9 dark:brightness-0 dark:invert"
            />
          </Link>
        </div>

        <div
          className={cn(
            "mx-auto flex w-full max-w-[26rem] flex-1 flex-col justify-start lg:min-h-0 lg:justify-center lg:overflow-y-auto",
            compact ? "py-0" : "py-1",
          )}
        >
          <div className={cn("auth-ticket", compact && "auth-ticket--compact")}>{children}</div>
        </div>
      </main>
    </div>
  );
}

function HarborPanel() {
  const [ended, setEnded] = useState(false);
  const PLAYBACK_RATE = 0.65;

  return (
    <aside className="relative hidden h-full overflow-hidden bg-primary lg:block">
      <video
        className={cn(
          "absolute inset-0 h-full w-full object-cover object-center transition-[filter,transform] duration-700",
          ended && "scale-105 blur-md brightness-[0.55]",
        )}
        autoPlay
        muted
        playsInline
        preload="auto"
        aria-hidden
        onLoadedMetadata={(e) => {
          e.currentTarget.playbackRate = PLAYBACK_RATE;
        }}
        onPlay={(e) => {
          e.currentTarget.playbackRate = PLAYBACK_RATE;
        }}
        onEnded={(e) => {
          e.currentTarget.pause();
          setEnded(true);
        }}
      >
        <source src={AUTH_VIDEO} type="video/mp4" />
      </video>
      <div
        className={cn(
          "absolute inset-0 transition-opacity duration-700",
          ended
            ? "bg-[#04140f]/55 backdrop-blur-[2px]"
            : "bg-gradient-to-t from-[#04140f]/55 via-transparent to-[#04140f]/25",
        )}
      />
      <WaveEdge />
      <div className="relative z-10 flex h-full flex-col px-10 py-10 xl:px-14">
        {!ended ? (
          <BrandOnDark />
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <Link
              href="/"
              className="inline-flex animate-[tb-toast-in_420ms_ease-out] rounded-2xl bg-white/95 px-8 py-6 shadow-[0_20px_60px_rgba(0,0,0,0.28)] ring-1 ring-white/40"
              aria-label="TradeBay home"
            >
              <Image
                src={AUTH_LOGO}
                alt="TradeBay"
                width={320}
                height={84}
                priority
                className="h-[4.75rem] w-auto object-contain xl:h-24"
              />
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}

function DockPanel() {
  const [ended, setEnded] = useState(false);
  const PLAYBACK_RATE = 0.7;

  return (
    <aside className="relative hidden h-full overflow-hidden bg-[#1a2e26] lg:block">
      <video
        className={cn(
          "absolute inset-0 h-full w-full object-cover object-center transition-[filter,transform] duration-700",
          ended && "scale-105 blur-md brightness-[0.5]",
        )}
        autoPlay
        muted
        playsInline
        preload="auto"
        aria-hidden
        onLoadedMetadata={(e) => {
          e.currentTarget.playbackRate = PLAYBACK_RATE;
        }}
        onEnded={(e) => {
          e.currentTarget.pause();
          setEnded(true);
        }}
      >
        <source src={AUTH_VIDEO} type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-gradient-to-br from-[#e86f2a]/35 via-transparent to-[#0d3b2a]/55" />
      <div
        className={cn(
          "absolute inset-0 transition-opacity duration-700",
          ended ? "bg-[#1a120c]/50 backdrop-blur-[2px]" : "bg-primary/25",
        )}
      />
      <WaveEdge tone="warm" />
      <div className="relative z-10 flex h-full flex-col px-10 py-10 xl:px-14">
        {!ended ? (
          <BrandOnDark />
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <Link
              href="/"
              className="inline-flex animate-[tb-toast-in_420ms_ease-out] rounded-2xl bg-white/95 px-8 py-6 shadow-[0_20px_60px_rgba(0,0,0,0.28)]"
              aria-label="TradeBay home"
            >
              <Image
                src={AUTH_LOGO}
                alt="TradeBay"
                width={300}
                height={80}
                className="h-20 w-auto object-contain"
              />
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}

function CoastPanel() {
  return (
    <aside className="relative hidden h-full overflow-hidden bg-[#1a4a5c] lg:block">
      <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_30%_20%,#f4a261_0%,#e07a3a_28%,#1a6b4f_58%,#0d3b2a_100%)]" />
      <WaveEdge tone="coast" />
      <div className="relative z-10 flex h-full flex-col justify-between px-10 py-10 xl:px-14">
        <BrandOnDark tagline="Email verification" />
        <div>
          <p className="font-[family-name:var(--font-outfit)] text-3xl font-semibold tracking-[-0.035em] text-[#ffe8d2]">
            Almost there
          </p>
          <p className="mt-2 max-w-[14rem] text-sm leading-relaxed text-white/85">
            Enter the code we sent to finish setting up your account.
          </p>
        </div>
      </div>
    </aside>
  );
}

function DeskPanel() {
  return (
    <aside className="relative hidden h-full overflow-hidden bg-[#2a241c] lg:block">
      <div className="absolute inset-0 bg-[linear-gradient(155deg,#3d3428_0%,#1a2e26_45%,#0d3b2a_100%)]" />
      <WaveEdge tone="desk" />
      <div className="relative z-10 flex h-full flex-col justify-between px-10 py-10 xl:px-14">
        <BrandOnDark tagline="Password reset" />
        <p className="max-w-[15rem] pb-4 text-sm leading-relaxed text-white/80">
          Choose a strong password to keep your TradeBay account secure.
        </p>
      </div>
    </aside>
  );
}

function CelebrateStage({
  children,
  plain,
}: {
  children: ReactNode;
  plain?: boolean;
}) {
  return (
    <div className="auth-root auth-panel relative min-h-svh lg:h-svh lg:overflow-hidden">
      {!plain ? (
        <>
          <div
            aria-hidden
            className="pointer-events-none absolute -right-16 top-10 h-64 w-64 bg-accent/15 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -left-12 bottom-8 h-56 w-56 bg-primary/20 blur-3xl"
          />
        </>
      ) : null}
      <div className="relative z-10 mx-auto flex min-h-svh w-full max-w-lg flex-col px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-8 sm:py-6 lg:h-full lg:overflow-hidden">
        <Link href="/" className="mb-3 inline-flex w-fit shrink-0 items-center sm:mb-4" aria-label="TradeBay home">
          <Image
            src={AUTH_LOGO}
            alt="TradeBay"
            width={140}
            height={36}
            className="h-8 w-auto object-contain sm:h-9 dark:brightness-0 dark:invert"
          />
        </Link>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-start lg:justify-center lg:overflow-y-auto lg:pb-6">
          <div className="auth-ticket w-full">{children}</div>
        </div>
      </div>
    </div>
  );
}

function BrandOnDark({ tagline }: { tagline?: string }) {
  return (
    <Link href="/" className="inline-flex flex-col gap-2" aria-label="TradeBay home">
      <Image
        src={AUTH_LOGO}
        alt="TradeBay"
        width={180}
        height={48}
        className="h-10 w-auto object-contain brightness-0 invert"
        priority
      />
      {tagline ? (
        <span className="text-[0.65rem] font-semibold uppercase tracking-[0.28em] text-white/55">
          {tagline}
        </span>
      ) : null}
    </Link>
  );
}

function WaveEdge({ tone = "cool" }: { tone?: "cool" | "warm" | "coast" | "desk" }) {
  const fill = "var(--tb-auth-panel)";
  return (
    <svg
      className="pointer-events-none absolute inset-y-0 right-0 z-20 h-full w-[6.5rem] translate-x-[1px]"
      viewBox="0 0 100 900"
      preserveAspectRatio="none"
      aria-hidden
      style={{ color: fill }}
    >
      <path d="M100 0 55 0 18 180 48 360 12 540 42 720 20 900 100 900Z" fill="currentColor" />
      <path
        d="M52 0 16 180 46 360 10 540 40 720 18 900"
        fill="none"
        stroke={tone === "warm" ? "#e86f2a" : "#1a6b4f"}
        strokeWidth="8"
        opacity="0.55"
      />
    </svg>
  );
}

