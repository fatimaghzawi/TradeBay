"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { AddToCartButton } from "@/components/cart/AddToCartButton";
import {
  InventoryBtn,
  InventoryEmpty,
  InventoryKpi,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventoryTabs,
  StatusBadge,
  StockBar,
} from "@/components/catalog/InventoryUi";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity, BusyText, Spinner } from "@/components/ui/LoadingState";
import { Modal } from "@/components/ui/Modal";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  PRODUCT_UNITS,
  catalogApi,
  type Category,
  type InventoryTransaction,
  type Product,
  type ProductPrice,
} from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { validateUpload } from "@/lib/validation/common";
import {
  priceTierSchema,
  productCreateSchema,
  stockQtySchema,
} from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

function txLabel(type: string): string {
  return type.split("_").join(" ");
}

function qtyTone(type: string): string {
  if (type.includes("sale") || type.includes("reserve") || type.includes("adjust_out")) {
    return "text-[#b42318]";
  }
  return "text-[#0f6b45]";
}

function ProductDetailInner() {
  const params = useParams<{ id: string }>();
  const productId = params.id;
  const router = useRouter();
  const searchParams = useSearchParams();
  const { hasPermission, business } = useAuth();
  const { success, error: toastError } = useToast();

  // Platform staff use the admin product detail chrome (readable console contrast).
  useEffect(() => {
    if (business?.type === "platform" && productId) {
      router.replace(ROUTES.admin.productDetail(productId));
    }
  }, [business?.type, productId, router]);

  const [product, setProduct] = useState<Product | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<Category | null>(null);
  const [prices, setPrices] = useState<ProductPrice[]>([]);
  const [txs, setTxs] = useState<InventoryTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"details" | "inventory">("details");

  const [priceOpen, setPriceOpen] = useState(false);
  const [minQty, setMinQty] = useState("50");
  const [maxQty, setMaxQty] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [openEnded, setOpenEnded] = useState(false);

  const [stockOpen, setStockOpen] = useState(false);
  const [stockAction, setStockAction] = useState<
    "stock" | "reserve" | "release" | "sale"
  >("stock");
  const [stockQty, setStockQty] = useState("");
  const [stockReason, setStockReason] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editSku, setEditSku] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editUnit, setEditUnit] = useState("piece");
  const [editOrigin, setEditOrigin] = useState("");
  const [editMoq, setEditMoq] = useState("1");
  const [editLeadTime, setEditLeadTime] = useState("0");
  const [editFeatured, setEditFeatured] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const editLive = useLiveFields(productCreateSchema, {
    name: editName,
    sku: editSku,
    category_id: editCategoryId,
    unit: editUnit,
    description: editDescription,
    origin: editOrigin,
    moq: editMoq,
    lead_time: editLeadTime,
  });
  const priceLive = useLiveFields(priceTierSchema, {
    min_quantity: minQty,
    max_quantity: maxQty,
    unit_price: unitPrice,
    open_ended: openEnded,
  });
  const stockLive = useLiveFields(stockQtySchema, {
    quantity: stockQty,
    reason: stockReason,
  });

  const isPlatform = business?.type === "platform";
  const isOwner =
    !!product &&
    !!business?.id &&
    product.business_account_id === business.id &&
    business.type === "supplier";
  const canManageProducts = hasPermission("products.manage") && isOwner;
  const canManageInventory = hasPermission("inventory.manage") && isOwner;
  // Stock & transaction history are supplier-owner ops — buyers never see them.
  const canReadInventory = hasPermission("inventory.read") && isOwner;
  const isBuyer = business?.type === "buyer";

  const reload = useCallback(() => {
    if (isPlatform) return;
    setLoading(true);
    setError(null);
    void Promise.all([
      catalogApi.getProduct(productId),
      catalogApi.listPrices(productId).catch(() => [] as ProductPrice[]),
      canReadInventory
        ? catalogApi
            .listTransactions(productId, { page_size: 30 })
            .then((r) => r.data)
            .catch(() => [] as InventoryTransaction[])
        : Promise.resolve([] as InventoryTransaction[]),
    ])
      .then(async ([p, priceRows, txRows]) => {
        setProduct(p);
        setPrices(priceRows);
        setTxs(txRows);
        const primary =
          p.images?.find((img) => img.is_primary) ?? p.images?.[0] ?? null;
        setActiveImageId(primary?.id ?? null);
        try {
          const cats = await catalogApi.listCategories({ page_size: 100 });
          setCategories(cats.data);
          setCategory(cats.data.find((c) => c.id === p.category_id) ?? null);
        } catch {
          setCategories([]);
          setCategory(null);
        }
      })
      .catch((err) => {
        setProduct(null);
        setError(err instanceof ApiError ? err.message : "Product not found.");
      })
      .finally(() => setLoading(false));
  }, [canReadInventory, isPlatform, productId]);

  useEffect(() => {
    reload();
  }, [reload]);

  function openEdit(p: Product) {
    setEditName(p.name);
    setEditSku(p.sku);
    setEditCategoryId(p.category_id);
    setEditDescription(p.description ?? "");
    setEditUnit(p.unit || "piece");
    setEditOrigin(p.origin ?? "");
    setEditMoq(String(p.moq ?? 1));
    setEditLeadTime(String(p.lead_time_days ?? 0));
    setEditFeatured(Boolean(p.is_featured));
    editLive.reset();
    setEditOpen(true);
  }

  useEffect(() => {
    if (!product || !canManageProducts) return;
    if (searchParams.get("edit") === "1") {
      openEdit(product);
      router.replace(ROUTES.inventoryProduct(productId), { scroll: false });
    }
    // Only react to the edit query flag once product is ready
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.id, canManageProducts, searchParams]);

  function activate() {
    setBusy(true);
    void catalogApi
      .updateProduct(productId, { status: "active" })
      .then(() => {
        success("Activated", "Product is visible in the marketplace.");
        reload();
      })
      .catch((err) => {
        toastError(
          "Activate failed",
          err instanceof ApiError
            ? err.message
            : "Need MOQ, an inventory row, and at least one price tier.",
        );
      })
      .finally(() => setBusy(false));
  }

  function submitEdit() {
    if (!editLive.finish()) return;
    const moq = Number(editMoq);
    const lead = Number(editLeadTime);
    setBusy(true);
    void catalogApi
      .updateProduct(productId, {
        name: editName.trim(),
        sku: editSku.trim(),
        category_id: editCategoryId,
        description: editDescription.trim(),
        unit: editUnit,
        origin: editOrigin.trim(),
        moq,
        lead_time_days: lead,
        is_featured: editFeatured,
      })
      .then(() => {
        success("Product updated", "Listing details saved.");
        setEditOpen(false);
        reload();
      })
      .catch((err) => {
        toastError(
          "Update failed",
          err instanceof ApiError ? err.message : "Could not save product.",
        );
      })
      .finally(() => setBusy(false));
  }

  function submitPrice() {
    if (!priceLive.finish()) return;
    setBusy(true);
    void catalogApi
      .createPrice(productId, {
        min_quantity: Number(minQty),
        max_quantity: openEnded || !maxQty.trim() ? null : Number(maxQty),
        unit_price: unitPrice.trim(),
      })
      .then(() => {
        success("Price tier added", "Wholesale range saved.");
        setPriceOpen(false);
        setMinQty("50");
        setMaxQty("");
        setUnitPrice("");
        setOpenEnded(false);
        reload();
      })
      .catch((err) => {
        toastError(
          "Price failed",
          err instanceof ApiError ? err.message : "Could not save price tier.",
        );
      })
      .finally(() => setBusy(false));
  }

  function submitStock() {
    if (!stockLive.finish()) return;
    setBusy(true);
    const body = {
      quantity: stockQty.trim(),
      reason: stockReason.trim() || undefined,
    };
    const run =
      stockAction === "stock"
        ? catalogApi.addStock
        : stockAction === "reserve"
          ? catalogApi.reserveStock
          : stockAction === "release"
            ? catalogApi.releaseStock
            : catalogApi.saleStock;
    void run(productId, body)
      .then(() => {
        success("Inventory updated", `${stockAction} recorded.`);
        setStockOpen(false);
        setStockQty("");
        setStockReason("");
        reload();
      })
      .catch((err) => {
        toastError(
          "Stock update failed",
          err instanceof ApiError ? err.message : "Could not update inventory.",
        );
      })
      .finally(() => setBusy(false));
  }

  if (isPlatform) {
    return <p className="text-sm text-[#5a6a62]">Opening admin product…</p>;
  }

  if (loading) {
    return <LoadingEntity entity="product" />;
  }

  if (error || !product) {
    return (
      <div className="tb-inv-page">
        <FeedbackBanner tone="error" title="Product unavailable">
          {error ?? "Not found"}
        </FeedbackBanner>
        <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="ghost">
          ← Products
        </InventoryLinkBtn>
      </div>
    );
  }

  const inv = product.inventory;
  const avail = Number(inv?.available_quantity ?? 0);
  const reserved = Number(inv?.reserved_quantity ?? 0);
  const totalUnits = Math.max(avail + reserved, 1);
  const gallery = product.images ?? [];
  const activeImage =
    gallery.find((img) => img.id === activeImageId) ??
    gallery.find((img) => img.is_primary) ??
    gallery[0] ??
    null;
  const heroSrc = mediaUrl(activeImage?.url ?? product.primary_image_url);
  const received = txs
    .filter((t) => t.transaction_type.includes("stock") || t.transaction_type === "receive")
    .reduce((sum, t) => sum + Number(t.quantity || 0), 0);
  const sold = txs
    .filter((t) => t.transaction_type.includes("sale"))
    .reduce((sum, t) => sum + Number(t.quantity || 0), 0);

  function uploadImages(fileList: FileList | null) {
    if (!fileList?.length || !canManageProducts) return;
    const files = Array.from(fileList);
    for (const file of files) {
      const message = validateUpload(file, { kinds: "image", label: "Image" });
      if (message) {
        setImageError(message);
        return;
      }
    }
    setImageError(null);
    setUploading(true);
    void (async () => {
      try {
        let first = true;
        for (const file of Array.from(fileList)) {
          if (!file.type.startsWith("image/")) continue;
          await catalogApi.uploadProductImage(productId, file, {
            is_primary: first && gallery.length === 0,
            alt_text: product.name,
          });
          first = false;
        }
        success("Images uploaded", "Gallery updated.");
        reload();
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : "Could not upload image.";
        toastError("Upload failed", message);
      } finally {
        setUploading(false);
      }
    })();
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow={product.sku}
        title={product.name}
        description={
          <>
            {product.origin ? `Origin ${product.origin} · ` : null}
            MOQ {product.moq} · Lead {product.lead_time_days}d
          </>
        }
        meta={<StatusBadge status={product.status} />}
        actions={
          <div className="flex flex-wrap gap-2">
            <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="ghost">
              {isBuyer ? "← Marketplace" : "← My products"}
            </InventoryLinkBtn>
            {isBuyer ? (
              <>
                <AddToCartButton
                  productId={product.id}
                  quantity={Math.max(1, product.moq || 1)}
                />
                <InventoryLinkBtn href={ROUTES.cart} tone="ghost">
                  View cart →
                </InventoryLinkBtn>
                <InventoryLinkBtn
                  href={ROUTES.procurementProductQuote(product.id)}
                  tone="soft"
                >
                  Request a Quote →
                </InventoryLinkBtn>
              </>
            ) : null}
          </div>
        }
      />

      <InventoryTabs
        value={tab}
        onChange={(id) => setTab(id as "details" | "inventory")}
        tabs={[
          { id: "details", label: "Details" },
          ...(canReadInventory ? [{ id: "inventory", label: "Inventory" }] : []),
        ]}
      />

      {tab === "details" ? (
        <div className="tb-inv-split">
          <InventoryPanel
            title="Product profile"
            subtitle="Core commercial identity"
            action={
              canManageProducts ? (
                <div className="flex flex-wrap gap-2">
                  <InventoryBtn tone="soft" onClick={() => openEdit(product)}>
                    Edit
                  </InventoryBtn>
                  {product.status !== "active" ? (
                    <InventoryBtn tone="accent" busy={busy} disabled={busy} onClick={activate}>
                      Activate
                    </InventoryBtn>
                  ) : null}
                  {product.status !== "inactive" ? (
                    <InventoryBtn tone="ghost" onClick={() => setDeleteOpen(true)}>
                      Delete
                    </InventoryBtn>
                  ) : null}
                </div>
              ) : null
            }
          >
            <div className="tb-inv-detail-hero">
              <div className="tb-inv-gallery">
                <div className="tb-inv-detail-media" aria-hidden>
                  {heroSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={heroSrc}
                      alt=""
                      className="h-full w-full rounded-[1.15rem] object-cover"
                    />
                  ) : (
                    product.name.slice(0, 2).toUpperCase()
                  )}
                </div>
                {gallery.length > 0 || canManageProducts ? (
                  <ul className="tb-inv-thumbs">
                    {gallery.map((img) => (
                      <li key={img.id} className="tb-inv-thumb-card">
                        <button
                          type="button"
                          className="tb-inv-thumb-preview"
                          data-primary={img.is_primary || img.id === activeImage?.id}
                          onClick={() => setActiveImageId(img.id)}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={mediaUrl(img.url)} alt={img.alt_text ?? ""} />
                          {img.is_primary ? (
                            <span className="tb-inv-thumb-badge">Primary</span>
                          ) : null}
                        </button>
                        {canManageProducts ? (
                          <div className="tb-inv-thumb-actions">
                            {!img.is_primary ? (
                              <button
                                type="button"
                                onClick={() => {
                                  void catalogApi
                                    .setPrimaryProductImage(productId, img.id)
                                    .then(() => {
                                      success("Primary image set");
                                      reload();
                                    })
                                    .catch((err) =>
                                      toastError(
                                        "Update failed",
                                        err instanceof ApiError
                                          ? err.message
                                          : "Could not set primary.",
                                      ),
                                    );
                                }}
                              >
                                Primary
                              </button>
                            ) : null}
                            <button
                              type="button"
                              className="is-danger"
                              onClick={() => {
                                void catalogApi
                                  .deleteProductImage(productId, img.id)
                                  .then(() => {
                                    success("Image removed");
                                    reload();
                                  })
                                  .catch((err) =>
                                    toastError(
                                      "Delete failed",
                                      err instanceof ApiError
                                        ? err.message
                                        : "Could not delete image.",
                                    ),
                                  );
                              }}
                            >
                              Remove
                            </button>
                          </div>
                        ) : null}
                      </li>
                    ))}
                    {canManageProducts ? (
                      <li>
                        <label className="tb-inv-thumb-add">
                          <span>{uploading ? <Spinner size="sm" /> : "+"}</span>
                          <span className="text-[0.65rem] font-bold">Add</span>
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/gif"
                            multiple
                            className="sr-only"
                            disabled={uploading}
                            onChange={(e) => {
                              uploadImages(e.target.files);
                              e.target.value = "";
                            }}
                          />
                        </label>
                      </li>
                    ) : null}
                  </ul>
                ) : null}
              </div>
              {imageError ? (
                <FieldError error={imageError} />
              ) : null}
              <dl className="tb-inv-detail-grid">
                {product.supplier_name ? (
                  <div>
                    <dt>Supplier</dt>
                    <dd>
                      <span className="tb-verified-inline capitalize">
                        {product.supplier_name}
                        <VerifiedBadge
                          verified={Boolean(product.supplier_verified)}
                          showWhenUnverified={false}
                        />
                      </span>
                    </dd>
                  </div>
                ) : null}
                {(
                  [
                    ["SKU", product.sku],
                    ["Category", category?.name ?? "—"],
                    ["Origin", product.origin ?? "—"],
                    ["Unit", product.unit],
                    ["MOQ", String(product.moq)],
                    ["Lead time", `${product.lead_time_days} days`],
                    ["Status", product.status],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd className="capitalize">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
            {product.description ? (
              <p className="mt-5 border-t border-[#eef3f0] pt-4 text-sm leading-relaxed text-[#4a5f55]">
                {product.description}
              </p>
            ) : null}
          </InventoryPanel>

          {canReadInventory ? (
            <InventoryPanel title="Stock summary" subtitle="Live available vs reserved">
              <p className="font-[family-name:var(--font-outfit)] text-2xl font-extrabold text-[#0d3b2a]">
                {avail}{" "}
                <span className="text-base font-semibold text-[#5a6a62]">available</span>
              </p>
              <StockBar label="Available" value={avail} max={totalUnits} tone="ok" />
              <StockBar label="Reserved" value={reserved} max={totalUnits} tone="warn" />
              {canManageInventory ? (
                <InventoryBtn
                  tone="accent"
                  className="mt-5 w-full"
                  onClick={() => {
                    setStockAction("stock");
                    setTab("inventory");
                    stockLive.reset();
                    setStockOpen(true);
                  }}
                >
                  + Record Transaction
                </InventoryBtn>
              ) : null}
            </InventoryPanel>
          ) : isBuyer ? (
            <InventoryPanel title="Order this product">
              <dl className="tb-inv-detail-grid">
                <div>
                  <dt>MOQ</dt>
                  <dd>{product.moq}</dd>
                </div>
                <div>
                  <dt>Lead time</dt>
                  <dd>{product.lead_time_days} days</dd>
                </div>
                <div>
                  <dt>Unit</dt>
                  <dd className="capitalize">{product.unit}</dd>
                </div>
              </dl>
              <div className="mt-5 flex flex-col gap-2">
                <AddToCartButton
                  productId={product.id}
                  quantity={Math.max(1, product.moq || 1)}
                  className="w-full"
                />
                <InventoryLinkBtn href={ROUTES.cart} tone="ghost" className="w-full">
                  Open cart →
                </InventoryLinkBtn>
                <InventoryLinkBtn
                  href={ROUTES.procurementProductQuote(product.id)}
                  tone="soft"
                  className="w-full"
                >
                  Request a Quote only →
                </InventoryLinkBtn>
              </div>
            </InventoryPanel>
          ) : null}
        </div>
      ) : null}

      {tab === "details" ? (
        <InventoryPanel
          title="Wholesale tiers"
          subtitle={undefined}
          action={
            canManageProducts ? (
              <InventoryBtn tone="soft" onClick={() => {
                priceLive.reset();
                setPriceOpen(true);
              }}>
                Add tier
              </InventoryBtn>
            ) : null
          }
        >
          {prices.length === 0 ? (
            <InventoryEmpty
              mark="$"
              title="No price tiers yet"
              body="Add at least one wholesale range before activating."
              action={
                canManageProducts ? (
                  <InventoryBtn tone="accent" onClick={() => {
                    priceLive.reset();
                    setPriceOpen(true);
                  }}>
                    Add tier
                  </InventoryBtn>
                ) : null
              }
            />
          ) : (
            <div className="tb-inv-table-wrap">
              <table className="tb-inv-table">
                <thead>
                  <tr>
                    <th>Qty range</th>
                    <th>Unit price</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {prices.map((tier) => (
                    <tr key={tier.id}>
                      <td>
                        {tier.min_quantity}
                        {tier.max_quantity != null ? ` – ${tier.max_quantity}` : "+"}
                      </td>
                      <td className="font-semibold">
                        {tier.currency} {tier.unit_price}
                      </td>
                      <td>
                        <StatusBadge status={tier.is_active ? "active" : "inactive"} />
                      </td>
                      <td>
                        {canManageProducts ? (
                          <button
                            type="button"
                            className="text-sm font-bold text-[#b42318] hover:underline"
                            onClick={() => {
                              void catalogApi
                                .deletePrice(productId, tier.id)
                                .then(() => {
                                  success("Removed", "Price tier soft-deleted.");
                                  reload();
                                })
                                .catch((err) =>
                                  toastError(
                                    "Delete failed",
                                    err instanceof ApiError
                                      ? err.message
                                      : "Could not delete tier.",
                                  ),
                                );
                            }}
                          >
                            Remove
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </InventoryPanel>
      ) : null}

      {tab === "inventory" && canReadInventory ? (
        <>
          <div className="tb-inv-kpi-grid">
            <InventoryKpi index={0} label="Available" value={avail} tone="ok" icon="✓" />
            <InventoryKpi index={1} label="Reserved" value={reserved} tone="warn" icon="◷" />
            <InventoryKpi index={2} label="Received (log)" value={received || "—"} icon="↓" />
            <InventoryKpi index={3} label="Sold (log)" value={sold || "—"} icon="↑" />
          </div>

          <InventoryPanel
            title="Transaction history"
            subtitle="Append-only movements for this SKU"
            action={
              canManageInventory ? (
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      ["stock", "Add stock"],
                      ["reserve", "Reserve"],
                      ["release", "Release"],
                      ["sale", "Sale"],
                    ] as const
                  ).map(([action, label]) => (
                    <InventoryBtn
                      key={action}
                      tone="ghost"
                      onClick={() => {
                        setStockAction(action);
                        stockLive.reset();
                        setStockOpen(true);
                      }}
                    >
                      {label}
                    </InventoryBtn>
                  ))}
                </div>
              ) : null
            }
          >
            {txs.length === 0 ? (
              <InventoryEmpty
                mark="⇄"
                title="No movements yet"
                body="Record stock, reserves, releases, or sales to build history."
              />
            ) : (
              <div className="tb-inv-table-wrap">
                <table className="tb-inv-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Qty</th>
                      <th>Balance</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {txs.map((tx) => (
                      <tr key={tx.id}>
                        <td className="text-xs text-[#5a6a62]">
                          {tx.created_at
                            ? new Date(tx.created_at).toLocaleString()
                            : "—"}
                        </td>
                        <td className="capitalize">{txLabel(tx.transaction_type)}</td>
                        <td className={`font-semibold ${qtyTone(tx.transaction_type)}`}>
                          {tx.transaction_type.includes("sale") ||
                          tx.transaction_type.includes("reserve")
                            ? `−${tx.quantity}`
                            : `+${tx.quantity}`}
                        </td>
                        <td>
                          {tx.new_available} avail · {tx.new_reserved} res
                        </td>
                        <td className="text-sm text-[#5a6a62]">{tx.reason ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </InventoryPanel>
        </>
      ) : null}

      <Modal
        open={priceOpen}
        onClose={() => setPriceOpen(false)}
        title="Add price tier"
        asideTitle="Wholesale pricing"
        asideBody="Quantity ranges must not overlap. Leave max empty for an open-ended top tier."
        mark="shield"
        footer={
          <>
            <button type="button" className="tb-split-btn-ghost" onClick={() => setPriceOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="tb-split-btn"
              disabled={busy || !unitPrice.trim()}
              onClick={submitPrice}
             aria-busy={busy || undefined}>
              <BusyText busy={busy}>{busy ? "Saving…" : "Save tier →"}</BusyText>
            </button>
          </>
        }
      >
        <label className="tb-split-field" data-state={priceLive.errors.min_quantity ? "error" : undefined}>
          <span>Min quantity</span>
          <NumberInput
            kind="integer"
            min={1}
            value={minQty}
            onChange={(e) => setMinQty(e.target.value)}
            onBlur={() => priceLive.touch("min_quantity")}
            required
          />
          <FieldError error={priceLive.errors.min_quantity} />
        </label>
        <label className="tb-split-field mt-3" data-state={priceLive.errors.max_quantity ? "error" : undefined}>
          <span>Max quantity</span>
          <NumberInput
            kind="integer"
            min={1}
            value={maxQty}
            disabled={openEnded}
            onChange={(e) => setMaxQty(e.target.value)}
            onBlur={() => priceLive.touch("max_quantity")}
            placeholder="Leave empty if open-ended"
          />
          <FieldError error={priceLive.errors.max_quantity} />
        </label>
        <label className="mt-2 flex items-center gap-2 text-sm text-[#5a6a62]">
          <input
            type="checkbox"
            checked={openEnded}
            onChange={(e) => {
              setOpenEnded(e.target.checked);
              if (e.target.checked) setMaxQty("");
            }}
          />
          Open-ended (no max)
        </label>
        <label className="tb-split-field mt-3" data-state={priceLive.errors.unit_price ? "error" : undefined}>
          <span>Unit price (USD)</span>
          <NumberInput
            kind="decimal"
            value={unitPrice}
            onChange={(e) => setUnitPrice(e.target.value)}
            onBlur={() => priceLive.touch("unit_price")}
            placeholder="4.50"
            required
          />
          <FieldError error={priceLive.errors.unit_price} />
        </label>
      </Modal>

      <Modal
        open={stockOpen}
        onClose={() => setStockOpen(false)}
        title={
          stockAction === "stock"
            ? "Add stock"
            : stockAction === "reserve"
              ? "Reserve stock"
              : stockAction === "release"
                ? "Release reservation"
                : "Record sale"
        }
        asideTitle="Inventory movement"
        asideBody="Every change writes an append-only transaction. Reservations cannot exceed available stock."
        mark="shield"
        footer={
          <>
            <button type="button" className="tb-split-btn-ghost" onClick={() => setStockOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="tb-split-btn"
              disabled={busy || !stockQty.trim()}
              onClick={submitStock}
             aria-busy={busy || undefined}>
              <BusyText busy={busy}>{busy ? "Updating…" : "Confirm →"}</BusyText>
            </button>
          </>
        }
      >
        <label className="tb-split-field" data-state={stockLive.errors.quantity ? "error" : undefined}>
          <span>Quantity</span>
          <NumberInput
            kind="integer"
            value={stockQty}
            onChange={(e) => setStockQty(e.target.value)}
            onBlur={() => stockLive.touch("quantity")}
            placeholder="20"
            required
          />
          <FieldError error={stockLive.errors.quantity} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Reason (optional)</span>
          <input
            value={stockReason}
            onChange={(e) => setStockReason(e.target.value)}
            onBlur={() => stockLive.touch("reason")}
            placeholder="Manual adjustment"
          />
          <FieldError error={stockLive.errors.reason} />
        </label>
      </Modal>

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Edit product"
        asideTitle="Listing details"
        asideBody="Update the commercial identity buyers see. Prices, stock, and images stay on this page."
        mark="shield"
        footer={
          <>
            <button type="button" className="tb-split-btn-ghost" onClick={() => setEditOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="tb-split-btn"
              disabled={busy || !editName.trim() || !editSku.trim() || !editCategoryId}
              onClick={submitEdit}
             aria-busy={busy || undefined}>
              <BusyText busy={busy}>{busy ? "Saving…" : "Save changes →"}</BusyText>
            </button>
          </>
        }
      >
        <label className="tb-split-field" data-state={editLive.errors.name ? "error" : undefined}>
          <span>Name</span>
          <input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={() => editLive.touch("name")}
            maxLength={200}
            required
          />
          <FieldError error={editLive.errors.name} />
        </label>
        <label className="tb-split-field mt-3" data-state={editLive.errors.sku ? "error" : undefined}>
          <span>SKU</span>
          <input
            value={editSku}
            onChange={(e) => setEditSku(e.target.value)}
            onBlur={() => editLive.touch("sku")}
            maxLength={64}
            required
          />
          <FieldError error={editLive.errors.sku} />
        </label>
        <label className="tb-split-field mt-3" data-state={editLive.errors.category_id ? "error" : undefined}>
          <span>Category</span>
          <select
            value={editCategoryId}
            onChange={(e) => setEditCategoryId(e.target.value)}
            onBlur={() => editLive.touch("category_id")}
            required
          >
            {categories.length === 0 ? (
              <option value="">No categories</option>
            ) : (
              categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))
            )}
          </select>
          <FieldError error={editLive.errors.category_id} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Unit</span>
          <select value={editUnit} onChange={(e) => setEditUnit(e.target.value)}>
            {PRODUCT_UNITS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>
        <label className="tb-split-field mt-3">
          <span>Description</span>
          <textarea
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            onBlur={() => editLive.touch("description")}
            rows={4}
            maxLength={5000}
          />
          <FieldError error={editLive.errors.description} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Origin</span>
          <input
            value={editOrigin}
            onChange={(e) => setEditOrigin(e.target.value)}
            onBlur={() => editLive.touch("origin")}
            maxLength={120}
            placeholder="Turkey"
          />
          <FieldError error={editLive.errors.origin} />
        </label>
        <label className="tb-split-field mt-3" data-state={editLive.errors.moq ? "error" : undefined}>
          <span>Minimum order quantity</span>
          <NumberInput
            kind="integer"
            min={1}
            value={editMoq}
            onChange={(e) => setEditMoq(e.target.value)}
            onBlur={() => editLive.touch("moq")}
            required
          />
          <FieldError error={editLive.errors.moq} />
        </label>
        <label className="tb-split-field mt-3" data-state={editLive.errors.lead_time ? "error" : undefined}>
          <span>Lead time (days)</span>
          <NumberInput
            kind="integer"
            min={0}
            value={editLeadTime}
            onChange={(e) => setEditLeadTime(e.target.value)}
            onBlur={() => editLive.touch("lead_time")}
            required
          />
          <FieldError error={editLive.errors.lead_time} />
        </label>
        <label className="mt-3 flex items-center gap-2 text-sm text-[#5a6a62]">
          <input
            type="checkbox"
            checked={editFeatured}
            onChange={(e) => setEditFeatured(e.target.checked)}
          />
          Show on landing page featured products
        </label>
      </Modal>

      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete product?"
        asideTitle="Soft-delete"
        asideBody="The listing is deactivated (set inactive), not permanently removed. Order history stays intact. You can reactivate later."
        confirmLabel="Delete"
        onConfirm={async () => {
          await catalogApi.deactivateProduct(productId);
          success("Deleted", "Product is no longer marketplace-visible.");
          router.push(ROUTES.inventoryProducts);
        }}
      >
        <p className="text-sm text-[#5c574e]">
          Soft-delete <strong>{product.name}</strong>? Buyers will no longer see it.
        </p>
      </ConfirmModal>
    </div>
  );
}

export default function ProductDetailPage() {
  return (
    <PermissionGate permission="products.read">
      <Suspense fallback={<LoadingEntity entity="product" />}>
        <ProductDetailInner />
      </Suspense>
    </PermissionGate>
  );
}
