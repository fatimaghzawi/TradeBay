"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { GuestExploreBanner } from "@/components/auth/GuestExploreBanner";
import { BuyerMarketplace } from "@/components/catalog/BuyerMarketplace";
import {
  InventoryEmpty,
  InventoryFoot,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  InventoryToolbar,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Pagination } from "@/components/ui/Pagination";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

function priceLabel(p: Product) {
  const tier = p.prices?.[0];
  if (!tier) return "Ask for quote";
  return `${tier.currency} ${tier.unit_price}`;
}

function SupplierProductsTable({
  products,
  categories,
  query,
  setQuery,
  categoryId,
  setCategoryId,
  status,
  setStatus,
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
  canManage,
}: {
  products: Product[];
  categories: Category[];
  query: string;
  setQuery: (v: string) => void;
  categoryId: string;
  setCategoryId: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
  unit: string;
  setUnit: (v: string) => void;
  originQ: string;
  setOriginQ: (v: string) => void;
  sort: "updated" | "name" | "stock";
  setSort: (v: "updated" | "name" | "stock") => void;
  page: number;
  setPage: (v: number) => void;
  total: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  setError: (v: string | null) => void;
  units: string[];
  canManage: boolean;
}) {
  const categoryName = (id: string) =>
    categories.find((c) => c.id === id)?.name ?? "—";

  const visible = useMemo(() => {
    let rows = [...products];
    if (unit !== "all") rows = rows.filter((p) => p.unit === unit);
    if (originQ.trim()) {
      const q = originQ.trim().toLowerCase();
      rows = rows.filter((p) => (p.origin ?? "").toLowerCase().includes(q));
    }
    if (sort === "name") rows.sort((a, b) => a.name.localeCompare(b.name));
    if (sort === "stock") {
      rows.sort(
        (a, b) =>
          Number(b.inventory?.available_quantity ?? 0) -
          Number(a.inventory?.available_quantity ?? 0),
      );
    }
    return rows;
  }, [originQ, products, sort, unit]);

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="My products"
        description="Create, edit, and activate your wholesale listings. Only products you added appear here."
        meta={total > 0 ? <span className="tb-inv-chip">{total} of yours</span> : null}
        actions={
          canManage ? (
            <InventoryLinkBtn href={ROUTES.inventoryProductNew} tone="accent">
              + Add Product
            </InventoryLinkBtn>
          ) : null
        }
      />

      <InventoryPanel title="Your listings" subtitle="Filter by status, category, origin, or stock">
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setPage(1);
              setQuery(e.target.value);
            }}
            placeholder="Search products…"
            className="min-w-[12rem] flex-1"
          />
          <select
            value={categoryId}
            onChange={(e) => {
              setPage(1);
              setCategoryId(e.target.value);
            }}
          >
            <option value="all">Category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
          >
            <option value="all">Status</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <select value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="all">Unit</option>
            {units.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
          <input
            type="search"
            value={originQ}
            onChange={(e) => setOriginQ(e.target.value)}
            placeholder="Origin…"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as typeof sort)}
          >
            <option value="updated">Recent</option>
            <option value="name">Name</option>
            <option value="stock">Stock</option>
          </select>
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Couldn’t load products" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="products" />
        ) : visible.length === 0 ? (
          <InventoryEmpty
            mark="◎"
            title={canManage ? "No products in your catalog yet" : "No products match"}
            body={
              canManage
                ? "Add your first listing to start selling on TradeBay."
                : "Try clearing filters to broaden the search."
            }
            action={
              canManage ? (
                <InventoryLinkBtn href={ROUTES.inventoryProductNew} tone="accent">
                  + Add Product
                </InventoryLinkBtn>
              ) : null
            }
          />
        ) : (
          <div className="tb-inv-table-wrap">
            <table className="tb-inv-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>Stock</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        {product.primary_image_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={mediaUrl(product.primary_image_url)}
                            alt=""
                            className="tb-inv-thumb object-cover"
                          />
                        ) : (
                          <span className="tb-inv-thumb">
                            {product.name.slice(0, 2).toUpperCase()}
                          </span>
                        )}
                        <div>
                          <Link
                            href={ROUTES.inventoryProduct(product.id)}
                            className="font-semibold text-[#0d3b2a] hover:underline"
                          >
                            {product.name}
                          </Link>
                          <p className="text-xs text-[#5a6a62]">
                            MOQ {product.moq}
                            {product.origin ? ` · ${product.origin}` : ""}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="font-mono text-xs">{product.sku}</td>
                    <td>{categoryName(product.category_id)}</td>
                    <td className="font-semibold">{priceLabel(product)}</td>
                    <td>
                      <span className="font-semibold">
                        {product.inventory?.available_quantity ?? "—"}
                      </span>
                      <span className="text-[#5a6a62]"> avail</span>
                    </td>
                    <td>
                      <StatusBadge status={product.status} />
                    </td>
                    <td>
                      <Link
                        href={ROUTES.inventoryProduct(product.id)}
                        className="text-sm font-bold text-[#1a6b4f] hover:underline"
                      >
                        {canManage ? "Manage →" : "Open →"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > 0 ? (
          <InventoryFoot
            left={`Page ${page} · ${total} products`}
            right={
              <Pagination
                page={page}
                pageCount={Math.max(1, Math.ceil(total / pageSize))}
                onPageChange={setPage}
              />
            }
          />
        ) : null}
      </InventoryPanel>
    </div>
  );
}

