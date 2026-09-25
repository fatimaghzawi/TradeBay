"use client";

import { DirectoryMast } from "@/components/shared/DirectoryMast";
import type { ReactNode } from "react";
import { useState } from "react";

export type IdentityStat = {
  icon: string;
  tone?: "orange" | "green" | "teal" | "rose";
  value: string | number;
  label: string;
};

export type IdentityTab = {
  key: string;
  label: string;
};

type IdentityPageShellProps = {
  crumb: string;
  title: string;
  lede?: ReactNode;
  action?: ReactNode;
  banner?: {
    icon?: string;
    title: string;
    body: string;
  };
  stats?: IdentityStat[];
  tabs?: IdentityTab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
  search?: string;
  searchPlaceholder?: string;
  onSearchChange?: (value: string) => void;
  searchExtra?: ReactNode;
  quote?: string;
  mark?: string;
  children: ReactNode;
};

export function IdentityPageShell({
  crumb,
  title,
  lede: _lede,
  action,
  banner,
  stats,
  tabs,
  activeTab,
  onTabChange,
  search,
  searchPlaceholder = "Search…",
  onSearchChange,
  searchExtra,
  quote = "“The right people, with the right access, create extraordinary businesses.”",
  mark = "TradeBay",
  children,
}: IdentityPageShellProps) {
  const [bannerOpen, setBannerOpen] = useState(Boolean(banner));
  const crumbParts = crumb.split("/").map((p) => p.trim()).filter(Boolean);

  return (
    <div className="tb-roles">
      <p className="tb-ov-crumb">
        {crumbParts.map((part, i) => (
          <span key={`${part}-${i}`}>
            {i > 0 ? <span> / </span> : null}
            {part}
          </span>
        ))}
      </p>

      <DirectoryMast title={title} actions={action} size="page" mark={mark} />

      {banner && bannerOpen ? (
        <div className="tb-roles-banner">
          <span className="tb-roles-banner-icon" aria-hidden>
            {banner.icon ?? "◈"}
          </span>
          <div className="min-w-0 flex-1">
            <p>
              <strong>{banner.title}</strong> {banner.body}
            </p>
          </div>
          <button
            type="button"
            className="tb-roles-banner-close"
            aria-label="Dismiss"
            onClick={() => setBannerOpen(false)}
          >
            ×
          </button>
        </div>
      ) : null}

      {stats && stats.length > 0 ? (
        <section className="tb-roles-stats">
          {stats.map((stat) => (
            <div key={stat.label} className="tb-roles-stat">
              <span className="tb-roles-stat-icon" data-tone={stat.tone ?? "green"}>
                {stat.icon}
              </span>
              <div>
                <p className="tb-roles-stat-value">{stat.value}</p>
                <p className="tb-roles-stat-label">{stat.label}</p>
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {(tabs && tabs.length > 0) || onSearchChange || searchExtra ? (
        <div className="tb-roles-toolbar">
          {tabs && tabs.length > 0 && onTabChange ? (
            <div className="tb-roles-tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  data-active={activeTab === tab.key}
                  className="tb-roles-tab"
                  onClick={() => onTabChange(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : (
            <div />
          )}
          <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
            {searchExtra}
            {onSearchChange ? (
              <input
                value={search ?? ""}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder={searchPlaceholder}
                className="tb-roles-search"
              />
            ) : null}
          </div>
        </div>
      ) : null}

      {children}

      {quote ? <p className="tb-roles-quote">{quote}</p> : null}
    </div>
  );
}
