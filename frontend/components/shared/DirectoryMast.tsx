"use client";

import type { FormEvent, ReactNode } from "react";

export type DirectoryMastStat = { value: string | number; label: string };

type Props = {
  title: ReactNode;
  lede?: ReactNode;
  searchId?: string;
  searchValue?: string;
  searchPlaceholder?: string;
  onSearchChange?: (value: string) => void;
  onSearchSubmit?: () => void;
  stats?: DirectoryMastStat[];
  actions?: ReactNode;
  meta?: ReactNode;
  
  size?: "display" | "page";
  mark?: string;
};

export function DirectoryMast({
  title,
  lede,
  searchId,
  searchValue,
  searchPlaceholder = "Search…",
  onSearchChange,
  onSearchSubmit,
  stats,
  actions,
  meta: _meta,
  size = "display",
  mark = "TradeBay",
}: Props) {
  const showSearch = Boolean(searchId && onSearchChange);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    onSearchSubmit?.();
  }

  return (
    <header className={`tb-sign${size === "page" ? " tb-sign--page" : ""}`}>
      <div className="tb-sign__bloom" aria-hidden />
      <div className="tb-sign__ring" aria-hidden />

      <div className="tb-sign__plate">
        <p className="tb-sign__mark">{mark}</p>

        <div className="tb-sign__flourish" aria-hidden>
          <span />
          <em>✦</em>
          <span />
        </div>

        <h1 className="tb-sign__title">{title}</h1>

        <svg className="tb-sign__ink" viewBox="0 0 320 28" aria-hidden>
          <path
            className="tb-sign__ink-path"
            d="M8 16 C52 6, 98 22, 148 12 C198 2, 248 20, 312 10"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <path
            d="M248 18 C268 24, 288 14, 308 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity="0.55"
          />
        </svg>

        {lede ? <div className="tb-sign__lede">{lede}</div> : null}
      </div>

      {showSearch ? (
        <form className="tb-sign__search" onSubmit={onSubmit}>
          <label htmlFor={searchId} className="sr-only">
            Search
          </label>
          <span className="tb-sign__search-icon" aria-hidden>
            ⌕
          </span>
          <input
            id={searchId}
            value={searchValue ?? ""}
            onChange={(e) => onSearchChange?.(e.target.value)}
            placeholder={searchPlaceholder}
          />
          <button type="submit">Search</button>
        </form>
      ) : null}

      {actions ? <div className="tb-sign__actions">{actions}</div> : null}

      {stats && stats.length > 0 ? (
        <ul className="tb-sign__stats">
          {stats.map((s) => (
            <li key={s.label}>
              <strong>{s.value}</strong>
              <span>{s.label}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </header>
  );
}