function ProductsInner() {
  const { hasPermission, business } = useAuth();
  const searchParams = useSearchParams();
  const isSupplier = business?.type === "supplier";
  const canManage = hasPermission("products.manage") && isSupplier;

  const initialCategory = searchParams.get("category")?.trim() || "all";
  const initialSupplier = searchParams.get("supplier")?.trim() || "all";
  const initialQuery = searchParams.get("q")?.trim() || "";

  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [query, setQuery] = useState(initialQuery);
  const [status, setStatus] = useState(isSupplier ? "all" : "active");
  const [categoryId, setCategoryId] = useState(initialCategory);
  const [supplierId, setSupplierId] = useState(initialSupplier);
  const [unit, setUnit] = useState("all");
  const [originQ, setOriginQ] = useState("");
  const [sort, setSort] = useState<"updated" | "name" | "stock" | "supplier">(
    isSupplier ? "updated" : "supplier",
  );
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = isSupplier ? 20 : 100;

  useEffect(() => {
    const fromUrl = searchParams.get("category")?.trim();
    if (fromUrl) {
      setCategoryId(fromUrl);
      setPage(1);
    }
    const supplierFromUrl = searchParams.get("supplier")?.trim();
    if (supplierFromUrl) {
      setSupplierId(supplierFromUrl);
      setPage(1);
    }
    const qFromUrl = searchParams.get("q");
    if (qFromUrl !== null) {
      setQuery(qFromUrl.trim());
      setPage(1);
    }
  }, [searchParams]);

  useEffect(() => {
    void catalogApi
      .listCategories({ active_only: !isSupplier, page_size: 100 })
      .then((result) => setCategories(result.data))
      .catch(() => setCategories([]));
  }, [isSupplier]);

  const reload = useCallback(() => {
    if (isSupplier && !business?.id) {
      setProducts([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    void catalogApi
      .listProducts({
        q: query.trim() || undefined,
        status: status === "all" ? undefined : status,
        category_id: categoryId === "all" ? undefined : categoryId,
        supplier_business_id: isSupplier
          ? business!.id
          : supplierId !== "all"
            ? supplierId
            : undefined,
        include_details: true,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        const rows = isSupplier
          ? result.data.filter((p) => p.business_account_id === business!.id)
          : result.data;
        setProducts(rows);
        setTotal(result.meta.total);
      })
      .catch((err) => {
        setProducts([]);
        setTotal(0);
        setError(err instanceof ApiError ? err.message : "Couldn't load products.");
      })
      .finally(() => setLoading(false));
  }, [business, categoryId, isSupplier, page, pageSize, query, status, supplierId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const units = useMemo(() => {
    const set = new Set(products.map((p) => p.unit).filter(Boolean));
    return Array.from(set).sort();
  }, [products]);

  if (!isSupplier) {
    return (
      <>
        <GuestExploreBanner action="sync favorites and request quotes" />
        <BuyerMarketplace
          products={products}
          categories={categories}
          query={query}
          setQuery={setQuery}
          categoryId={categoryId}
          setCategoryId={setCategoryId}
          supplierId={supplierId}
          setSupplierId={setSupplierId}
          unit={unit}
          setUnit={setUnit}
          originQ={originQ}
          setOriginQ={setOriginQ}
          sort={sort === "stock" ? "supplier" : sort}
          setSort={(v) => setSort(v)}
          page={page}
          setPage={setPage}
          total={total}
          pageSize={pageSize}
          loading={loading}
          error={error}
          setError={setError}
          units={units}
        />
      </>
    );
  }

  return (
    <SupplierProductsTable
      products={products}
      categories={categories}
      query={query}
      setQuery={setQuery}
      categoryId={categoryId}
      setCategoryId={setCategoryId}
      status={status}
      setStatus={setStatus}
      unit={unit}
      setUnit={setUnit}
      originQ={originQ}
      setOriginQ={setOriginQ}
      sort={sort === "supplier" ? "updated" : sort}
      setSort={(v) => setSort(v)}
      page={page}
      setPage={setPage}
      total={total}
      pageSize={pageSize}
      loading={loading}
      error={error}
      setError={setError}
      units={units}
      canManage={canManage}
    />
  );
}

export default function InventoryProductsPage() {
  return (
    <PermissionGate permission="products.read" allowGuest>
      <Suspense
        fallback={<LoadingEntity entity="products" className="p-6" />}
      >
        <ProductsInner />
      </Suspense>
    </PermissionGate>
  );
}
