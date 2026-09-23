"use client";

import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ROUTES } from "@/lib/constants";
import { LP } from "@/lib/landingLinks";
import { mediaUrl } from "@/lib/media";
import {
  isProductSaved,
  PRODUCT_FAV_EVENT,
  toggleProductFavorite,
} from "@/lib/productFavorites";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

const FEATURED_COUNT = 4;

type RailItem = {
  id: string;
  name: string;
  supplier: string;
  rating: string;
  moq: string;
  image: string;
  href: string;
};

function fromCatalog(products: Product[]): RailItem[] {
  return products.slice(0, FEATURED_COUNT).map((p) => ({
    id: p.id,
    name: p.name,
    supplier: p.supplier_name ?? "Supplier",
    rating: "—",
    moq: `${p.moq} ${p.unit}`,
    image: p.primary_image_url ? mediaUrl(p.primary_image_url) : "",
    href: ROUTES.inventoryProduct(p.id),
  }));
}

async function loadFeaturedProducts(): Promise<Product[]> {
  const featured = await catalogApi.listProducts({
    status: "active",
    featured: true,
    include_details: true,
    page_size: FEATURED_COUNT,
  });
  const rows = featured.data ?? [];
  if (rows.length > 0) return rows;
  const latest = await catalogApi.listProducts({
    status: "active",
    include_details: true,
    page_size: FEATURED_COUNT,
  });
  return latest.data ?? [];
}

function FavoriteHeart({ product }: { product: RailItem }) {
  const [saved, setSaved] = useState(() => isProductSaved(product.id));

  useEffect(() => {
    const sync = () => setSaved(isProductSaved(product.id));
    sync();
    window.addEventListener(PRODUCT_FAV_EVENT, sync);
    return () => window.removeEventListener(PRODUCT_FAV_EVENT, sync);
  }, [product.id]);

  return (
    <button
      type="button"
      className={`tb-lp-product__fav${saved ? " is-on" : ""}`}
      aria-label={saved ? `Remove ${product.name} from favorites` : `Save ${product.name}`}
      aria-pressed={saved}
      onClick={() => {
        const result = toggleProductFavorite({
          id: product.id,
          name: product.name,
          image: product.image,
          href: product.href,
        });
        setSaved(result.saved);
      }}
    >
      {saved ? "♥" : "♡"}
    </button>
  );
}

export function FeaturedProductsRail() {
  const [items, setItems] = useState<RailItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void loadFeaturedProducts()
      .then((rows) => {
        if (!cancelled) setItems(fromCatalog(rows));
      })
      .catch((err) => {
        if (!(err instanceof ApiError)) {
          console.error(err);
        }
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section
      id="featured"
      className="tb-lp-products"
      aria-labelledby="featured-heading"
    >
      <div className="tb-lp-wrap">
        <div className="tb-lp-section-head">
          <h2 id="featured-heading">Featured Products</h2>
          <Link href={LP.marketplace} className="tb-lp-section-link">
            View all →
          </Link>
        </div>
        {loading ? (
          <LoadingEntity entity="products" className="py-8" />
        ) : items.length === 0 ? (
          <p className="tb-lp-products__empty">
            Featured products will appear here once suppliers publish them.{" "}
            <Link href={LP.marketplace} className="font-semibold underline">
              Browse the marketplace
            </Link>
            .
          </p>
        ) : (
          <div className="tb-lp-products__rail">
            {items.map((product) => (
              <article key={product.id} className="tb-lp-product">
                <div className="tb-lp-product__media">
                  {product.image.startsWith("/images/") || product.image.startsWith("http") ? (
                    <Image
                      src={product.image}
                      alt=""
                      fill
                      sizes="(max-width: 720px) 50vw, 25vw"
                      className="object-contain p-2.5"
                      unoptimized={!product.image.startsWith("/images/")}
                    />
                  ) : product.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={product.image} alt="" className="tb-lp-product__img" />
                  ) : (
                    <span className="tb-lp-product__fallback" aria-hidden>
                      {product.name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                  <FavoriteHeart product={product} />
                </div>
                <div className="tb-lp-product__body">
                  <h3>{product.name}</h3>
                  <p>{product.supplier}</p>
                  <div className="tb-lp-product__meta">
                    <span>★ {product.rating}</span>
                    <span>MOQ {product.moq}</span>
                  </div>
                  <Link href={product.href} className="tb-lp-product__link">
                    View Product →
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
