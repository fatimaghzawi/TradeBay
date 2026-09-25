"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import {
  InventoryEmpty,
  InventoryFoot,
  InventoryKpi,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

function OverviewInner() {
  const { hasPermission, business } = useAuth();
  const isSupplier = business?.type === "supplier";
  const canManage = hasPermission("products.manage") && isSupplier;
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const ownId = isSupplier ? business?.id : undefined;
    void Promise.all([
      catalogApi.listProducts({
        include_details: true,
        page_size: 100,
        supplier_business_id: ownId,
        status: isSupplier ? undefined : "active",
      }),
      catalogApi.listCategories({ page_size: 100 }),
    ])
      .then(([prod, cats]) => {
        const rows = ownId
          ? prod.data.filter((p) => p.business_account_id === ownId)
          : prod.data;
        setProducts(rows);
        setCategories(cats.data);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load overview.");
      })
      .finally(() => setLoading(false));
  }, [business?.id, isSupplier]);

  const stats = useMemo(() => {
    const activeCats = categories.filter((c) => c.is_active).length;
    const activeProducts = products.filter((p) => p.status === "active").length;
    const lowStock = products.filter(
      (p) => Number(p.inventory?.available_quantity ?? 0) < (p.moq || 1),
    );
    let available = 0;
    let reserved = 0;
    let stockValue = 0;
    for (const p of products) {
      const avail = Number(p.inventory?.available_quantity ?? 0);
      const res = Number(p.inventory?.reserved_quantity ?? 0);
      available += avail;
      reserved += res;
      const price = Number(p.prices?.[0]?.unit_price ?? 0);
      if (Number.isFinite(price)) stockValue += avail * price;
    }
    return {
      total: products.length,
      activeProducts,
      activeCats,
      lowStock: lowStock.length,
      stockValue,
      available,
      reserved,
      lowItems: lowStock.slice(0, 6),
    };
  }, [categories, products]);

  const byCategory = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of products) {
      map.set(p.category_id, (map.get(p.category_id) ?? 0) + 1);
    }
    const rows = Array.from(map.entries())
      .map(([id, count]) => ({
        id,
        name: categories.find((c) => c.id === id)?.name ?? "Uncategorized",
        count,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
    const max = Math.max(1, ...rows.map((r) => r.count));
    return { rows, max };
  }, [categories, products]);

  const featured = useMemo(() => {
    return [...products]
      .filter((p) => p.status === "active")
      .sort((a, b) => {
        const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return tb - ta;
      })
      .slice(0, 6);
  }, [products]);

  const supplierShortcuts = [
    { href: ROUTES.inventoryProducts, label: "Products", hint: "Search & filter SKUs" },
    { href: ROUTES.inventoryCategories, label: "Categories", hint: "Taxonomy tree" },
    { href: ROUTES.inventoryStock, label: "Stock", hint: "Available vs reserved" },
    { href: ROUTES.inventoryMovements, label: "Movements", hint: "Stock history" },
  ];

  const buyerShortcuts = [
    { href: ROUTES.inventoryProducts, label: "All products", hint: "Search wholesale listings" },
    { href: ROUTES.inventoryCategories, label: "Categories", hint: "Browse by taxonomy" },
    { href: ROUTES.procurement, label: "Procurement", hint: "Start an RFQ / order" },
    { href: ROUTES.quotations, label: "Quotations", hint: "Track supplier quotes" },
  ];

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title={isSupplier ? "My catalog" : "Browse wholesale"}
        description={
          isSupplier
            ? "Manage the products you list on TradeBay — stock and listing health."
            : "Browse wholesale products from suppliers."
        }
        meta={
          <>
            <span className="tb-inv-chip">{stats.total} products</span>
            <span className="tb-inv-chip">{stats.activeCats} categories</span>
            {isSupplier && stats.lowStock > 0 ? (
              <span className="tb-inv-chip" data-tone="warn">
                {stats.lowStock} low stock
              </span>
            ) : null}
          </>
        }
        actions={
          canManage ? (
            <InventoryLinkBtn href={ROUTES.inventoryProductNew} tone="accent">
              + Add product
            </InventoryLinkBtn>
          ) : !isSupplier ? (
            <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="accent">
              Browse products →
            </InventoryLinkBtn>
          ) : null
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Overview failed">
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <InventoryPanel>
          <InventorySkeleton entity="inventory" />
        </InventoryPanel>
      ) : (
        <>
          <div className="tb-inv-kpi-grid">
            <InventoryKpi
              index={0}
              label="Products"
              value={stats.total}
              hint={`${stats.activeProducts} live on marketplace`}
              icon="◎"
            />
            <InventoryKpi
              index={1}
              label="Categories"
              value={stats.activeCats}
              hint={`${categories.length} taxonomy nodes`}
              tone="accent"
              icon="☰"
            />
            {isSupplier ? (
              <>
                <InventoryKpi
                  index={2}
                  label="Low stock"
                  value={stats.lowStock}
                  hint="Below MOQ"
                  tone={stats.lowStock > 0 ? "warn" : "ok"}
                  icon="!"
                />
                <InventoryKpi
                  index={3}
                  label="On hand"
                  value={stats.available.toLocaleString()}
                  hint={
                    stats.stockValue > 0
                      ? `≈ $${stats.stockValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                      : `${stats.reserved} reserved`
                  }
                  tone="ok"
                  icon="$"
                />
              </>
            ) : (
              <>
                <InventoryKpi
                  index={2}
                  label="Ready to order"
                  value={stats.activeProducts}
                  tone="ok"
                  icon="✓"
                />
                <InventoryKpi
                  index={3}
                  label="Next step"
                  value="RFQ"
                  tone="accent"
                  icon="→"
                />
              </>
            )}
          </div>

          <nav className="tb-inv-quick" aria-label={isSupplier ? "Inventory shortcuts" : "Marketplace shortcuts"}>
            {(isSupplier ? supplierShortcuts : buyerShortcuts).map((item) => (
              <Link key={item.href} href={item.href} className="tb-inv-quick-link">
                <strong>{item.label}</strong>
                <span>{item.hint}</span>
              </Link>
            ))}
          </nav>

          <div className="tb-inv-split">
            <InventoryPanel
              title={isSupplier ? "Products by category" : "Shop by category"}
              subtitle={
                isSupplier
                  ? "Distribution across your active taxonomy"
                  : "Find wholesale goods by category"
              }
            >
              {byCategory.rows.length === 0 ? (
                <InventoryEmpty
                  mark="◎"
                  title="No products yet"
                  body={
                    canManage
                      ? "Create your first listing to populate this chart."
                      : "Nothing in the marketplace to chart yet."
                  }
                  action={
                    canManage ? (
                      <InventoryLinkBtn href={ROUTES.inventoryProductNew} tone="accent">
                        Add product
                      </InventoryLinkBtn>
                    ) : null
                  }
                />
              ) : (
                <div className="tb-inv-chart">
                  {byCategory.rows.map((row, i) => (
                    <Link
                      key={row.id}
                      href={`${ROUTES.inventoryProducts}?category=${row.id}`}
                      className="tb-inv-chart-col"
                    >
                      <span className="tb-inv-chart-value">{row.count}</span>
                      <div
                        className="tb-inv-chart-bar"
                        style={{
                          height: `${Math.max(16, Math.round((row.count / byCategory.max) * 150))}px`,
                          animationDelay: `${i * 70}ms`,
                        }}
                        title={`${row.name}: ${row.count}`}
                      />
                      <span className="tb-inv-chart-label" title={row.name}>
                        {row.name}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </InventoryPanel>

            <InventoryPanel
              title={isSupplier ? "Recent activity" : "Featured by supplier"}
              subtitle={
                isSupplier
                  ? "Latest listing updates"
                  : "Card browse — open a product to review tiers and order"
              }
              action={
                <Link
                  href={ROUTES.inventoryProducts}
                  className="text-xs font-bold text-link hover:underline"
                >
                  View all
                </Link>
              }
            >
              {!isSupplier ? (
                <div className="tb-mkt-grid-compact">
                  {featured.length === 0 ? (
                    <p className="py-4 text-sm text-muted-foreground">No products to show yet.</p>
                  ) : (
                    featured.map((p) => (
                      <Link
                        key={p.id}
                        href={ROUTES.inventoryProduct(p.id)}
                        className="tb-mkt-card"
                      >
                        <div className="tb-mkt-card-media" aria-hidden>
                          {p.primary_image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(p.primary_image_url)} alt="" />
                          ) : (
                            <span>{p.name.slice(0, 2).toUpperCase()}</span>
                          )}
                        </div>
                        <div className="tb-mkt-card-body">
                          <p className="tb-mkt-card-supplier">
                            {p.supplier_logo_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={mediaUrl(p.supplier_logo_url)}
                                alt=""
                                className="tb-mkt-card-supplier-logo"
                              />
                            ) : null}
                            <span>{p.supplier_name ?? "Supplier"}</span>
                          </p>
                          <h3 className="tb-mkt-card-title">{p.name}</h3>
                          <p className="tb-mkt-card-meta">
                            MOQ {p.moq}
                            {p.origin ? ` · ${p.origin}` : ""}
                          </p>
                          <div className="tb-mkt-card-foot">
                            <strong>
                              {p.prices?.[0]
                                ? `${p.prices[0].currency} ${p.prices[0].unit_price}`
                                : "Ask for quote"}
                            </strong>
                            <span>Open →</span>
                          </div>
                        </div>
                      </Link>
                    ))
                  )}
                </div>
              ) : (
              <div className="tb-inv-activity">
                {featured.length === 0 ? (
                  <p className="py-4 text-sm text-muted-foreground">No products to show yet.</p>
                ) : (
                  featured.map((p) => (
                    <Link
                      key={p.id}
                      href={ROUTES.inventoryProduct(p.id)}
                      className="tb-inv-activity-item"
                    >
                      {p.primary_image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={mediaUrl(p.primary_image_url)}
                          alt=""
                          className="h-9 w-9 rounded-xl object-cover"
                        />
                      ) : (
                        <span className="tb-inv-activity-dot" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-heading">{p.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {p.status === "draft" ? "Draft touched" : "Listing updated"}
                          {p.updated_at
                            ? ` · ${new Date(p.updated_at).toLocaleString()}`
                            : ""}
                        </p>
                      </div>
                      <StatusBadge status={p.status} />
                    </Link>
                  ))
                )}
              </div>
              )}
            </InventoryPanel>
          </div>

          {isSupplier && stats.lowItems.length > 0 ? (
            <InventoryPanel
              title="Needs attention"
              subtitle="These SKUs are below their minimum order quantity"
            >
              <div className="tb-inv-table-wrap">
                <table className="tb-inv-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>SKU</th>
                      <th>Available</th>
                      <th>MOQ</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.lowItems.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <Link
                            href={ROUTES.inventoryProduct(p.id)}
                            className="font-semibold text-heading hover:underline"
                          >
                            {p.name}
                          </Link>
                        </td>
                        <td className="font-mono text-xs">{p.sku}</td>
                        <td className="font-semibold text-destructive">
                          {p.inventory?.available_quantity ?? "0"}
                        </td>
                        <td>{p.moq}</td>
                        <td>
                          <StatusBadge status={p.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <InventoryFoot
                left={`${stats.lowItems.length} items need restock`}
                right={
                  <InventoryLinkBtn href={ROUTES.inventoryStock} tone="soft">
                    Open stock →
                  </InventoryLinkBtn>
                }
              />
            </InventoryPanel>
          ) : null}
        </>
      )}
    </div>
  );
}

export default function InventoryOverviewPage() {
  return (
    <PermissionGate permission="products.read">
      <OverviewInner />
    </PermissionGate>
  );
}
