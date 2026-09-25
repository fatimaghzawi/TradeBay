"use client";

import {
  InventoryEmpty,
  InventorySkeleton,
} from "@/components/catalog/InventoryUi";
import { AddToCartButton } from "@/components/cart/AddToCartButton";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import type { Category, Product } from "@/lib/api/catalogApi";
import { LEBANON_REGIONS } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  isProductSaved,
  PRODUCT_FAV_EVENT,
  toggleProductFavorite,
} from "@/lib/productFavorites";
import { useAuth } from "@/providers/AuthProvider";

function priceLabel(p: Product) {
  const tier = p.prices?.[0];
  if (!tier) return "Ask for quote";
  return `${tier.currency} ${tier.unit_price}`;
}

function parsePrice(p: Product): number | null {
  const n = Number(p.prices?.[0]?.unit_price);
  return Number.isFinite(n) ? n : null;
}

function isInStock(p: Product) {
  return Number(p.inventory?.available_quantity ?? 0) > 0;
}

function isNewArrival(p: Product) {
  if (!p.created_at) return false;
  const created = new Date(p.created_at).getTime();
  if (!Number.isFinite(created)) return false;
  return Date.now() - created < 1000 * 60 * 60 * 24 * 45;
}

type Segment = "all" | "new" | "in_stock" | "open_price" | "low_moq";

type Props = {
  products: Product[];
  categories: Category[];
  query: string;
  setQuery: (v: string) => void;
  categoryId: string;
  setCategoryId: (v: string) => void;
  supplierId: string;
  setSupplierId: (v: string) => void;
  unit: string;
  setUnit: (v: string) => void;
  originQ: string;
  setOriginQ: (v: string) => void;
  sort: "updated" | "name" | "supplier";
  setSort: (v: "updated" | "name" | "supplier") => void;
  page: number;
  setPage: (v: number) => void;
  total: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  setError: (v: string | null) => void;
  units: string[];
};

