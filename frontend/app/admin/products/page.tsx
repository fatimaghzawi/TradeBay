"use client";

import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { AdminProductPhoto, productPrimaryImageUrl } from "@/components/admin/AdminProductPhoto";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Pagination } from "@/components/ui/Pagination";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { statusTone } from "@/lib/admin/identityDirectory";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

type StatusFilter = "all" | "active" | "draft" | "inactive";

function priceLabel(product: Product): string {
  const tier = product.prices?.find((p) => p.is_active) ?? product.prices?.[0];
  if (!tier) return "No price";
  return `${tier.unit_price} ${tier.currency}`;
}

function stockLabel(product: Product): string {
  if (!product.inventory) return "—";
  return `${product.inventory.available_quantity} avail`;
}

function AdminProductsInner() {
  const searchParams = useSearchParams();
  const qFromUrl = searchParams.get("q") ?? "";
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(qFromUrl);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const categoryName = useMemo(() => {
    const map = new Map(categories.map((c) => [c.id, c.name]));
    return (id: string) => map.get(id) ?? "—";
  }, [categories]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    void Promise.all([
      catalogApi.listProducts({
        q: query.trim() || undefined,
        status: status === "all" ? undefined : status,
        category_id: categoryId || undefined,
        include_details: true,
        page,
        page_size: pageSize,
      }),
      catalogApi.listCategories({ page_size: 100 }).catch(() => ({
        data: [] as Category[],
      })),
    ])
      .then(([prod, cats]) => {
        setProducts(prod.data);
        setTotal(prod.meta.total);
        setCategories(cats.data);
      })
      .catch((err) => {
        setProducts([]);
        setTotal(0);
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load products.",
        );
      })
      .finally(() => setLoading(false));
  }, [categoryId, page, pageSize, query, status]);

  useEffect(() => {
    setQuery(qFromUrl);
    setPage(1);
  }, [qFromUrl]);

  useEffect(() => {
    const handle = window.setTimeout(() => load(), query ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [load, query]);

  useEffect(() => {
    setPage(1);
  }, [status, categoryId, query, pageSize]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);
  const activeOnPage = products.filter((p) => p.status === "active").length;

  return (
    <AdminPage>
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.home} className="hover:underline">
          Admin
        </Link>{" "}
        / Catalog / Products
      </p>
      <DirectoryMast title="Products" mark="Platform" size="page" />

      {error ? (
        <div className="mt-4">
          <FeedbackBanner
            tone="error"
            title="Couldn’t load products"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      <div className="tb-summary">
        {[
          { label: "Matching", value: total },
          { label: "This page", value: products.length },
          { label: "Active (page)", value: activeOnPage },
        ].map((stat) => (
          <div key={stat.label} className="tb-summary-item">
            <p className="tb-summary-label">{stat.label}</p>
            <p className="tb-summary-value tb-num">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="tb-toolbar flex-wrap gap-y-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search product name…"
          className="h-9 w-full max-w-sm border-0 border-b border-input bg-transparent px-0 text-sm outline-none focus:border-ring"
        />
        {(
          [
            ["all", "All"],
            ["active", "Active"],
            ["draft", "Draft"],
            ["inactive", "Inactive"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className="tb-filter"
            data-active={status === key}
            onClick={() => setStatus(key)}
          >
            {label}
          </button>
        ))}
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="h-9 rounded-lg border border-input bg-card px-2 text-sm"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          className="h-9 rounded-lg border border-input bg-card px-2 text-sm"
        >
          {[10, 20, 50].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <LoadingEntity entity="products" className="mt-6" />
      ) : products.length === 0 ? (
        <div className="tb-empty mt-6">
          <h3>No products</h3>
          <p>No supplier listings match the current filters.</p>
        </div>
      ) : (
        <ul className="tb-data mt-4">
          {products.map((product) => {
            const src = productPrimaryImageUrl(product);
            return (
              <li
                key={product.id}
                className="tb-data-row grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto]"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <AdminProductPhoto url={src} alt={product.name} />
                  <div className="min-w-0">
                    <Link
                      href={ROUTES.admin.productDetail(product.id)}
                      className="font-semibold text-foreground hover:underline"
                    >
                      {product.name}
                    </Link>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {product.sku}
                      {` · ${categoryName(product.category_id)}`}
                      {` · MOQ ${product.moq} ${product.unit}`}
                    </p>
                  </div>
                </div>
                <div className="min-w-0 text-sm text-muted-foreground">
                  <p className="flex items-center gap-2">
                    {product.supplier_logo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={mediaUrl(product.supplier_logo_url)}
                        alt=""
                        className="h-6 w-6 shrink-0 rounded-md object-contain bg-muted"
                      />
                    ) : null}
                    <Link
                      href={ROUTES.admin.businessDetail(product.business_account_id)}
                      className="font-semibold text-heading hover:underline"
                    >
                      {product.supplier_name || "Supplier"}
                    </Link>
                  </p>
                  <p className="mt-0.5">
                    {priceLabel(product)} · {stockLabel(product)}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="tb-status" data-tone={statusTone(product.status)}>
                    {product.status}
                  </span>
                  <AdminAct href={ROUTES.admin.productDetail(product.id)} tone="go" arrow>
                    Open
                  </AdminAct>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {total > 0 ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="tb-meta">
            {total} matching · showing page {page} of {pageCount}
          </p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}
    </AdminPage>
  );
}

export default function AdminProductsPage() {
  return (
    <PermissionGate
      permission="products.read"
      fallbackTitle="Products are restricted"
      fallbackDescription="Platform staff access is required to view supplier listings."
    >
      <Suspense fallback={<LoadingEntity entity="products" className="p-8" />}>
        <AdminProductsInner />
      </Suspense>
    </PermissionGate>
  );
}
