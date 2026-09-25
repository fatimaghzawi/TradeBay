"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import {
  InventoryBtn,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Spinner } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  PRODUCT_UNITS,
  catalogApi,
  type Category,
} from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { validateUpload } from "@/lib/validation/common";
import { NumberInput } from "@/components/ui/FormField";
import { productCreateSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BackLink } from "@/components/ui/BackLink";

type PendingImage = {
  id: string;
  file: File;
  preview: string;
};

function NewProductInner() {
  const router = useRouter();
  const { business } = useAuth();
  const { success, error: toastError } = useToast();
  const [categories, setCategories] = useState<Category[]>([]);
  const [catsLoading, setCatsLoading] = useState(true);
  const [categoryId, setCategoryId] = useState("");
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [unit, setUnit] = useState<string>("piece");
  const [origin, setOrigin] = useState("");
  const [moq, setMoq] = useState("1");
  const [leadTime, setLeadTime] = useState("0");
  const [featured, setFeatured] = useState(false);
  const [images, setImages] = useState<PendingImage[]>([]);
  const [primaryId, setPrimaryId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const live = useLiveFields(productCreateSchema, {
    name,
    sku,
    category_id: categoryId,
    unit,
    description,
    origin,
    moq,
    lead_time: leadTime,
  });

  useEffect(() => {
    void catalogApi
      .listCategories({ active_only: true, page_size: 100 })
      .then((result) => {
        setCategories(result.data);
        if (result.data[0]) setCategoryId(result.data[0].id);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load categories. Ask platform staff to create some first.",
        );
      })
      .finally(() => setCatsLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      for (const img of images) URL.revokeObjectURL(img.preview);
    };
    
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (business?.type !== "supplier") {
    return (
      <div className="tb-inv-page">
        <FeedbackBanner tone="warning" title="Supplier only">
          Only verified supplier companies can create catalog products.
        </FeedbackBanner>
        <BackLink href={ROUTES.inventoryProducts}>Back to marketplace</BackLink>
      </div>
    );
  }

  function addFiles(fileList: FileList | null) {
    if (!fileList?.length) return;
    const next: PendingImage[] = [];
    for (const file of Array.from(fileList)) {
      const message = validateUpload(file, { kinds: "image", label: file.name });
      if (message) {
        setImageError(message);
        continue;
      }
      setImageError(null);
      next.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
        file,
        preview: URL.createObjectURL(file),
      });
    }
    if (!next.length) return;
    setImages((prev) => {
      const merged = [...prev, ...next].slice(0, 12);
      if (!primaryId && merged[0]) setPrimaryId(merged[0].id);
      return merged;
    });
  }

  function removeImage(id: string) {
    setImages((prev) => {
      const target = prev.find((img) => img.id === id);
      if (target) URL.revokeObjectURL(target.preview);
      const rest = prev.filter((img) => img.id !== id);
      if (primaryId === id) setPrimaryId(rest[0]?.id ?? null);
      return rest;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!live.finish()) return;
    setPending(true);
    void catalogApi
      .createProduct({
        category_id: categoryId,
        sku: sku.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        unit,
        origin: origin.trim() || undefined,
        moq: Number(moq),
        lead_time_days: Number(leadTime),
        is_featured: featured,
      })
      .then(async (product) => {
        for (const img of images) {
          await catalogApi.uploadProductImage(product.id, img.file, {
            is_primary: img.id === primaryId,
            alt_text: name.trim() || undefined,
          });
        }
        success(
          "Product created",
          images.length
            ? `${product.name} saved with ${images.length} image${images.length === 1 ? "" : "s"}.`
            : `${product.name} is saved as a draft.`,
        );
        router.push(ROUTES.inventoryProduct(product.id));
      })
      .catch((err) => {
        const message =
          err instanceof ApiError ? err.message : "Could not create product.";
        setError(message);
        toastError("Couldn't create", message);
      })
      .finally(() => setPending(false));
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="Add product"
        description="Creates a draft listing under your business. Add photos, price tiers, and stock before activating."
        actions={
          <BackLink href={ROUTES.inventoryProducts}>My products</BackLink>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t create" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      <form onSubmit={submit}>
        <InventoryPanel
          title="Basic information"
          subtitle="Identity fields buyers and ops will search by"
        >
          <div className="tb-inv-form-grid">
            <label className="tb-split-field" data-state={live.errors.name ? "error" : undefined}>
              <span>Product Name</span>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => live.touch("name")}
                placeholder="Organic Olive Oil"
                maxLength={200}
              />
              {live.errors.name ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.name}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field" data-state={live.errors.sku ? "error" : undefined}>
              <span>SKU</span>
              <input
                required
                value={sku}
                onChange={(e) => setSku(e.target.value.toUpperCase())}
                onBlur={() => live.touch("sku")}
                placeholder="OIL-001"
                maxLength={64}
              />
              {live.errors.sku ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.sku}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field" data-state={live.errors.category_id ? "error" : undefined}>
              <span className="tb-busy-label">
                Category
                {catsLoading ? <Spinner size="sm" /> : null}
              </span>
              <select
                required
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                onBlur={() => live.touch("category_id")}
                disabled={catsLoading || categories.length === 0}
                aria-busy={catsLoading || undefined}
              >
                {catsLoading ? (
                  <option value="">Loading categories…</option>
                ) : categories.length === 0 ? (
                  <option value="">No categories available</option>
                ) : (
                  categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))
                )}
              </select>
              {live.errors.category_id ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.category_id}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field">
              <span>Unit</span>
              <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                {PRODUCT_UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </label>
            <label className="tb-split-field sm:col-span-2">
              <span>Description</span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={() => live.touch("description")}
                rows={4}
                maxLength={4000}
                placeholder="Short wholesale description…"
              />
              {live.errors.description ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.description}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field">
              <span>Origin</span>
              <input
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                placeholder="Turkey"
                maxLength={120}
              />
            </label>
            <label className="tb-split-field" data-state={live.errors.moq ? "error" : undefined}>
              <span>Minimum Order Quantity</span>
              <NumberInput
                required
                kind="integer"
                min={1}
                value={moq}
                onChange={(e) => setMoq(e.target.value)}
                onBlur={() => live.touch("moq")}
              />
              {live.errors.moq ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.moq}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field" data-state={live.errors.lead_time ? "error" : undefined}>
              <span>Lead Time (days)</span>
              <NumberInput
                required
                kind="integer"
                min={0}
                value={leadTime}
                onChange={(e) => setLeadTime(e.target.value)}
                onBlur={() => live.touch("lead_time")}
              />
              {live.errors.lead_time ? (
                <p className="tb-hint" data-tone="error">
                  {live.errors.lead_time}
                </p>
              ) : null}
            </label>
            <label className="tb-split-field sm:col-span-2 flex flex-row items-center gap-2">
              <input
                type="checkbox"
                checked={featured}
                onChange={(e) => setFeatured(e.target.checked)}
              />
              <span>Show on landing page featured products</span>
            </label>
          </div>
        </InventoryPanel>

        <InventoryPanel
          title="Product images"
          subtitle="Upload up to 12 photos. Click a thumb to mark it as primary."
          className="mt-4"
        >
          <label className="tb-inv-image-drop">
            <span className="font-semibold text-foreground">
              Drop images here or browse
            </span>
            <span className="text-xs text-muted-foreground">
              JPG, PNG, WEBP, GIF · max 8 MB each
            </span>
            {imageError ? (
              <span className="tb-hint" data-tone="error">
                {imageError}
              </span>
            ) : null}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
              className="sr-only"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>

          {images.length > 0 ? (
            <ul className="tb-inv-thumbs mt-4">
              {images.map((img) => (
                <li key={img.id} className="tb-inv-thumb-card">
                  <button
                    type="button"
                    className="tb-inv-thumb-preview"
                    data-primary={img.id === primaryId}
                    onClick={() => setPrimaryId(img.id)}
                    title="Set as primary"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={img.preview} alt="" />
                    {img.id === primaryId ? (
                      <span className="tb-inv-thumb-badge">Primary</span>
                    ) : null}
                  </button>
                  <button
                    type="button"
                    className="tb-inv-thumb-remove"
                    onClick={() => removeImage(img.id)}
                    aria-label="Remove image"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              No images yet — you can also add them after creating the draft.
            </p>
          )}

          <div className="mt-6 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
            <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="ghost">
              Cancel
            </InventoryLinkBtn>
            <InventoryBtn
              type="submit"
              tone="accent" busy={pending} disabled={pending || !categoryId}
            >
              {pending ? "Creating…" : "Create draft →"}
            </InventoryBtn>
          </div>
        </InventoryPanel>
      </form>
    </div>
  );
}

export default function NewProductPage() {
  return (
    <PermissionGate permission="products.manage">
      <NewProductInner />
    </PermissionGate>
  );
}
