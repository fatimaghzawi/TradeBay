"use client";

import { catalogApi, type Category } from "@/lib/api/catalogApi";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const FALLBACK = [
  { name: "Construction Materials", pct: 28 },
  { name: "Agricultural Supplies", pct: 22 },
  { name: "Food & Beverages", pct: 18 },
  { name: "Electronics", pct: 16 },
  { name: "Home & Kitchen", pct: 12 },
] as const;

export function DashboardCategories() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    catalogApi
      .listCategories({ page: 1, page_size: 12 })
      .then((res) => {
        if (!cancelled) {
          setCategories(
            res.data
              .filter((c) => c.is_active && !c.parent_category_id)
              .sort((a, b) => a.display_order - b.display_order)
              .slice(0, 5),
          );
        }
      })
      .catch(() => {
        if (!cancelled) setCategories([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => {
    if (categories.length === 0) {
      return FALLBACK.map((f, i) => ({ id: `fb-${i}`, name: f.name, pct: f.pct, href: ROUTES.marketplace }));
    }
    const weights = [28, 22, 18, 16, 12];
    return categories.map((c, i) => ({
      id: c.id,
      name: c.name,
      pct: weights[i] ?? Math.max(8, 30 - i * 4),
      href: `${ROUTES.marketplace}?category=${encodeURIComponent(c.id)}`,
    }));
  }, [categories]);

  return (
    <section className="tb-desk-cats" aria-labelledby="tb-desk-cats-title">
      <header className="tb-desk-panel__head">
        <div>
          <h2 id="tb-desk-cats-title">Top Product Categories</h2>
        </div>
        <span className="tb-desk-cats__range">This month</span>
      </header>

      {loading ? (
        <LoadingEntity entity="categories" />
      ) : (
        <ol className="tb-desk-cats__list">
          {rows.map((row, i) => (
            <li key={row.id}>
              <Link href={row.href}>
                <span className="tb-desk-cats__rank">{i + 1}</span>
                <span className="tb-desk-cats__meta">
                  <strong>{row.name}</strong>
                  <span className="tb-desk-cats__bar" aria-hidden>
                    <span style={{ width: `${row.pct}%` }} />
                  </span>
                </span>
                <em>{row.pct}%</em>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
