"use client";

import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { AdminProductPhoto, productPrimaryImageUrl } from "@/components/admin/AdminProductPhoto";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { statusTone } from "@/lib/admin/identityDirectory";
import { ApiError } from "@/lib/api/client";
import {
  catalogApi,
  type Category,
  type Product,
  type ProductPrice,
} from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="tb-admin-field">
      <span className="tb-admin-field__label">{label}</span>
      <strong className="tb-admin-field__value">{value || "—"}</strong>
    </div>
  );
}

function AdminProductDetailInner() {
  const params = useParams<{ id: string }>();
  const productId = params.id;

  const [product, setProduct] = useState<Product | null>(null);
  const [category, setCategory] = useState<Category | null>(null);
  const [prices, setPrices] = useState<ProductPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    void Promise.all([
      catalogApi.getProduct(productId),
      catalogApi.listPrices(productId).catch(() => [] as ProductPrice[]),
      catalogApi.listCategories({ page_size: 100 }).catch(() => ({
        data: [] as Category[],
      })),
    ])
      .then(([p, priceRows, cats]) => {
        setProduct(p);
        setPrices(priceRows);
        setCategory(cats.data.find((c) => c.id === p.category_id) ?? null);
      })
      .catch((err) => {
        setProduct(null);
        setError(err instanceof ApiError ? err.message : "Product not found.");
      })
      .finally(() => setLoading(false));
  }, [productId]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (loading) {
    return (
      <AdminPage>
        <p className="tb-ov-crumb mb-3">
          <Link href={ROUTES.admin.products} className="hover:underline">
            Products
          </Link>{" "}
          / Detail
        </p>
        <DirectoryMast title="Product" mark="Platform" size="page" />
        <LoadingEntity entity="product" className="justify-center py-12" />
      </AdminPage>
    );
  }

  if (error || !product) {
    return (
      <AdminPage>
        <p className="tb-ov-crumb mb-3">
          <Link href={ROUTES.admin.products} className="hover:underline">
            Products
          </Link>{" "}
          / Detail
        </p>
        <DirectoryMast title="Product" mark="Platform" size="page" />
        <FeedbackBanner tone="error" title="Product unavailable">
          {error ?? "Not found"}
        </FeedbackBanner>
        <AdminAct href={ROUTES.admin.products} tone="ghost">
          ← Back to products
        </AdminAct>
      </AdminPage>
    );
  }

  const heroSrc = productPrimaryImageUrl(product);
  const inv = product.inventory;
  const activePrices = prices.filter((p) => p.is_active);

  return (
    <div className="tb-cc tb-admin-product">
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.home} className="hover:underline">
          Admin
        </Link>{" "}
        /{" "}
        <Link href={ROUTES.admin.products} className="hover:underline">
          Products
        </Link>{" "}
        / {product.name}
      </p>

      <DirectoryMast
        title={product.name}
        mark="Platform"
        size="page"
        actions={
          <div className="flex flex-wrap gap-2">
            <AdminAct href={ROUTES.admin.products} tone="soft">
              ← All products
            </AdminAct>
            <AdminAct
              href={ROUTES.admin.businessDetail(product.business_account_id)}
              tone="go"
              arrow
            >
              Supplier profile
            </AdminAct>
          </div>
        }
      />

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="tb-status" data-tone={statusTone(product.status)}>
          {product.status}
        </span>
        <span className="tb-admin-chip">{product.sku}</span>
        {category ? <span className="tb-admin-chip">{category.name}</span> : null}
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <section className="tb-panel overflow-hidden p-0">
          <AdminProductPhoto url={heroSrc} alt={product.name} size="hero" />
        </section>

        <div className="space-y-5">
          <section className="tb-panel p-5">
            <h2 className="tb-section-label">Product profile</h2>
            <p className="tb-admin-lede">Core commercial identity</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field
                label="Supplier"
                value={product.supplier_name || "—"}
              />
              <Field label="SKU" value={product.sku} />
              <Field label="Category" value={category?.name || "—"} />
              <Field label="Origin" value={product.origin || "—"} />
              <Field label="Unit" value={product.unit} />
              <Field label="MOQ" value={String(product.moq)} />
              <Field label="Lead time" value={`${product.lead_time_days} days`} />
              <Field label="Status" value={product.status} />
            </div>
            {product.description ? (
              <p className="tb-admin-body mt-4">{product.description}</p>
            ) : null}
            <div className="mt-4">
              <AdminAct
                href={ROUTES.admin.businessDetail(product.business_account_id)}
                tone="go"
                arrow
              >
                Open supplier company
              </AdminAct>
            </div>
          </section>

          <section className="tb-panel p-5">
            <h2 className="tb-section-label">Inventory snapshot</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <Field label="Available" value={inv?.available_quantity ?? "—"} />
              <Field label="Reserved" value={inv?.reserved_quantity ?? "—"} />
              <Field
                label="Updated"
                value={
                  inv?.updated_at
                    ? new Date(inv.updated_at).toLocaleString()
                    : "—"
                }
              />
            </div>
          </section>
        </div>
      </div>

      <section className="tb-panel mt-5 p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="tb-section-label">Wholesale tiers</h2>
            <p className="tb-admin-lede">Quantity ranges that apply at catalog price</p>
          </div>
          <p className="tb-admin-copy">
            {activePrices.length} active · {prices.length} total
          </p>
        </div>

        {prices.length === 0 ? (
          <div className="tb-empty mt-4">
            <h3>No price tiers</h3>
            <p>This listing has no wholesale price ranges yet.</p>
          </div>
        ) : (
          <ul className="tb-cc-cards mt-4">
            {prices.map((tier) => (
              <li key={tier.id}>
                <p className="tb-summary-label">Qty range</p>
                <strong>
                  {tier.min_quantity}
                  {tier.max_quantity != null ? ` – ${tier.max_quantity}` : "+"}
                </strong>
                <p className="tb-meta">
                  {tier.currency} {tier.unit_price}
                </p>
                <span
                  className="tb-status"
                  data-tone={statusTone(tier.is_active ? "active" : "inactive")}
                >
                  {tier.is_active ? "active" : "inactive"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="tb-panel mt-5 p-5">
        <h2 className="tb-section-label">Record</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field
            label="Created"
            value={
              product.created_at
                ? new Date(product.created_at).toLocaleString()
                : "—"
            }
          />
          <Field
            label="Updated"
            value={
              product.updated_at
                ? new Date(product.updated_at).toLocaleString()
                : "—"
            }
          />
        </div>
      </section>
    </div>
  );
}

export default function AdminProductDetailPage() {
  return (
    <PermissionGate
      permission="products.read"
      fallbackTitle="Products are restricted"
      fallbackDescription="Platform staff access is required to inspect listings."
    >
      <AdminProductDetailInner />
    </PermissionGate>
  );
}
