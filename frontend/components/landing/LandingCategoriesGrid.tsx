"use client";

import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category } from "@/lib/api/catalogApi";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ROUTES } from "@/lib/constants";
import { LP } from "@/lib/landingLinks";
import { mediaUrl } from "@/lib/media";
import Link from "next/link";
import { useEffect, useState } from "react";

const FEATURED_CATEGORY_COUNT = 10;

export function LandingCategoriesGrid() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void catalogApi
      .listCategories({ active_only: true, page_size: 100 })
      .then((result) => {
        const roots = result.data
          .filter((c) => !c.parent_category_id)
          .sort((a, b) => a.display_order - b.display_order);
        setCategories(roots.length ? roots : result.data);
      })
      .catch((err) => {
        if (!(err instanceof ApiError)) {
          console.error(err);
        }
        setCategories([]);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingEntity entity="categories" className="justify-center py-8" />;
  }

  if (categories.length === 0) {
    return (
      <p className="tb-lp-cats__empty">
        Categories will appear here once platform staff publish them.{" "}
        <Link href={LP.marketplace} className="font-semibold underline">
          Browse the marketplace
        </Link>
        .
      </p>
    );
  }

  return (
    <div className="tb-lp-cats__grid">
      {categories.slice(0, FEATURED_CATEGORY_COUNT).map((cat) => {
        const href = `${ROUTES.inventoryProducts}?category=${encodeURIComponent(cat.id)}`;
        const src = mediaUrl(cat.image_url);
        return (
          <Link key={cat.id} href={href} className={src ? "tb-lp-cat tb-lp-cat--photo" : "tb-lp-cat"}>
            <div className="tb-lp-cat__media">
              {src ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={src} alt={cat.name} />
              ) : (
                <span className="tb-lp-cat__fallback" aria-hidden>
                  {cat.name.slice(0, 1).toUpperCase()}
                </span>
              )}
            </div>
            <span className="tb-lp-cat__name">
              <span>{cat.name}</span>
              <i aria-hidden>→</i>
            </span>
          </Link>
        );
      })}
    </div>
  );
}
