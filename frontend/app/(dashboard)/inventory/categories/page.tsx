"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import {
  InventoryBtn,
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  InventoryToolbar,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { categoryCreateSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { FieldError } from "@/components/ui/FormField";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { BusyText } from "@/components/ui/LoadingState";

function BuyerShopByCategory() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    void Promise.all([
      catalogApi.listCategories({ active_only: true, page_size: 100 }),
      catalogApi
        .listProducts({ status: "active", include_details: true, page_size: 100 })
        .catch(() => ({ data: [] as Product[] })),
    ])
      .then(([cats, prod]) => {
        setCategories(cats.data);
        setProducts(prod.data);
        setError(null);
      })
      .catch((err) => {
        setCategories([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load categories.");
      })
      .finally(() => setLoading(false));
  }, []);

  const productCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of products) {
      map.set(p.category_id, (map.get(p.category_id) ?? 0) + 1);
    }
    return map;
  }, [products]);

  
  const countWithChildren = useCallback(
    (catId: string): number => {
      let total = productCount.get(catId) ?? 0;
      for (const child of categories) {
        if (child.parent_category_id === catId) {
          total += countWithChildren(child.id);
        }
      }
      return total;
    },
    [categories, productCount],
  );

  const roots = useMemo(() => {
    let rows = categories.filter((c) => c.is_active);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      rows = rows.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.description ?? "").toLowerCase().includes(q),
      );
    }
    const rootRows = rows.filter(
      (c) => !c.parent_category_id || !categories.some((x) => x.id === c.parent_category_id),
    );
    return rootRows
      .map((c) => ({
        ...c,
        listingCount: countWithChildren(c.id),
        children: categories.filter(
          (child) => child.parent_category_id === c.id && child.is_active,
        ),
      }))
      .filter((c) => c.listingCount > 0 || !query.trim())
      .sort((a, b) => b.listingCount - a.listingCount || a.name.localeCompare(b.name));
  }, [categories, countWithChildren, query]);

  const totalListings = products.length;

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow="Marketplace"
        title="Shop by category"
        description="Browse by category."
        meta={
          <>
            <span className="tb-inv-chip">{roots.length} categories</span>
            <span className="tb-inv-chip">{totalListings} listings</span>
          </>
        }
        actions={
          <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="soft">
            All products →
          </InventoryLinkBtn>
        }
      />

      <InventoryPanel
        title="Browse the aisle"
        subtitle={undefined}
      >
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search categories…"
            className="min-w-[14rem] flex-1"
          />
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Couldn't load" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="categories" />
        ) : roots.length === 0 ? (
          <InventoryEmpty
            mark="☰"
            title="No categories to shop"
            body="When suppliers list products, categories will appear here for quick browsing."
            action={
              <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="accent">
                Browse all products
              </InventoryLinkBtn>
            }
          />
        ) : (
          <div className="tb-mkt-grid">
            {roots.map((cat) => (
              <article key={cat.id} className="tb-mkt-card tb-cat-shop-card">
                <Link
                  href={`${ROUTES.inventoryProducts}?category=${encodeURIComponent(cat.id)}`}
                  className="tb-cat-shop-main"
                >
                  <div className="tb-mkt-card-media" aria-hidden>
                    {cat.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(cat.image_url)} alt="" />
                    ) : (
                      <span>{cat.name.slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div className="tb-mkt-card-body">
                    {cat.image_url ? (
                      <h3 className="sr-only">{cat.name}</h3>
                    ) : (
                      <h3 className="tb-mkt-card-title">{cat.name}</h3>
                    )}
                    <p className="tb-mkt-card-meta">
                      {cat.image_url
                        ? `${cat.listingCount} listing${cat.listingCount === 1 ? "" : "s"} ready to order`
                        : cat.description?.trim() ||
                          `${cat.listingCount} product${cat.listingCount === 1 ? "" : "s"} ready to order`}
                    </p>
                    <div className="tb-mkt-card-foot">
                      <strong>
                        {cat.listingCount} listing{cat.listingCount === 1 ? "" : "s"}
                      </strong>
                      <span>Shop →</span>
                    </div>
                  </div>
                </Link>
                {cat.children.length > 0 ? (
                  <ul className="tb-cat-shop-subs">
                    {cat.children.map((child) => {
                      const childCount = countWithChildren(child.id);
                      return (
                        <li key={child.id}>
                          <Link
                            href={`${ROUTES.inventoryProducts}?category=${encodeURIComponent(child.id)}`}
                          >
                            <span>{child.name}</span>
                            <span className="tb-cat-shop-sub-count">{childCount}</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </InventoryPanel>
    </div>
  );
}

function SupplierCategoriesView() {
  const { business } = useAuth();
  const ownId = business?.id;
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!ownId) {
      setProducts([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    void Promise.all([
      catalogApi.listCategories({ active_only: true, page_size: 100 }),
      catalogApi
        .listProducts({
          include_details: true,
          page_size: 100,
          supplier_business_id: ownId,
        })
        .catch(() => ({ data: [] as Product[] })),
    ])
      .then(([cats, prod]) => {
        setCategories(cats.data);
        setProducts(prod.data.filter((p) => p.business_account_id === ownId));
        setError(null);
      })
      .catch((err) => {
        setCategories([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load categories.");
      })
      .finally(() => setLoading(false));
  }, [ownId]);

  const productCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of products) {
      map.set(p.category_id, (map.get(p.category_id) ?? 0) + 1);
    }
    return map;
  }, [products]);

  const countWithChildren = useCallback(
    (catId: string): number => {
      let total = productCount.get(catId) ?? 0;
      for (const child of categories) {
        if (child.parent_category_id === catId) {
          total += countWithChildren(child.id);
        }
      }
      return total;
    },
    [categories, productCount],
  );

  const roots = useMemo(() => {
    let rows = categories.filter((c) => c.is_active);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      rows = rows.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.description ?? "").toLowerCase().includes(q),
      );
    }
    const rootRows = rows.filter(
      (c) => !c.parent_category_id || !categories.some((x) => x.id === c.parent_category_id),
    );
    return rootRows
      .map((c) => ({
        ...c,
        listingCount: countWithChildren(c.id),
        children: categories.filter(
          (child) => child.parent_category_id === c.id && child.is_active,
        ),
      }))
      .filter((c) => c.listingCount > 0 || query.trim().length > 0)
      .sort((a, b) => b.listingCount - a.listingCount || a.name.localeCompare(b.name));
  }, [categories, countWithChildren, query]);

  const totalListings = products.length;

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="Categories"
        description="See how your products are organized. Open a category to manage those listings."
        meta={
          <>
            <span className="tb-inv-chip">{roots.length} with your SKUs</span>
            <span className="tb-inv-chip">{totalListings} of yours</span>
          </>
        }
        actions={
          <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="soft">
            My products →
          </InventoryLinkBtn>
        }
      />

      <InventoryPanel
        title="Your taxonomy"
        subtitle="Counts reflect only products you listed"
      >
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search categories…"
            className="min-w-[14rem] flex-1"
          />
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Couldn't load" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="categories" />
        ) : roots.length === 0 ? (
          <InventoryEmpty
            mark="☰"
            title="No categories in use"
            body="Assign a category when you add a product — it will show up here."
            action={
              <InventoryLinkBtn href={ROUTES.inventoryProductNew} tone="accent">
                + Add product
              </InventoryLinkBtn>
            }
          />
        ) : (
          <div className="tb-mkt-grid">
            {roots.map((cat) => (
              <article key={cat.id} className="tb-mkt-card tb-cat-shop-card">
                <Link
                  href={`${ROUTES.inventoryProducts}?category=${encodeURIComponent(cat.id)}`}
                  className="tb-cat-shop-main"
                >
                  <div className="tb-mkt-card-media" aria-hidden>
                    {cat.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(cat.image_url)} alt="" />
                    ) : (
                      <span>{cat.name.slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div className="tb-mkt-card-body">
                    <h3 className="tb-mkt-card-title">{cat.name}</h3>
                    <p className="tb-mkt-card-meta">
                      {cat.description?.trim() ||
                        `${cat.listingCount} of your product${cat.listingCount === 1 ? "" : "s"}`}
                    </p>
                    <div className="tb-mkt-card-foot">
                      <strong>
                        {cat.listingCount} listing{cat.listingCount === 1 ? "" : "s"}
                      </strong>
                      <span>Manage →</span>
                    </div>
                  </div>
                </Link>
                {cat.children.length > 0 ? (
                  <ul className="tb-cat-shop-subs">
                    {cat.children.map((child) => {
                      const childCount = countWithChildren(child.id);
                      if (childCount === 0 && !query.trim()) return null;
                      return (
                        <li key={child.id}>
                          <Link
                            href={`${ROUTES.inventoryProducts}?category=${encodeURIComponent(child.id)}`}
                          >
                            <span>{child.name}</span>
                            <span className="tb-cat-shop-sub-count">{childCount}</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </InventoryPanel>
    </div>
  );
}

function ManagerCategories() {
  const { success, error: toastError } = useToast();
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [parentId, setParentId] = useState("");
  const [pending, setPending] = useState(false);
  const live = useLiveFields(categoryCreateSchema, {
    name,
    slug,
    description,
  });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const reload = useCallback(() => {
    setLoading(true);
    void Promise.all([
      catalogApi.listCategories({ page_size: 100 }),
      catalogApi.listProducts({ page_size: 100 }).catch(() => ({ data: [] as Product[] })),
    ])
      .then(([cats, prod]) => {
        setCategories(cats.data);
        setProducts(prod.data);
        setError(null);
        setExpanded(new Set(cats.data.map((c) => c.id)));
      })
      .catch((err) => {
        setCategories([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load categories.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const productCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of products) {
      map.set(p.category_id, (map.get(p.category_id) ?? 0) + 1);
    }
    return map;
  }, [products]);

  const filtered = useMemo(() => {
    let rows = categories;
    if (activeFilter === "active") rows = rows.filter((c) => c.is_active);
    if (activeFilter === "inactive") rows = rows.filter((c) => !c.is_active);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      rows = rows.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.slug.toLowerCase().includes(q) ||
          (c.description ?? "").toLowerCase().includes(q),
      );
    }
    return rows;
  }, [activeFilter, categories, query]);

  const roots = filtered.filter(
    (c) => !c.parent_category_id || !filtered.some((x) => x.id === c.parent_category_id),
  );
  const childrenOf = (id: string) => filtered.filter((c) => c.parent_category_id === id);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function submitCreate() {
    if (!live.finish()) return;
    setPending(true);
    void catalogApi
      .createCategory({
        name: name.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || undefined,
        parent_category_id: parentId || null,
      })
      .then(() => {
        success("Category created", name.trim());
        setCreateOpen(false);
        setName("");
        setSlug("");
        setDescription("");
        setParentId("");
        live.reset();
        reload();
      })
      .catch((err) => {
        toastError(
          "Create failed",
          err instanceof ApiError ? err.message : "Could not create category.",
        );
      })
      .finally(() => setPending(false));
  }

  function renderRows(cat: Category, depth: number): ReactNode[] {
    const kids = childrenOf(cat.id);
    const isOpen = expanded.has(cat.id);
    const rows: React.ReactNode[] = [
      <tr key={cat.id}>
        <td>
          <div className="flex items-center gap-2" style={{ paddingLeft: depth * 1.15 + "rem" }}>
            {kids.length > 0 ? (
              <button
                type="button"
                className="grid h-6 w-6 place-items-center rounded-md border border-input text-xs font-bold text-link"
                onClick={() => toggle(cat.id)}
                aria-label={isOpen ? "Collapse" : "Expand"}
              >
                {isOpen ? "−" : "+"}
              </button>
            ) : (
              <span className="inline-block w-6" />
            )}
            <span className="tb-inv-thumb !h-8 !w-8 !text-[0.65rem]">
              {cat.name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <p className="font-semibold text-heading">{cat.name}</p>
              <p className="text-xs text-muted-foreground">/{cat.slug}</p>
            </div>
          </div>
        </td>
        <td>{productCount.get(cat.id) ?? 0}</td>
        <td>
          <StatusBadge status={cat.is_active ? "active" : "inactive"} />
        </td>
        <td>
          <div className="flex gap-3">
            <button
              type="button"
              className="text-sm font-bold text-link hover:underline"
              onClick={() => {
                void catalogApi
                  .updateCategory(cat.id, { is_active: !cat.is_active })
                  .then(() => {
                    success(cat.is_active ? "Deactivated" : "Activated", cat.name);
                    reload();
                  })
                  .catch((err) =>
                    toastError(
                      "Update failed",
                      err instanceof ApiError ? err.message : "Could not update.",
                    ),
                  );
              }}
            >
              {cat.is_active ? "Deactivate" : "Activate"}
            </button>
          </div>
        </td>
      </tr>,
    ];
    if (isOpen) {
      for (const child of kids) {
        rows.push(...renderRows(child, depth + 1));
      }
    }
    return rows;
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="Manage categories"
        description="Platform taxonomy for all supplier listings."
        actions={
          <InventoryBtn tone="accent" onClick={() => setCreateOpen(true)}>
            + Add Category
          </InventoryBtn>
        }
      />

      <InventoryPanel title="Taxonomy" subtitle="Expand rows to browse nested categories">
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search categories…"
            className="min-w-[14rem] flex-1"
          />
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Couldn't load" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="categories" />
        ) : filtered.length === 0 ? (
          <InventoryEmpty
            mark="☰"
            title="No categories match"
            body="Try a different search or status filter."
            action={
              <InventoryBtn tone="accent" onClick={() => setCreateOpen(true)}>
                + Add Category
              </InventoryBtn>
            }
          />
        ) : (
          <div className="tb-inv-table-wrap">
            <table className="tb-inv-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Products</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>{roots.flatMap((root) => renderRows(root, 0))}</tbody>
            </table>
          </div>
        )}
      </InventoryPanel>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create category"
        asideTitle="Taxonomy"
        asideBody="Top-level categories have no parent. Child categories nest under one parent only."
        footer={
          <>
            <button
              type="button"
              className="tb-btn tb-btn--outline"
              onClick={() => setCreateOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="tb-btn tb-btn--primary"
              disabled={pending || !name.trim()}
              onClick={submitCreate}
             aria-busy={pending || undefined}>
              <BusyText busy={pending}>{pending ? "Creating…" : "Create →"}</BusyText>
            </button>
          </>
        }
      >
        <label className="tb-split-field" data-state={live.errors.name ? "error" : undefined}>
          <span>Name</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => live.touch("name")}
            placeholder="Electronics"
          />
          <FieldError error={live.errors.name} />
        </label>
        <label className="tb-split-field mt-3" data-state={live.errors.slug ? "error" : undefined}>
          <span>Slug (optional)</span>
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            onBlur={() => live.touch("slug")}
            placeholder="electronics"
          />
          <FieldError error={live.errors.slug} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => live.touch("description")}
            rows={3}
            placeholder="What belongs in this category?"
          />
          <FieldError error={live.errors.description} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Parent</span>
          <select value={parentId} onChange={(e) => setParentId(e.target.value)}>
            <option value="">None (top-level)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </Modal>
    </div>
  );
}

function CategoriesInner() {
  const { hasPermission, business } = useAuth();
  const canManage = hasPermission("categories.manage");
  const isSupplier = business?.type === "supplier";

  if (canManage) {
    return <ManagerCategories />;
  }
  if (isSupplier) {
    return <SupplierCategoriesView />;
  }

  return <BuyerShopByCategory />;
}

export default function InventoryCategoriesPage() {
  return (
    <PermissionGate permission="categories.read" allowGuest>
      <CategoriesInner />
    </PermissionGate>
  );
}
