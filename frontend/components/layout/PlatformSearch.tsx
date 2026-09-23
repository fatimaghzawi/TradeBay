"use client";

import { catalogApi } from "@/lib/api/catalogApi";
import { identityApi } from "@/lib/api/identityApi";
import { platformUserName } from "@/lib/admin/identityDirectory";
import { ROUTES } from "@/lib/constants";
import {
  filterNavItems,
  type NavItem,
  type WorkspaceNav,
} from "@/lib/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

type SearchHit = {
  id: string;
  href: string;
  title: string;
  subtitle?: string;
  group: "Pages" | "Users" | "Companies" | "Products";
};

function flattenNav(items: NavItem[]): NavItem[] {
  const out: NavItem[] = [];
  for (const item of items) {
    out.push(item);
    if (item.children?.length) out.push(...flattenNav(item.children));
  }
  return out;
}

function matchPages(nav: WorkspaceNav, query: string, can: (code: string) => boolean): SearchHit[] {
  const needle = query.toLowerCase();
  const items = flattenNav([
    ...filterNavItems(nav.primary, can),
    ...filterNavItems(nav.secondary, can),
  ]);
  return items
    .filter((item) => {
      const hay = `${item.label} ${item.hint ?? ""} ${item.group ?? ""}`.toLowerCase();
      return hay.includes(needle);
    })
    .slice(0, 6)
    .map((item) => ({
      id: `page-${item.key}`,
      href: item.href,
      title: item.label,
      subtitle: item.hint || item.group || undefined,
      group: "Pages" as const,
    }));
}

async function searchRecords(query: string, can: (code: string) => boolean): Promise<SearchHit[]> {
  const hits: SearchHit[] = [];
  const jobs: Promise<void>[] = [];

  if (can("users.read")) {
    jobs.push(
      identityApi
        .listPlatformUsers({ q: query, page: 1, page_size: 5 })
        .then((result) => {
          for (const user of result.data) {
            hits.push({
              id: `user-${user.id}`,
              href: `${ROUTES.admin.users}?q=${encodeURIComponent(user.email || platformUserName(user))}`,
              title: platformUserName(user),
              subtitle: user.email || user.status,
              group: "Users",
            });
          }
        })
        .catch(() => undefined),
    );
  }

  if (can("businesses.read")) {
    jobs.push(
      identityApi
        .listPlatformBusinesses({ q: query, page: 1, page_size: 5 })
        .then((result) => {
          for (const biz of result.data) {
            const kind = biz.type === "supplier" ? "Supplier" : biz.type === "buyer" ? "Buyer" : "Company";
            hits.push({
              id: `biz-${biz.id}`,
              href: ROUTES.admin.businessDetail(biz.id),
              title: biz.name,
              subtitle: [kind, biz.email_domain, biz.contact_email].filter(Boolean).join(" · "),
              group: "Companies",
            });
          }
        })
        .catch(() => undefined),
    );
  }

  if (can("products.read")) {
    jobs.push(
      catalogApi
        .listProducts({ q: query, page: 1, page_size: 5 })
        .then((result) => {
          for (const product of result.data) {
            hits.push({
              id: `product-${product.id}`,
              href: ROUTES.admin.productDetail(product.id),
              title: product.name,
              subtitle: [product.sku, product.supplier_name].filter(Boolean).join(" · "),
              group: "Products",
            });
          }
        })
        .catch(() => undefined),
    );
  }

  await Promise.all(jobs);
  return hits;
}

const GROUP_ORDER: SearchHit["group"][] = ["Pages", "Users", "Companies", "Products"];

export function PlatformSearch({
  nav,
}: {
  nav: WorkspaceNav;
}) {
  const router = useRouter();
  const { permissions } = useAuth();
  const can = (code: string) => permissions.includes(code);
  const rootRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [remoteHits, setRemoteHits] = useState<SearchHit[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);

  const pageHits = useMemo(
    () => (query.trim().length >= 1 ? matchPages(nav, query.trim(), can) : []),
    [nav, query, permissions],
  );

  const hits = useMemo(() => {
    const merged = [...pageHits, ...remoteHits];
    const seen = new Set<string>();
    return merged.filter((hit) => {
      if (seen.has(hit.id)) return false;
      seen.add(hit.id);
      return true;
    });
  }, [pageHits, remoteHits]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setRemoteHits([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const handle = window.setTimeout(() => {
      void searchRecords(q, can).then((rows) => {
        if (cancelled) return;
        setRemoteHits(rows);
        setLoading(false);
      });
    }, 280);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [query, permissions]);

  useEffect(() => {
    setActiveIndex(0);
  }, [hits]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  function onSubmit() {
    const chosen = hits[activeIndex] ?? hits[0];
    if (chosen) {
      go(chosen.href);
      return;
    }
    const q = query.trim();
    if (q) go(`${ROUTES.admin.users}?q=${encodeURIComponent(q)}`);
  }

  const grouped = GROUP_ORDER.map((group) => ({
    group,
    items: hits.filter((hit) => hit.group === group),
  })).filter((section) => section.items.length > 0);

  const showPanel = open && query.trim().length > 0;

  return (
    <div ref={rootRef} className="tb-platform-search relative min-w-0 flex-1">
      <label className="relative block min-w-0">
        <span className="sr-only">Search</span>
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--tb-muted-fg)]">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
            <path d="M16 16l4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
        <input
          type="search"
          value={query}
          placeholder={nav.searchPlaceholder}
          autoComplete="off"
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActiveIndex((i) => Math.min(i + 1, Math.max(hits.length - 1, 0)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActiveIndex((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              onSubmit();
            }
          }}
          className="h-11 w-full rounded-full border border-[var(--tb-field-line)] bg-[var(--tb-field-bg)] py-0 pl-11 pr-4 text-sm text-[var(--tb-field-fg)] outline-none placeholder:text-[var(--tb-field-muted)] focus:border-[var(--tb-field-focus)]"
        />
      </label>

      {showPanel ? (
        <div className="tb-platform-search__fly tb-nav-fly" role="listbox">
          {loading && hits.length === 0 ? (
            <p className="tb-platform-search__empty">Searching…</p>
          ) : grouped.length === 0 ? (
            <p className="tb-platform-search__empty">No matches for “{query.trim()}”.</p>
          ) : (
            grouped.map((section) => (
              <div key={section.group} className="tb-nav-fly__group">
                <p className="tb-nav-fly__group-label">{section.group}</p>
                {section.items.map((hit) => {
                  const index = hits.findIndex((row) => row.id === hit.id);
                  return (
                    <button
                      key={hit.id}
                      type="button"
                      role="option"
                      aria-selected={index === activeIndex}
                      className="tb-nav-fly__link tb-platform-search__hit"
                      data-active={index === activeIndex}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => go(hit.href)}
                    >
                      <span className="tb-nav-fly__label">
                        <strong>{hit.title}</strong>
                        {hit.subtitle ? <em>{hit.subtitle}</em> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
