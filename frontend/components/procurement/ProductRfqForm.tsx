"use client";

import {
  InventoryBtn,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import { procurementApi } from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { productRfqSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

/** Product RFQ — quote a specific listed product from its owning supplier. */
export function ProductRfqForm() {
  const router = useRouter();
  const search = useSearchParams();
  const productId = search.get("product") || "";

  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState("100");
  const [targetPrice, setTargetPrice] = useState("");
  const [requiredBy, setRequiredBy] = useState("");
  const [requirements, setRequirements] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const rfqSchema = useMemo(
    () =>
      productRfqSchema.extend({
        quantity: productRfqSchema.shape.quantity.refine((value) => {
          const n = Number(value);
          const moq = product?.moq || 1;
          return Number.isFinite(n) && n >= moq;
        }, `Quantity must be at least the MOQ (${product?.moq || 1})`),
      }),
    [product?.moq],
  );
  const live = useLiveFields(rfqSchema, {
    quantity,
    targetPrice,
    requiredBy,
    requirements,
    notes,
  });

  useEffect(() => {
    if (!productId) {
      setLoading(false);
      setError("Missing product.");
      return;
    }
    void catalogApi
      .getProduct(productId)
      .then((p) => {
        setProduct(p);
        setQuantity(String(Math.max(1, p.moq || 1)));
        setTargetPrice(p.prices?.[0]?.unit_price ?? "");
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Product not found"),
      )
      .finally(() => setLoading(false));
  }, [productId]);

  async function submit(publish: boolean) {
    if (!product) return;
    if (!live.finish()) return;
    setBusy(true);
    setError(null);
    try {
      const rfq = await procurementApi.createProductRfq({
        product_id: product.id,
        quantity: quantity.trim(),
        unit: product.unit || "unit",
        target_unit_price: targetPrice.trim() || null,
        required_by: requiredBy ? new Date(`${requiredBy}T12:00:00`).toISOString() : null,
        requirements: requirements.trim() || null,
        notes: notes.trim() || null,
        currency: product.prices?.[0]?.currency || "USD",
        publish,
      });
      router.push(ROUTES.procurementRfq(rfq.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create quote request");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingEntity entity="product" />;
  if (!product) {
    return (
      <FeedbackBanner tone="error" title="Couldn't start this RFQ">
        {error || "Product missing"}
      </FeedbackBanner>
    );
  }

  const img =
    product.primary_image_url ||
    product.images?.find((i) => i.is_primary)?.url ||
    product.images?.[0]?.url;

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow="Product RFQ"
        title="Create RFQ"
        description={undefined}
        actions={
          <InventoryLinkBtn href={ROUTES.inventoryProduct(product.id)} tone="ghost">
            ← Back to product
          </InventoryLinkBtn>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Could not submit">
          {error}
        </FeedbackBanner>
      ) : null}

      <InventoryPanel title="Product">
        <div className="flex gap-4 px-5 pb-5">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-[#e8f2ec]">
            {img ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={mediaUrl(img)} alt="" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full items-center justify-center text-sm font-bold text-[#0d3b2a]">
                {product.name.slice(0, 2).toUpperCase()}
              </span>
            )}
          </div>
          <div>
            <p className="text-lg font-bold text-[#0c1612]">{product.name}</p>
            <p className="mt-1 text-sm text-[#5a6a62]">
              SKU: {product.sku || "—"}
              {" · "}
              Supplier: {product.supplier_name || "Supplier"}
            </p>
            <p className="mt-2 text-sm font-semibold text-[#0c1612]">
              Listed price:{" "}
              {product.prices?.[0]?.unit_price
                ? `${product.prices[0].currency} ${product.prices[0].unit_price}`
                : "—"}
            </p>
          </div>
        </div>
      </InventoryPanel>

      <InventoryPanel title="Your requirements">
        <div className="tb-inv-form-stack px-5 pb-5">
          <label data-state={live.errors.quantity ? "error" : undefined}>
            Quantity
            <NumberInput
              kind="integer"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              onBlur={() => live.touch("quantity")}
              placeholder={`MOQ ${product.moq}`}
            />
            <FieldError error={live.errors.quantity} />
          </label>
          <label data-state={live.errors.targetPrice ? "error" : undefined}>
            Your offer (unit price)
            <NumberInput
              kind="decimal"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              onBlur={() => live.touch("targetPrice")}
              placeholder={product.prices?.[0]?.unit_price || "Price you want to pay"}
            />
            <FieldError error={live.errors.targetPrice} />
          </label>
          <label>
            Required delivery date
            <input
              type="date"
              value={requiredBy}
              onChange={(e) => setRequiredBy(e.target.value)}
            />
          </label>
          <label>
            Additional requirements
            <textarea
              rows={4}
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              onBlur={() => live.touch("requirements")}
              placeholder="Customization, packaging, branding, samples…"
            />
            <FieldError error={live.errors.requirements} />
          </label>
          <label>
            Notes
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={() => live.touch("notes")}
            />
            <FieldError error={live.errors.notes} />
          </label>
          <div className="tb-inv-form-actions">
            <InventoryBtn tone="soft" busy={busy} disabled={busy} onClick={() => void submit(false)}>
              Save draft
            </InventoryBtn>
            <InventoryBtn tone="accent" busy={busy} disabled={busy} onClick={() => void submit(true)}>
              {busy ? "Submitting…" : "Submit RFQ"}
            </InventoryBtn>
          </div>
        </div>
      </InventoryPanel>
    </div>
  );
}
