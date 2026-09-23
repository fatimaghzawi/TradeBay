"use client";

import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { FieldError } from "@/components/ui/FormField";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  aiSourcingApi,
  type ProcurementRequirements,
  type RecommendationProduct,
  type RecommendationsResult,
  type SupplierMatch,
} from "@/lib/api/aiSourcingApi";
import { cartApi } from "@/lib/api/cartApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import {
  isProductSaved,
  PRODUCT_FAV_EVENT,
  toggleProductFavorite,
} from "@/lib/productFavorites";
import {
  isSupplierSaved,
  SHORTLIST_EVENT,
  toggleSupplier,
} from "@/lib/supplierShortlist";
import { openCartTray } from "@/lib/shoppingTrays";
import { sourcingLetterSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";

type Step = "describe" | "confirm" | "results";

type DetailTarget =
  | { kind: "product"; product: RecommendationProduct }
  | { kind: "supplier"; supplier: SupplierMatch };

const EXAMPLE =
  "I run a supermarket in Tyre. I sell food and household products. I am looking for beverage and cleaning-product suppliers. I usually buy in bulk every month and I need suppliers who can deliver to South Lebanon.";

function labelRelevance(value: string | null | undefined) {
  if (value === "highly_relevant") return "Strong fit";
  if (value === "relevant") return "Good fit";
  if (value === "partial") return "Similar";
  return "Match";
}

function scorePercent(score: number | null | undefined) {
  if (score == null || Number.isNaN(score)) return null;
  const pct = score <= 1 ? Math.round(score * 100) : Math.round(score);
  return Math.max(0, Math.min(100, pct));
}

function companyInitials(name: string | null | undefined) {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "TB";
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

function AISourcingExperienceInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>("describe");
  const [description, setDescription] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [requirements, setRequirements] = useState<ProcurementRequirements | null>(null);
  const [recs, setRecs] = useState<RecommendationsResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(Boolean(searchParams.get("request")));
  const promptFromQuery = searchParams.get("prompt");
  const imageRefreshFor = useRef<string | null>(null);
  const live = useLiveFields(sourcingLetterSchema, { description });

  useEffect(() => {
    if (!promptFromQuery) return;
    setDescription(promptFromQuery);
    setStep("describe");
  }, [promptFromQuery]);

  // From Ask the Bay / deep links: auto-run analyze once the prompt is filled.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!promptFromQuery || autoStarted.current || resuming) return;
    if (searchParams.get("request")) return;
    const trimmed = promptFromQuery.trim();
    if (trimmed.length < 12) return;
    autoStarted.current = true;
    setDescription(trimmed);
    setError(null);
    setBusy(true);
    void aiSourcingApi
      .analyze(trimmed)
      .then((result) => {
        setRequestId(result.sourcing_request_id);
        setRequirements(result.requirements);
        setStep("confirm");
      })
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : "We couldn't understand your description right now. Please try again.",
        );
      })
      .finally(() => setBusy(false));
  }, [promptFromQuery, resuming, searchParams]);

  useEffect(() => {
    const id = searchParams.get("request");
    if (!id) {
      setResuming(false);
      return;
    }
    let cancelled = false;
    setBusy(true);
    void aiSourcingApi
      .getRequest(id)
      .then((req) => {
        if (cancelled) return;
        setRequestId(req.id);
        const reqs = req.requirements as ProcurementRequirements | null;
        if (reqs && typeof reqs === "object" && "product_requirements" in reqs) {
          setRequirements(reqs);
        }
        const products = req.recommendations?.products ?? [];
        const suppliers = req.recommendations?.suppliers ?? [];
        if (products.length || suppliers.length) {
          setRecs({
            sourcing_request_id: req.id,
            status: req.status,
            products,
            suppliers,
            suggestions: [],
          });
          setStep("results");
        } else if (reqs) {
          setStep("confirm");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : "Could not open that sourcing request.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusy(false);
          setResuming(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  async function onAnalyze() {
    if (!live.finish()) return;
    setError(null);
    setBusy(true);
    try {
      const result = await aiSourcingApi.analyze(description.trim());
      setRequestId(result.sourcing_request_id);
      setRequirements(result.requirements);
      setStep("confirm");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "We couldn't understand your description right now. Please try again or enter your requirements manually.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!requestId || !requirements) return;
    setError(null);
    setBusy(true);
    try {
      const confirmed = await aiSourcingApi.confirm(requestId, requirements);
      setRequirements(confirmed.requirements);
      const found = await aiSourcingApi.recommend(requestId);
      setRecs(found);
      setStep("results");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "I couldn’t find matches right now. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  /** Refresh once if results are missing image URLs (stale client state). */
  useEffect(() => {
    if (step !== "results" || !requestId || !recs?.products.length) return;
    if (imageRefreshFor.current === requestId) return;
    const missingImages = recs.products.some(
      (p) => p.product_id && !p.primary_image_url,
    );
    if (!missingImages) {
      imageRefreshFor.current = requestId;
      return;
    }
    imageRefreshFor.current = requestId;
    let cancelled = false;
    void aiSourcingApi
      .getRequest(requestId)
      .then((req) => {
        if (cancelled || !req.recommendations?.products?.length) return;
        setRecs((prev) => ({
          sourcing_request_id: req.id,
          status: req.status,
          products: req.recommendations.products,
          suppliers: req.recommendations.suppliers || [],
          suggestions: prev?.suggestions ?? [],
        }));
      })
      .catch(() => {
        /* keep existing cards */
      });
    return () => {
      cancelled = true;
    };
  }, [step, requestId, recs]);

  function resetFlow() {
    setStep("describe");
    setDescription("");
    setRequestId(null);
    setRequirements(null);
    setRecs(null);
    setError(null);
    imageRefreshFor.current = null;
    if (searchParams.get("request") || searchParams.get("prompt")) {
      router.replace(ROUTES.aiSourcing);
    }
  }

  return (
    <div className="tb-src" data-step={step} data-busy={busy || undefined}>
      <DirectoryMast
        title="Ask the Bay"
        size="page"
        lede="Describe what you want to source."
      />

      <div className="tb-src-body">
        {resuming ? (
          <FeedbackBanner tone="info" title="Loading sourcing request">
            Preparing the request linked from your business plan…
          </FeedbackBanner>
        ) : null}

        {error ? (
          <FeedbackBanner tone="error" title="Couldn’t prepare recommendations" onDismiss={() => setError(null)}>
            {error}
          </FeedbackBanner>
        ) : null}

        {step === "describe" && !resuming ? (
          <section className="tb-src-letter">
            <div className="tb-src-letter-seal" aria-hidden>
              <span>TB</span>
            </div>
            <p className="tb-src-letter-to">To the bay,</p>
            <label className="sr-only" htmlFor="src-desc">
              Your letter
            </label>
            <textarea
              id="src-desc"
              className="tb-src-letter-body"
              rows={8}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={() => live.touch("description")}
              placeholder={EXAMPLE}
              disabled={busy}
            />
            <FieldError error={live.errors.description} />
            <div className="tb-src-letter-foot">
              <div className="tb-src-inks" aria-label="Quick starters">
                {[
                  { label: "Tyre supermarket", text: EXAMPLE },
                  {
                    label: "Beirut hotel kitchen",
                    text: "I manage a hotel restaurant in Beirut. I need pantry staples, olive oil, rice, pasta, and kitchen housewares for monthly bulk restocking. Prefer verified local suppliers who can deliver to Beirut.",
                  },
                  {
                    label: "Mount Lebanon contractor",
                    text: "I am a contractor based in Mount Lebanon. I need construction materials and hardware in bulk, with reliable delivery to Beirut and the South.",
                  },
                ].map((ink) => (
                  <button
                    key={ink.label}
                    type="button"
                    className="tb-src-ink"
                    disabled={busy}
                    onClick={() => setDescription(ink.text)}
                  >
                    {ink.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="tb-src-cast"
                disabled={busy || description.trim().length < 8}
                onClick={() => void onAnalyze()}
              >
                <BusyText busy={busy}>{busy ? "Preparing recommendations…" : "Cast to the bay →"}</BusyText>
              </button>
            </div>
          </section>
        ) : null}

        {step === "confirm" && requirements ? (
          <section className="tb-src-sheet">
            <div className="tb-src-sheet-top">
              <div>
                <h2>Edit your requirements</h2>
                <p>Review your brief, then search.</p>
              </div>
            </div>

            <dl className="tb-src-mosaic">
              <div>
                <dt>
                  <label htmlFor="src-biz">Business</label>
                </dt>
                <dd>
                  <input
                    id="src-biz"
                    value={requirements.business_type ?? ""}
                    onChange={(e) =>
                      setRequirements({
                        ...requirements,
                        business_type: e.target.value || null,
                      })
                    }
                    placeholder="e.g. supermarket"
                    disabled={busy}
                  />
                </dd>
              </div>
              <div>
                <dt>
                  <label htmlFor="src-loc">Location</label>
                </dt>
                <dd>
                  <input
                    id="src-loc"
                    value={requirements.location ?? ""}
                    onChange={(e) =>
                      setRequirements({
                        ...requirements,
                        location: e.target.value || null,
                      })
                    }
                    placeholder="e.g. Tyre, South Lebanon"
                    disabled={busy}
                  />
                </dd>
              </div>
            </dl>

            <div className="tb-src-row">
              <button type="button" className="tb-src-ghost" onClick={resetFlow}>
                Start over
              </button>
              <button
                type="button"
                className="tb-src-cast"
                disabled={busy}
                onClick={() => void onConfirm()}
              >
                <BusyText busy={busy}>{busy ? "Preparing recommendations…" : "Find suppliers →"}</BusyText>
              </button>
            </div>
          </section>
        ) : null}

        {step === "results" && recs ? (
          <ResultsView
            recs={recs}
            onBack={() => setStep("confirm")}
            onRestart={resetFlow}
          />
        ) : null}
      </div>
    </div>
  );
}

export function AISourcingExperience() {
  return (
    <Suspense
      fallback={
        <div className="tb-src">
          <LoadingEntity entity="AI Sourcing" />
        </div>
      }
    >
      <AISourcingExperienceInner />
    </Suspense>
  );
}

function ResultsView({
  recs,
  onBack,
  onRestart,
}: {
  recs: RecommendationsResult;
  onBack: () => void;
  onRestart: () => void;
}) {
  const [lane, setLane] = useState<"products" | "suppliers">("products");
  const [detail, setDetail] = useState<DetailTarget | null>(null);
  const hasMatches = recs.products.length > 0 || recs.suppliers.length > 0;
  const strongFits = recs.products.filter((p) => p.relevance_label === "highly_relevant").length;
  const verifiedSuppliers = recs.suppliers.filter((s) => s.verified).length;
  const similarHeavy =
    hasMatches &&
    (recs.suggestions.some((s) => /similar/i.test(s)) ||
      recs.products.filter((p) => p.relevance_label === "partial").length >=
        Math.ceil(recs.products.length * 0.6));
  const topCatch = [...recs.products].sort(
    (a, b) => (b.match_score ?? 0) - (a.match_score ?? 0),
  )[0];
  const restProducts = topCatch
    ? recs.products.filter((p) => p.id !== topCatch.id)
    : recs.products;

  const productsForSupplier = (supplierId: string) =>
    recs.products.filter((p) => p.supplier_id === supplierId);

  return (
    <section className="tb-src-sheet tb-src-haul">
      <div className="tb-src-sheet-top">
        <div>
          <p className="tb-src-catch-kicker">Your catch</p>
          <h2>What floated back</h2>
          <p>Matching products from the catalog.</p>
        </div>
      </div>

      <div className="tb-src-tide" aria-hidden>
        <span />
        <span />
        <span />
      </div>

      {similarHeavy ? (
        <FeedbackBanner tone="info" title="Close matches from the bay">
          Similar products that may fit your brief.
        </FeedbackBanner>
      ) : null}

      {hasMatches ? (
        <ul className="tb-src-haul-stats">
          <li>
            <strong>{recs.products.length}</strong>
            <span>products</span>
          </li>
          <li>
            <strong>{recs.suppliers.length}</strong>
            <span>suppliers</span>
          </li>
          <li>
            <strong>{strongFits || "—"}</strong>
            <span>strong fits</span>
          </li>
          <li>
            <strong>{verifiedSuppliers || "—"}</strong>
            <span>verified</span>
          </li>
        </ul>
      ) : null}

      {!hasMatches ? (
        <div className="tb-src-empty-bay">
          <p className="tb-src-empty-bay-title">No verified listings available yet</p>
          <p>Once suppliers publish matching products, they’ll appear here. Meanwhile try:</p>
          <ul>
            {(recs.suggestions.length
              ? recs.suggestions
              : ["broader product names", "related categories", "checking with platform staff"]
            ).map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <div className="tb-src-row">
            <button type="button" className="tb-src-ghost" onClick={onBack}>
              Edit details
            </button>
            <button type="button" className="tb-src-cast" onClick={onRestart}>
              New cast
            </button>
          </div>
        </div>
      ) : (
        <>
          {lane === "products" && topCatch ? (
            <TopCatchHero
              product={topCatch}
              onOpen={() => setDetail({ kind: "product", product: topCatch })}
            />
          ) : null}

          <div className="tb-src-lanes" role="tablist" aria-label="Results">
            <button
              type="button"
              role="tab"
              aria-selected={lane === "products"}
              data-active={lane === "products"}
              onClick={() => setLane("products")}
            >
              Product buoys <em>{recs.products.length}</em>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={lane === "suppliers"}
              data-active={lane === "suppliers"}
              onClick={() => setLane("suppliers")}
            >
              Supplier buoys <em>{recs.suppliers.length}</em>
            </button>
          </div>

          <div className="tb-src-fleet tb-src-fleet-catch" data-lane={lane}>
            {lane === "products"
              ? restProducts.map((product, index) => (
                  <ProductBuoy
                    key={product.id}
                    product={product}
                    index={index}
                    onOpen={() => setDetail({ kind: "product", product })}
                  />
                ))
              : recs.suppliers.map((supplier, index) => (
                  <SupplierBuoy
                    key={supplier.supplier_id}
                    supplier={supplier}
                    index={index}
                    onOpen={() => setDetail({ kind: "supplier", supplier })}
                  />
                ))}
          </div>

          <div className="tb-src-row">
            <button type="button" className="tb-src-ghost" onClick={onBack}>
              Edit details
            </button>
            <button type="button" className="tb-src-cast" onClick={onRestart}>
              New cast
            </button>
          </div>
        </>
      )}

      <Modal
        open={detail != null}
        onClose={() => setDetail(null)}
        title={
          detail?.kind === "product"
            ? detail.product.product_name || "Product"
            : detail?.kind === "supplier"
              ? detail.supplier.supplier_name
              : "Detail"
        }
        kicker={detail?.kind === "product" ? "Product buoy" : "Supplier buoy"}
        asideTitle={
          detail?.kind === "product"
            ? "Pulled from the catalog"
            : "A company that answered"
        }
        asideBody={
          detail?.kind === "product"
            ? "Add it to cart or favorite it for later — no need to leave this cast."
            : "Save them for later, or open a matching product from this catch."
        }
        mark="shield"
        footer={
          detail ? (
            detail.kind === "product" ? (
              <ProductMatchActions product={detail.product} />
            ) : (
              <MatchCompanyActions
                supplierId={detail.supplier.supplier_id}
                supplierName={detail.supplier.supplier_name}
                verified={detail.supplier.verified}
              />
            )
          ) : null
        }
      >
        {detail?.kind === "product" ? (
          <ProductDetail product={detail.product} />
        ) : detail?.kind === "supplier" ? (
          <SupplierDetail
            supplier={detail.supplier}
            products={productsForSupplier(detail.supplier.supplier_id)}
            onOpenProduct={(product) => setDetail({ kind: "product", product })}
          />
        ) : null}
      </Modal>
    </section>
  );
}

function useShortlistSaved(supplierId: string | null | undefined) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!supplierId) {
      setSaved(false);
      return;
    }
    const sync = () => setSaved(isSupplierSaved(supplierId));
    sync();
    window.addEventListener(SHORTLIST_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(SHORTLIST_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [supplierId]);

  return saved;
}

function useProductFavoriteSaved(productId: string | null | undefined) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!productId) {
      setSaved(false);
      return;
    }
    const sync = () => setSaved(isProductSaved(productId));
    sync();
    window.addEventListener(PRODUCT_FAV_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(PRODUCT_FAV_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [productId]);

  return saved;
}

function MatchCompanyActions({
  supplierId,
  supplierName,
  verified,
}: {
  supplierId: string | null | undefined;
  supplierName: string | null | undefined;
  verified?: boolean;
}) {
  const saved = useShortlistSaved(supplierId);
  if (!supplierId) return null;
  const name = supplierName?.trim() || "Supplier";

  return (
    <div className="tb-src-card-acts">
      <button
        type="button"
        data-active={saved || undefined}
        onClick={() => toggleSupplier({ id: supplierId, name, verified })}
      >
        {saved ? "Saved" : "Save for later"}
      </button>
    </div>
  );
}

function ProductMatchActions({ product }: { product: RecommendationProduct }) {
  const productId = product.product_id;
  const saved = useProductFavoriteSaved(productId);
  const { success, error: toastError } = useToast();
  const [cartPending, setCartPending] = useState(false);
  const [inCart, setInCart] = useState(false);

  useEffect(() => {
    if (!productId) {
      setInCart(false);
      return;
    }
    let cancelled = false;
    void cartApi
      .get()
      .then((cart) => {
        if (!cancelled) {
          setInCart(cart.items.some((item) => item.product_id === productId));
        }
      })
      .catch(() => {
        if (!cancelled) setInCart(false);
      });
    return () => {
      cancelled = true;
    };
  }, [productId]);

  if (!productId) return null;

  const qty = Math.max(1, product.moq || 1);

  return (
    <div className="tb-src-card-acts">
      <button
        type="button"
        disabled={cartPending}
        data-active={inCart || undefined}
        onClick={() => {
          if (inCart) {
            openCartTray();
            return;
          }
          setCartPending(true);
          void cartApi
            .addItem(productId, qty)
            .then((cart) => {
              setInCart(true);
              success(
                "Added to cart",
                `${cart.item_count} item${cart.item_count === 1 ? "" : "s"} in cart`,
              );
            })
            .catch((err) => {
              toastError(
                "Could not add",
                err instanceof ApiError ? err.message : "Couldn't add this product.",
              );
            })
            .finally(() => setCartPending(false));
        }}
      >
        {cartPending ? "Adding…" : inCart ? "In cart" : "Add to cart"}
      </button>
      <button
        type="button"
        data-active={saved || undefined}
        onClick={() =>
          toggleProductFavorite({
            id: productId,
            name: product.product_name || "Product",
            image: product.primary_image_url,
          })
        }
      >
        {saved ? "Favorited" : "Add to favorite"}
      </button>
    </div>
  );
}

function TopCatchHero({
  product,
  onOpen,
}: {
  product: RecommendationProduct;
  onOpen: () => void;
}) {
  const image = mediaUrl(product.primary_image_url);
  const [broken, setBroken] = useState(false);
  const showImage = Boolean(image) && !broken;
  const pct = scorePercent(product.match_score);

  return (
    <article className="tb-src-top-catch">
      <button type="button" className="tb-src-top-catch__hit" onClick={onOpen}>
        <div className="tb-src-top-catch__media" aria-hidden={!showImage}>
          {showImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={image} alt="" onError={() => setBroken(true)} />
          ) : (
            <span>{companyInitials(product.product_name)}</span>
          )}
        </div>
        <div className="tb-src-top-catch__copy">
          <p className="tb-src-catch-kicker">Top of the catch</p>
          <h3>{product.product_name}</h3>
          <p className="tb-verified-inline">
            {product.supplier_name}
            <VerifiedBadge
              verified={Boolean(product.supplier_verified)}
              showWhenUnverified={false}
            />
            {product.category_name ? ` · ${product.category_name}` : ""}
          </p>
          {product.reasons[0] ? (
            <blockquote>“{product.reasons[0]}”</blockquote>
          ) : null}
          <div className="tb-src-top-catch__meta">
            <span>{labelRelevance(product.relevance_label)}</span>
            {pct != null ? <span>{pct}% fit</span> : null}
            <span>
              {product.unit_price
                ? `${product.currency ?? ""} ${product.unit_price}`.trim()
                : "Ask for price"}
            </span>
          </div>
          <em>Open buoy →</em>
        </div>
      </button>
      <ProductMatchActions product={product} />
    </article>
  );
}

function ProductBuoy({
  product,
  index,
  onOpen,
}: {
  product: RecommendationProduct;
  index: number;
  onOpen: () => void;
}) {
  const image = mediaUrl(product.primary_image_url);
  const [broken, setBroken] = useState(false);
  const showImage = Boolean(image) && !broken;
  const pct = scorePercent(product.match_score);

  return (
    <article
      className="tb-src-card tb-src-card-product tb-src-buoy"
      style={{ animationDelay: `${Math.min(index, 12) * 0.06}s` }}
    >
      <button type="button" className="tb-src-buoy-hit" onClick={onOpen}>
        <div className="tb-src-card-media" aria-hidden={!showImage}>
          {showImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={image} alt="" onError={() => setBroken(true)} />
          ) : (
            <span className="tb-src-card-media-empty">No image</span>
          )}
          <em className="tb-src-buoy-tag">{labelRelevance(product.relevance_label)}</em>
        </div>
        <header>
          <div>
            <h3>{product.product_name}</h3>
            <p>
              <span className="tb-verified-inline">
                {product.supplier_name}
                <VerifiedBadge
                  verified={Boolean(product.supplier_verified)}
                  showWhenUnverified={false}
                />
              </span>
              {product.category_name ? ` · ${product.category_name}` : ""}
            </p>
          </div>
          {pct != null ? <span className="tb-src-score">{pct}%</span> : null}
        </header>
        <dl>
          <div>
            <dt>MOQ</dt>
            <dd>{product.moq ?? "—"}</dd>
          </div>
          <div>
            <dt>Stock</dt>
            <dd>{product.availability_status.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Price</dt>
            <dd>
              {product.unit_price
                ? `${product.currency ?? ""} ${product.unit_price}`.trim()
                : "Ask"}
            </dd>
          </div>
        </dl>
        {product.reasons[0] ? (
          <p className="tb-src-buoy-why">“{product.reasons[0]}”</p>
        ) : null}
        {pct != null ? (
          <div className="tb-src-pulse" aria-hidden>
            <i style={{ width: `${pct}%` }} />
          </div>
        ) : null}
        <span className="tb-src-open-hint">Look closer →</span>
      </button>
      <ProductMatchActions product={product} />
    </article>
  );
}

function SupplierBuoy({
  supplier,
  index,
  onOpen,
}: {
  supplier: SupplierMatch;
  index: number;
  onOpen: () => void;
}) {
  return (
    <article
      className="tb-src-card tb-src-card-company tb-src-buoy"
      style={{ animationDelay: `${Math.min(index, 12) * 0.06}s` }}
    >
      <button type="button" className="tb-src-buoy-hit" onClick={onOpen}>
        <div className="tb-src-company-mark" aria-hidden>
          {companyInitials(supplier.supplier_name)}
        </div>
        <header>
          <div>
            <h3 className="tb-verified-inline">
              {supplier.supplier_name}
              <VerifiedBadge
                verified={Boolean(supplier.verified)}
                showWhenUnverified={false}
              />
            </h3>
            <p>
              {supplier.product_count} matching product
              {supplier.product_count === 1 ? "" : "s"}
            </p>
          </div>
          <span className="tb-src-score">{labelRelevance(supplier.relevance_label)}</span>
        </header>
        {supplier.reasons.length ? (
          <ul className="tb-src-why-list">
            {supplier.reasons.slice(0, 2).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        <span className="tb-src-open-hint">Look closer →</span>
      </button>
      <MatchCompanyActions
        supplierId={supplier.supplier_id}
        supplierName={supplier.supplier_name}
        verified={supplier.verified}
      />
    </article>
  );
}

function ProductDetail({ product }: { product: RecommendationProduct }) {
  const image = mediaUrl(product.primary_image_url);
  const [broken, setBroken] = useState(false);
  const showImage = Boolean(image) && !broken;
  const pct = scorePercent(product.match_score);

  return (
    <div className="tb-src-detail">
      <div className="tb-src-detail-media">
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt="" onError={() => setBroken(true)} />
        ) : (
          <span>No image on this buoy</span>
        )}
      </div>

      <dl className="tb-src-detail-grid">
        <div>
          <dt>Supplier</dt>
          <dd className="tb-verified-inline">
            {product.supplier_name || "—"}
            <VerifiedBadge
              verified={Boolean(product.supplier_verified)}
              showWhenUnverified={false}
            />
          </dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{product.category_name || "—"}</dd>
        </div>
        <div>
          <dt>MOQ</dt>
          <dd>
            {product.moq ?? "—"}
            {product.unit ? ` ${product.unit}` : ""}
          </dd>
        </div>
        <div>
          <dt>Price</dt>
          <dd>
            {product.unit_price
              ? `${product.currency ?? ""} ${product.unit_price}`.trim()
              : "Ask"}
          </dd>
        </div>
        <div>
          <dt>Stock</dt>
          <dd>{product.availability_status.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Fit</dt>
          <dd>
            {labelRelevance(product.relevance_label)}
            {pct != null ? ` · ${pct}%` : ""}
          </dd>
        </div>
      </dl>

      {pct != null ? (
        <div className="tb-src-pulse" aria-hidden>
          <i style={{ width: `${pct}%` }} />
        </div>
      ) : null}

      {product.reasons.length ? (
        <div className="tb-src-detail-block">
          <h4>Why it floated up</h4>
          <ul>
            {product.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {product.matched_requirements.length ? (
        <div className="tb-src-detail-block">
          <h4>Matched</h4>
          <ul>
            {product.matched_requirements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SupplierDetail({
  supplier,
  products,
  onOpenProduct,
}: {
  supplier: SupplierMatch;
  products: RecommendationProduct[];
  onOpenProduct: (product: RecommendationProduct) => void;
}) {
  return (
    <div className="tb-src-detail">
      <div className="tb-sup-profile-hero">
        <div className="tb-src-company-mark tb-src-company-mark-lg" aria-hidden>
          {companyInitials(supplier.supplier_name)}
        </div>
        <div>
          <h3 className="tb-verified-inline">
            {supplier.supplier_name}
            <VerifiedBadge
              verified={Boolean(supplier.verified)}
              showWhenUnverified={false}
            />
          </h3>
          <p>
            {supplier.product_count} matching product
            {supplier.product_count === 1 ? "" : "s"} ·{" "}
            {labelRelevance(supplier.relevance_label)}
          </p>
        </div>
      </div>

      {supplier.reasons.length ? (
        <div className="tb-src-detail-block">
          <h4>Why they answered</h4>
          <ul>
            {supplier.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {supplier.matched_requirements.length ? (
        <div className="tb-src-detail-block">
          <h4>Matched</h4>
          <ul>
            {supplier.matched_requirements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {products.length ? (
        <div className="tb-src-detail-block">
          <h4>Products in this catch</h4>
          <ul className="tb-src-detail-products">
            {products.map((product) => (
              <li key={product.id}>
                <button type="button" onClick={() => onOpenProduct(product)}>
                  <span>{product.product_name || "Product"}</span>
                  <span>
                    {product.unit_price
                      ? `${product.currency ?? ""} ${product.unit_price}`.trim()
                      : "Ask"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
