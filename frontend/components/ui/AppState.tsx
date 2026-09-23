"use client";

import { Spinner } from "@/components/ui/LoadingState";
import { cn } from "@/lib/utils";
import Link from "next/link";
import type { ReactNode } from "react";

export type AppStateTone = "loading" | "error" | "not-found" | "empty";

type AppStateFrameProps = {
  tone: AppStateTone;
  title: string;
  body?: ReactNode;
  actions?: ReactNode;
  /** Compact = inline section; page = full viewport moment */
  size?: "page" | "section";
  className?: string;
  children?: ReactNode;
};

const TONE_MARK: Record<AppStateTone, string> = {
  loading: "Loading",
  error: "Something went wrong",
  "not-found": "Missing route",
  empty: "Nothing here",
};

const TONE_GLYPH: Record<AppStateTone, string> = {
  loading: "◉",
  error: "!",
  "not-found": "?",
  empty: "◇",
};

/**
 * Shared chrome for loading / error / not-found / empty moments.
 * Keeps TradeBay page openings consistent across the shell.
 */
export function AppStateFrame({
  tone,
  title,
  body,
  actions,
  size = "section",
  className,
  children,
}: AppStateFrameProps) {
  return (
    <div
      className={cn(
        "tb-app-state",
        size === "page" && "tb-app-state--page",
        `tb-app-state--${tone}`,
        className,
      )}
      role={tone === "error" ? "alert" : undefined}
      aria-busy={tone === "loading" ? true : undefined}
      aria-live={tone === "loading" ? "polite" : undefined}
    >
      <div className="tb-app-state__bloom" aria-hidden />
      <div className="tb-app-state__ring" aria-hidden />

      <p className="tb-app-state__mark">{TONE_MARK[tone]}</p>

      <div className="tb-app-state__flourish" aria-hidden>
        <span />
        <em>✦</em>
        <span />
      </div>

      <div className={`tb-app-state__glyph tb-app-state__glyph--${tone}`} aria-hidden>
        {tone === "loading" ? (
          <Spinner size="md" />
        ) : (
          <span>{TONE_GLYPH[tone]}</span>
        )}
      </div>

      <h1 className="tb-app-state__title">{title}</h1>

      <svg className="tb-app-state__ink" viewBox="0 0 280 22" aria-hidden>
        <path
          d="M6 12 C48 4, 90 18, 132 10 C174 2, 216 16, 274 8"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      </svg>

      {body ? <div className="tb-app-state__body">{body}</div> : null}
      {children}
      {actions ? <div className="tb-app-state__actions">{actions}</div> : null}
    </div>
  );
}

export function AppStateAction({
  href,
  onClick,
  children,
  tone = "primary",
}: {
  href?: string;
  onClick?: () => void;
  children: ReactNode;
  tone?: "primary" | "soft";
}) {
  const className = cn(
    "tb-app-state__btn",
    tone === "soft" && "tb-app-state__btn--soft",
  );
  if (href) {
    return (
      <Link href={href} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={className} onClick={onClick}>
      {children}
    </button>
  );
}