export function BuyerMarketplace({
  products,
  categories,
  query,
  setQuery,
  categoryId,
  setCategoryId,
  supplierId,
  setSupplierId,
  unit,
  setUnit,
  originQ,
  setOriginQ,
  sort,
  setSort,
  page,
  setPage,
  total,
  pageSize,
  loading,
  error,
  setError,
  units,
}: Props) {
  const [segment, setSegment] = useState<Segment>("all");
  const [maxMoq, setMaxMoq] = useState<number | null>(null);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [openPriceOnly, setOpenPriceOnly] = useState(false);
  const [draftOrigin, setDraftOrigin] = useState(originQ);
  const [view, setView] = useState<"grid" | "list">("grid");

  const categoryName = (id: string) =>
    categories.find((c) => c.id === id)?.name ?? "Uncategorized";

  const suppliers = useMemo(() => {
    const map = new Map<string, { id: string; name: string; logo?: string | null }>();
    for (const p of products) {
      if (!map.has(p.business_account_id)) {
        map.set(p.business_account_id, {
          id: p.business_account_id,
          name: p.supplier_name ?? "Supplier",
          logo: p.supplier_logo_url,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [products]);

  const bounds = useMemo(() => {
    const moqs = products.map((p) => p.moq).filter((n) => Number.isFinite(n) && n > 0);
    const prices = products.map(parsePrice).filter((n): n is number => n != null);
    return {
      moqMax: moqs.length ? Math.max(50, Math.ceil(Math.max(...moqs) / 10) * 10) : 100,
      priceMax: prices.length ? Math.ceil(Math.max(...prices)) : 1000,
    };
  }, [products]);

  const parentOf = useMemo(
    () => new Map(categories.map((c) => [c.id, c.parent_category_id ?? null])),
    [categories],
  );

  const categoryCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of products) {
      let id: string | null = p.category_id;
      const seen = new Set<string>();
      while (id && !seen.has(id)) {
        seen.add(id);
        map.set(id, (map.get(id) || 0) + 1);
        id = parentOf.get(id) ?? null;
      }
    }
    return map;
  }, [products, parentOf]);

  const topCategories = useMemo(
    () => categories.filter((c) => !c.parent_category_id),
    [categories],
  );

  const categoryOptions = useMemo(() => {
    const rows: { id: string; label: string }[] = [];
    for (const parent of topCategories) {
      rows.push({ id: parent.id, label: parent.name });
      for (const child of categories.filter((c) => c.parent_category_id === parent.id)) {
        rows.push({ id: child.id, label: `— ${child.name}` });
      }
    }
    return rows;
  }, [categories, topCategories]);

  const visible = useMemo(() => {
    let rows = [...products];
    if (supplierId !== "all") {
      rows = rows.filter((p) => p.business_account_id === supplierId);
    }
    if (unit !== "all") rows = rows.filter((p) => p.unit === unit);
    if (originQ.trim()) {
      const q = originQ.trim().toLowerCase();
      rows = rows.filter((p) => (p.origin ?? "").toLowerCase().includes(q));
    }
    if (maxMoq != null) rows = rows.filter((p) => p.moq <= maxMoq);
    if (maxPrice != null) {
      rows = rows.filter((p) => {
        const price = parsePrice(p);
        return price != null && price <= maxPrice;
      });
    }
    if (inStockOnly || segment === "in_stock") rows = rows.filter(isInStock);
    if (openPriceOnly || segment === "open_price") {
      rows = rows.filter((p) => parsePrice(p) != null);
    }
    if (segment === "new") rows = rows.filter(isNewArrival);
    if (segment === "low_moq") rows = rows.filter((p) => p.moq <= 20);

    if (sort === "name") rows.sort((a, b) => a.name.localeCompare(b.name));
    if (sort === "supplier") {
      rows.sort((a, b) =>
        (a.supplier_name ?? "").localeCompare(b.supplier_name ?? ""),
      );
    }
    return rows;
  }, [
    inStockOnly,
    maxMoq,
    maxPrice,
    openPriceOnly,
    originQ,
    products,
    segment,
    sort,
    supplierId,
    unit,
  ]);

  const segmentCounts = useMemo(() => {
    return {
      all: products.length,
      new: products.filter(isNewArrival).length,
      in_stock: products.filter(isInStock).length,
      open_price: products.filter((p) => parsePrice(p) != null).length,
      low_moq: products.filter((p) => p.moq <= 20).length,
    };
  }, [products]);

  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (query.trim()) n += 1;
    if (categoryId !== "all") n += 1;
    if (supplierId !== "all") n += 1;
    if (unit !== "all") n += 1;
    if (originQ.trim() || draftOrigin.trim()) n += 1;
    if (maxMoq != null) n += 1;
    if (maxPrice != null) n += 1;
    if (inStockOnly) n += 1;
    if (openPriceOnly) n += 1;
    if (segment !== "all") n += 1;
    return n;
  }, [
    categoryId,
    draftOrigin,
    inStockOnly,
    maxMoq,
    maxPrice,
    openPriceOnly,
    originQ,
    query,
    segment,
    supplierId,
    unit,
  ]);

  function clearAll() {
    setPage(1);
    setQuery("");
    setCategoryId("all");
    setSupplierId("all");
    setUnit("all");
    setOriginQ("");
    setDraftOrigin("");
    setSort("supplier");
    setSegment("all");
    setMaxMoq(null);
    setMaxPrice(null);
    setInStockOnly(false);
    setOpenPriceOnly(false);
  }

  function applyRefine() {
    setPage(1);
    setOriginQ(draftOrigin.trim());
  }

  const moqSlider = maxMoq ?? bounds.moqMax;
  const priceSlider = maxPrice ?? bounds.priceMax;

  const segments: { id: Segment; label: string; count: number }[] = [
    { id: "all", label: "All products", count: segmentCounts.all },
    { id: "new", label: "New arrivals", count: segmentCounts.new },
    { id: "in_stock", label: "In stock", count: segmentCounts.in_stock },
    { id: "open_price", label: "Open pricing", count: segmentCounts.open_price },
    { id: "low_moq", label: "Low MOQ", count: segmentCounts.low_moq },
  ];

  return (
    <div className="tb-mkt-explore tb-prod-explore">
      <DirectoryMast
        title="Products"
        lede="Search and browse wholesale products."
        searchId="prod-search"
        searchValue={query}
        searchPlaceholder="Search products, categories, or suppliers…"
        onSearchChange={(v) => {
          setPage(1);
          setQuery(v);
        }}
        stats={[
          { value: loading ? "—" : total, label: "listings" },
          { value: loading ? "—" : suppliers.length, label: "suppliers" },
          {
            value: loading ? "—" : products.filter(isInStock).length,
            label: "in stock",
          },
        ]}
      />

      <div className="tb-mkt-segments tb-prod-segments" role="tablist" aria-label="Product segments">
        {segments.map((seg) => (
          <button
            key={seg.id}
            type="button"
            role="tab"
            aria-selected={segment === seg.id}
            className={segment === seg.id ? "is-active" : ""}
            onClick={() => setSegment(seg.id)}
          >
            <strong>{seg.label}</strong>
            <span>{seg.count}</span>
          </button>
        ))}
      </div>

      <section className="tb-prod-cats" aria-label="Shop by category">
        <button
          type="button"
          className={`tb-prod-cat ${categoryId === "all" ? "is-active" : ""}`}
          onClick={() => {
            setPage(1);
            setCategoryId("all");
          }}
        >
          <span className="tb-prod-cat__mark" aria-hidden>
            ◆
          </span>
          <strong>All Categories</strong>
          <em>{total} products</em>
        </button>
        {topCategories.slice(0, 8).map((c) => (
          <button
            key={c.id}
            type="button"
            className={`tb-prod-cat ${categoryId === c.id ? "is-active" : ""}`}
            onClick={() => {
              setPage(1);
              setCategoryId(c.id);
            }}
          >
            <span className="tb-prod-cat__media" aria-hidden>
              {c.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={mediaUrl(c.image_url)} alt="" />
              ) : (
                c.name.slice(0, 1)
              )}
            </span>
            <strong>{c.name}</strong>
            <em>{categoryCounts.get(c.id) || 0} products</em>
          </button>
        ))}
      </section>

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load products" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-mkt-layout tb-prod-layout">
        <aside className="tb-mkt-filters tb-prod-filters" aria-label="Refine your search">
          <div className="tb-mkt-filters__head tb-prod-filters__head">
            <h2>Refine your search</h2>
            {activeFilterCount > 0 ? (
              <span className="tb-mkt-filters__count">{activeFilterCount} active</span>
            ) : null}
          </div>

          <fieldset className="tb-mkt-filter-block">
            <legend>Category</legend>
            <label className="tb-prod-field">
              <span className="sr-only">Category</span>
              <select
                value={categoryId}
                onChange={(e) => {
                  setPage(1);
                  setCategoryId(e.target.value);
                }}
              >
                <option value="all">All categories</option>
                {categoryOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>

          <fieldset className="tb-mkt-filter-block">
            <legend>Location / origin</legend>
            <label className="tb-prod-field">
              <span className="sr-only">Location</span>
              <select value={draftOrigin} onChange={(e) => setDraftOrigin(e.target.value)}>
                <option value="">All Lebanon</option>
                {LEBANON_REGIONS.map((r) => (
                  <option key={r.value} value={r.label}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>

          <fieldset className="tb-mkt-filter-block">
            <legend>Supplier</legend>
            <label className="tb-prod-field">
              <span className="sr-only">Supplier</span>
              <select
                value={supplierId}
                onChange={(e) => {
                  setPage(1);
                  setSupplierId(e.target.value);
                }}
              >
                <option value="all">All suppliers</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>

          <fieldset className="tb-mkt-filter-block tb-prod-range">
            <legend>
              Unit price
              <em>{maxPrice == null ? "Any" : `Up to $${Math.round(priceSlider)}`}</em>
            </legend>
            <input
              type="range"
              min={0}
              max={bounds.priceMax}
              value={priceSlider}
              onChange={(e) => {
                const v = Number(e.target.value);
                setMaxPrice(v >= bounds.priceMax ? null : v);
              }}
            />
          </fieldset>

          <fieldset className="tb-mkt-filter-block tb-prod-range">
            <legend>
              Maximum MOQ
              <em>{maxMoq == null ? "Any" : `≤ ${moqSlider}`}</em>
            </legend>
            <input
              type="range"
              min={1}
              max={bounds.moqMax}
              value={moqSlider}
              onChange={(e) => {
                const v = Number(e.target.value);
                setMaxMoq(v >= bounds.moqMax ? null : v);
              }}
            />
          </fieldset>

          <fieldset className="tb-mkt-filter-block">
            <legend>Unit</legend>
            <label className="tb-prod-field">
              <span className="sr-only">Unit</span>
              <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                <option value="all">Any unit</option>
                {units.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>

          <fieldset className="tb-mkt-filter-block">
            <legend>Availability</legend>
            <div className="tb-prod-checks">
              <label>
                <input
                  type="checkbox"
                  checked={inStockOnly}
                  onChange={(e) => setInStockOnly(e.target.checked)}
                />
                <span>In stock now</span>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={openPriceOnly}
                  onChange={(e) => setOpenPriceOnly(e.target.checked)}
                />
                <span>Open pricing</span>
              </label>
            </div>
          </fieldset>

          <div className="tb-mkt-filters__actions tb-prod-filters__actions">
            <button type="button" className="tb-mkt-filters__apply tb-prod-filters__apply" onClick={applyRefine}>
              Show {visible.length} result{visible.length === 1 ? "" : "s"}
            </button>
            <button type="button" className="tb-mkt-filters__clear tb-prod-filters__clear" onClick={clearAll}>
              Clear all filters
            </button>
          </div>
        </aside>

        <div className="tb-mkt-main tb-prod-main">
          <section className="tb-prod-directory" aria-labelledby="all-products-title">
            <div className="tb-mkt-directory__head">
              <div>
                <h2 id="all-products-title">All products</h2>
                <p>
                  <span>
                    {visible.length} product{visible.length === 1 ? "" : "s"} found
                  </span>
                  {activeFilterCount > 0 ? (
                    <span>
                      {" "}
                      · {activeFilterCount} filter{activeFilterCount === 1 ? "" : "s"}
                    </span>
                  ) : null}
                  {total ? (
                    <span className="tb-prod-directory__meta-soft"> · of {total} listings</span>
                  ) : null}
                </p>
              </div>
              <div className="tb-mkt-directory__controls">
                <label className="tb-mkt-directory__sort">
                  <span>Sort</span>
                  <select
                    value={sort}
                    onChange={(e) => setSort(e.target.value as typeof sort)}
                  >
                    <option value="supplier">Supplier</option>
                    <option value="updated">Recently updated</option>
                    <option value="name">Name A–Z</option>
                  </select>
                </label>
                <div className="tb-mkt-view tb-prod-view" role="group" aria-label="View mode">
                  <button
                    type="button"
                    className={view === "grid" ? "is-active" : ""}
                    aria-pressed={view === "grid"}
                    onClick={() => setView("grid")}
                  >
                    Grid
                  </button>
                  <button
                    type="button"
                    className={view === "list" ? "is-active" : ""}
                    aria-pressed={view === "list"}
                    onClick={() => setView("list")}
                  >
                    List
                  </button>
                </div>
              </div>
            </div>

            {loading ? (
              <InventorySkeleton entity="products" />
            ) : visible.length === 0 ? (
              <InventoryEmpty
                mark="◎"
                title="No products match"
                body="Try clearing filters or search."
                action={
                  <button type="button" className="tb-btn tb-btn--secondary" onClick={clearAll}>
                    Clear filters
                  </button>
                }
              />
            ) : view === "grid" ? (
              <div className="tb-mkt-grid tb-prod-grid">
                {visible.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            ) : (
              <ul className="tb-prod-list">
                {visible.map((product) => (
                  <li key={product.id}>
                    <ProductRow
                      product={product}
                      categoryLabel={categoryName(product.category_id)}
                    />
                  </li>
                ))}
              </ul>
            )}

            {total > pageSize ? (
              <div className="tb-prod-pager">
                <Pagination
                  page={page}
                  pageCount={Math.max(1, Math.ceil(total / pageSize))}
                  onPageChange={setPage}
                />
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}

function ProductCard({ product }: { product: Product }) {
  const { business, isAuthenticated } = useAuth();
  const canFavorite = !isAuthenticated || business?.type === "buyer";
  const [saved, setSaved] = useState(() => isProductSaved(product.id));

  useEffect(() => {
    if (!canFavorite) return;
    const sync = () => setSaved(isProductSaved(product.id));
    sync();
    window.addEventListener(PRODUCT_FAV_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(PRODUCT_FAV_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [product.id, canFavorite]);

  return (
    <article className="tb-mkt-card tb-prod-card">
      <Link href={ROUTES.inventoryProduct(product.id)} className="tb-prod-card__media">
        {product.primary_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl(product.primary_image_url)} alt="" />
        ) : (
          <span>{product.name.slice(0, 2).toUpperCase()}</span>
        )}
        {isNewArrival(product) ? (
          <em className="tb-prod-badge is-new">New</em>
        ) : isInStock(product) ? (
          <em className="tb-prod-badge is-stock">In stock</em>
        ) : null}
      </Link>
      {canFavorite ? (
        <button
          type="button"
          className={`tb-prod-card__fav${saved ? " is-on" : ""}`}
          aria-label={saved ? "Remove from favorites" : "Add to favorites"}
          aria-pressed={saved}
          onClick={() => {
            const result = toggleProductFavorite({
              id: product.id,
              name: product.name,
              image: product.primary_image_url,
            });
            setSaved(result.saved);
          }}
        >
          {saved ? "♥" : "♡"}
        </button>
      ) : null}
      <div className="tb-prod-card__body">
        <h3>
          <Link href={ROUTES.inventoryProduct(product.id)}>{product.name}</Link>
        </h3>
        <p className="tb-prod-card__meta">
          <strong>{priceLabel(product)}</strong>
          <span>· MOQ {product.moq}</span>
        </p>
        <p className="tb-prod-card__supplier">
          <span className="tb-verified-inline">
            {product.supplier_name ?? "Supplier"}
            <VerifiedBadge
              verified={Boolean(product.supplier_verified)}
              showWhenUnverified={false}
            />
          </span>
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <AddToCartButton
            productId={product.id}
            quantity={Math.max(1, product.moq || 1)}
            stopPropagation
          />
          <Link href={ROUTES.inventoryProduct(product.id)} className="tb-prod-card__cta">
            View →
          </Link>
        </div>
      </div>
    </article>
  );
}

function ProductRow({
  product,
  categoryLabel,
}: {
  product: Product;
  categoryLabel: string;
}) {
  const location =
    [product.supplier_city, product.supplier_governorate].filter(Boolean).join(", ") ||
    product.origin ||
    null;

  return (
    <div className="tb-prod-row">
      <div className="tb-prod-row__media" aria-hidden>
        {product.primary_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl(product.primary_image_url)} alt="" />
        ) : (
          <span>{product.name.slice(0, 2).toUpperCase()}</span>
        )}
      </div>
      <div className="tb-prod-row__main">
        <h3>
          <Link href={ROUTES.inventoryProduct(product.id)}>{product.name}</Link>
        </h3>
        <p>
          {categoryLabel}
          {location ? ` · ${location}` : ""}
          {` · MOQ ${product.moq}`}
        </p>
        <p className="tb-prod-row__supplier">
          <span className="tb-verified-inline">
            {product.supplier_name ?? "Supplier"}
            <VerifiedBadge
              verified={Boolean(product.supplier_verified)}
              showWhenUnverified={false}
            />
          </span>
        </p>
      </div>
      <div className="tb-prod-row__side">
        <strong>{priceLabel(product)}</strong>
        <AddToCartButton
          productId={product.id}
          quantity={Math.max(1, product.moq || 1)}
          tone="soft"
          stopPropagation
        />
        <Link href={ROUTES.inventoryProduct(product.id)}>View →</Link>
      </div>
    </div>
  );
}
