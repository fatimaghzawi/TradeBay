"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import {
  isSupplierSaved,
  SHORTLIST_EVENT,
  toggleSupplier,
} from "@/lib/supplierShortlist";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

function SupplierProfileInner() {
  const params = useParams<{ id: string }>();
  const supplierId = params.id;

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const refreshSaved = useCallback(() => {
    setSaved(isSupplierSaved(supplierId));
  }, [supplierId]);

  useEffect(() => {
    refreshSaved();
    window.addEventListener(SHORTLIST_EVENT, refreshSaved);
    window.addEventListener("storage", refreshSaved);
    return () => {
      window.removeEventListener(SHORTLIST_EVENT, refreshSaved);
      window.removeEventListener("storage", refreshSaved);
    };
  }, [refreshSaved]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void catalogApi
      .listProducts({
        supplier_business_id: supplierId,
        status: "active",
        include_details: true,
        page: 1,
        page_size: 100,
      })
      .then((result) => setProducts(result.data))
      .catch((err) => {
        setProducts([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load this supplier.");
      })
      .finally(() => setLoading(false));
  }, [supplierId]);

  const supplierName = useMemo(() => {
    const fromProduct = products.find((p) => p.supplier_name)?.supplier_name;
    return fromProduct?.trim() || "Supplier";
  }, [products]);

  const isVerified = products.some((p) => Boolean(p.supplier_verified));
  const logo = products.find((p) => p.supplier_logo_url)?.supplier_logo_url ?? null;

  function onToggleSave() {
    const result = toggleSupplier({ id: supplierId, name: supplierName });
    setSaved(result.saved);
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow="Suppliers"
        title={supplierName}
        description="This supplier’s catalog."
        meta={
          <span className="tb-inv-chip">
            {products.length} product{products.length === 1 ? "" : "s"}
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="tb-inv-btn tb-inv-btn-soft"
              onClick={onToggleSave}
            >
              {saved ? "Saved for later ✓" : "Save for later"}
            </button>
            <InventoryLinkBtn href={ROUTES.supplierProducts(supplierId)} tone="accent">
              See products in bay →
            </InventoryLinkBtn>
          </div>
        }
      />

      <section className="tb-sup-profile-hero" aria-label="Supplier">
        <div className="tb-sup-profile-avatar" aria-hidden>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={mediaUrl(logo)} alt="" />
          ) : (
            <span>{supplierName.slice(0, 2).toUpperCase()}</span>
          )}
        </div>
        <div className="min-w-0">
          <p className="tb-sup-profile-kicker">TradeBay supplier</p>
          <h2 className="tb-sup-profile-name tb-verified-inline">
            {supplierName}
            <VerifiedBadge
              verified={isVerified}
              showWhenUnverified={false}
              size="md"
            />
          </h2>
          <p className="tb-sup-profile-copy">
            Open any product for details, MOQ, and availability — or keep this company on your
            shortlist for the next order cycle.
          </p>
        </div>
      </section>

      <InventoryPanel title="Their products">
        {error ? (
          <FeedbackBanner tone="error" title="Couldn’t load products" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="products" />
        ) : products.length === 0 ? (
          <InventoryEmpty
            mark="◎"
            title="No active products yet"
            body="This supplier has no active listings right now. Save them for later and check back."
            action={
              <InventoryLinkBtn href={ROUTES.aiSourcing} tone="soft">
                Back to Ask the Bay
              </InventoryLinkBtn>
            }
          />
        ) : (
          <div className="tb-mkt-grid">
            {products.map((product) => {
              const image =
                product.primary_image_url ||
                product.images?.find((img) => img.is_primary)?.url ||
                product.images?.[0]?.url ||
                null;
              const price = product.prices?.find((p) => p.is_active);
              return (
                <Link
                  key={product.id}
                  href={ROUTES.inventoryProduct(product.id)}
                  className="tb-mkt-card"
                >
                  <div className="tb-mkt-card-media" aria-hidden>
                    {image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(image)} alt="" />
                    ) : (
                      <span>{product.name.slice(0, 1)}</span>
                    )}
                  </div>
                  <div className="tb-mkt-card-body">
                    <h3 className="tb-mkt-card-title">{product.name}</h3>
                    <p className="tb-mkt-card-meta">
                      SKU {product.sku}
                      {product.moq ? ` · MOQ ${product.moq}` : ""}
                    </p>
                    <div className="tb-mkt-card-foot">
                      <strong>
                        {price
                          ? `${price.currency} ${price.unit_price}`
                          : "Ask for quote"}
                      </strong>
                      <span>View & order →</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </InventoryPanel>
    </div>
  );
}

export default function SupplierProfilePage() {
  return (
    <PermissionGate permission="products.read" allowGuest>
      <SupplierProfileInner />
    </PermissionGate>
  );
}
