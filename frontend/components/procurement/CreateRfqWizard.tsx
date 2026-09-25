"use client";

import {
  InventoryBtn,
  InventoryLinkBtn,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { DealHandshake } from "@/components/procurement/DealHandshake";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import {
  procurementApi,
  type CreateRFQItemInput,
  type EligibleSupplier,
} from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { issuesToFieldMap } from "@/lib/validation/common";
import { rfqLineSchema, sourcingBasicsSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { BackLink } from "@/components/ui/BackLink";

type DraftItem = CreateRFQItemInput & { key: string };

const STEPS = [
  { em: "01", label: "Name it", hint: "Title the brief" },
  { em: "02", label: "Goods", hint: "Load the table" },
  { em: "03", label: "Seats", hint: "Who sits opposite" },
  { em: "04", label: "Handshake", hint: "Send the ask" },
] as const;

function productToLine(p: Product): DraftItem {
  return {
    key: `${p.id}-${Date.now()}`,
    product_id: p.id,
    product_name: p.name,
    sku: p.sku,
    quantity: String(Math.max(1, p.moq || 1)),
    unit: p.unit || "unit",
    catalog_unit_price: p.prices?.[0]?.unit_price ?? null,
    target_unit_price: p.prices?.[0]?.unit_price ?? "",
    category_id: p.category_id,
    supplier_business_id: p.business_account_id || null,
    primary_image_url:
      p.primary_image_url ||
      p.images?.find((i) => i.is_primary)?.url ||
      p.images?.[0]?.url ||
      null,
  };
}

export function CreateRfqWizard(_props?: { mode?: "catalog" | "sourcing" | "legacy" }) {
  const router = useRouter();
  const { business } = useAuth();
  const search = useSearchParams();
  const productParam = search.get("product");
  const suppliersParam = search.get("suppliers");

  const [step, setStep] = useState(0);
  const [stepDir, setStepDir] = useState<"forward" | "back">("forward");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<DraftItem[]>([]);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [q, setQ] = useState("");
  const [rfqId, setRfqId] = useState<string | null>(null);
  const [eligible, setEligible] = useState<EligibleSupplier[]>([]);
  const [selectedSuppliers, setSelectedSuppliers] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [itemsSubmitted, setItemsSubmitted] = useState(false);
  const [itemTouched, setItemTouched] = useState<Record<string, boolean>>({});
  const [handshakeTo, setHandshakeTo] = useState<string | null>(null);
  const basicsLive = useLiveFields(sourcingBasicsSchema, {
    title,
    notes,
  });

  const buyerName = business?.name || "You";
  const selectedProductIds = useMemo(
    () => new Set(items.map((it) => it.product_id).filter(Boolean) as string[]),
    [items],
  );
  const seated = useMemo(
    () => eligible.filter((s) => selectedSuppliers.includes(s.supplier_business_id)),
    [eligible, selectedSuppliers],
  );

  useEffect(() => {
    if (productParam) {
      router.replace(ROUTES.procurementProductQuote(productParam));
    }
  }, [productParam, router]);

  useEffect(() => {
    setCatalogLoading(true);
    void catalogApi
      .listProducts({
        page_size: 48,
        q: q || undefined,
        status: "active",
        include_details: true,
      })
      .then((res) => setCatalog(res.data))
      .catch(() => setCatalog([]))
      .finally(() => setCatalogLoading(false));
  }, [q]);

  function updateItem(key: string, patch: Partial<DraftItem>) {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  }

  function toggleProduct(p: Product) {
    setItems((prev) => {
      const existing = prev.find((it) => it.product_id === p.id);
      if (existing) return prev.filter((it) => it.product_id !== p.id);
      return [...prev, productToLine(p)];
    });
    if (!title.trim()) setTitle(`${p.name} procurement`);
  }

  function lineErrors(it: DraftItem) {
    const parsed = rfqLineSchema.safeParse({
      product_name: it.product_name,
      quantity: it.quantity,
      target_unit_price: it.target_unit_price ?? "",
    });
    if (parsed.success) return {} as Record<string, string>;
    return issuesToFieldMap(parsed.error.issues);
  }

  function showLineErrors(it: DraftItem) {
    return itemsSubmitted || itemTouched[it.key];
  }

  function catalogItems() {
    return items.filter((it) => it.product_id && it.product_name.trim());
  }

  function itemsValid() {
    const named = catalogItems();
    if (!named.length) return false;
    return named.every((it) => Object.keys(lineErrors(it)).length === 0);
  }

  function goTo(next: number) {
    setStepDir(next < step ? "back" : "forward");
    setStep(next);
  }

  async function saveDraft() {
    if (!basicsLive.finish()) {
      goTo(0);
      return null;
    }
    setItemsSubmitted(true);
    const named = catalogItems();
    if (!named.length) {
      setError("Pick at least one product from the marketplace");
      goTo(1);
      return null;
    }
    if (!itemsValid()) {
      setError("Fix quantities and prices before saving.");
      goTo(1);
      return null;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        description: null,
        destination: { city: "Beirut", governorate: "Beirut", country: "Lebanon" },
        required_by: null,
        notes: notes || null,
        currency: "USD",
        visibility: "open",
        items: named.map(({ key: _k, ...rest }) => ({
          ...rest,
          target_unit_price: (rest.target_unit_price ?? "").trim() || null,
          sku: rest.sku || null,
        })),
      };
      const first = payload.items[0];
      if (!first) {
        setError("Pick at least one product from the marketplace");
        goTo(1);
        return null;
      }
      const rfq = rfqId
        ? await procurementApi.updateRfq(rfqId, payload)
        : await procurementApi.createSourcingRfq({
            title: payload.title,
            description: payload.description,
            requirements: payload.description,
            quantity: first.quantity,
            unit: first.unit || "unit",
            target_unit_price: first.target_unit_price,
            destination: payload.destination,
            required_by: payload.required_by,
            notes: payload.notes,
            currency: "USD",
            visibility: "open",
            items: payload.items,
            publish: false,
          });
      setRfqId(rfq.id);
      return rfq;
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Couldn't save",
      );
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function goSuppliers() {
    const rfq = await saveDraft();
    if (!rfq) return;
    setBusy(true);
    try {
      const list = await procurementApi.eligibleSuppliers(rfq.id);
      setEligible(list);
      const matched = list
        .filter(
          (s) =>
            (s.can_invite ?? s.verified) &&
            (s.product_match || (s.products?.length ?? 0) > 0),
        )
        .map((s) => s.supplier_business_id);
      const preselected = (suppliersParam || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (preselected.length) {
        const allowed = new Set(
          list.filter((s) => s.can_invite ?? s.verified).map((s) => s.supplier_business_id),
        );
        setSelectedSuppliers(preselected.filter((id) => allowed.has(id)));
      } else if (matched.length) {
        setSelectedSuppliers(matched);
      } else {
        setSelectedSuppliers([]);
      }
      setStepDir("forward");
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load suppliers");
    } finally {
      setBusy(false);
    }
  }

  async function publishAndInvite() {
    if (!rfqId) return;
    setBusy(true);
    setError(null);
    try {
      const hasCatalogProducts = items.some((item) => item.product_id);
      let nextHref = ROUTES.procurementRfq(rfqId);
      if (hasCatalogProducts) {
        const result = await procurementApi.sendRfq(rfqId);
        const nextId = result.rfq?.id || result.sent?.[0]?.id || rfqId;
        const sent = result.sent?.length || 1;
        nextHref = `${ROUTES.procurementRfq(nextId)}?sent=${sent}`;
      } else if (selectedSuppliers.length) {
        const current = await procurementApi.getRfq(rfqId);
        if (current.status === "draft") {
          await procurementApi.publishRfq(rfqId);
        }
        await procurementApi.inviteSuppliers(rfqId, selectedSuppliers);
        nextHref = `${ROUTES.procurementRfq(rfqId)}?sent=${selectedSuppliers.length}`;
      }
      setHandshakeTo(nextHref);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send RFQ");
    } finally {
      setBusy(false);
    }
  }

  const finishHandshake = useCallback(() => {
    if (!handshakeTo) return;
    const href = handshakeTo;
    setHandshakeTo(null);
    router.push(href);
  }, [handshakeTo, router]);

  const named = catalogItems();
  const supplierLabel =
    seated[0]?.name ||
    (selectedSuppliers.length ? `${selectedSuppliers.length} suppliers` : "Suppliers");

  return (
    <div className="tb-inv-page tb-deal tb-rfq-flow" data-step={step} data-dir={stepDir}>
      {handshakeTo ? (
        <DealHandshake
          buyerName={buyerName}
          supplierName={supplierLabel}
          headline="Ask sent"
          detail="The brief is on their table. Opening the deal room…"
          onDone={finishHandshake}
          durationMs={2400}
        />
      ) : null}

      <header className="tb-deal-hero tb-rfq-flow__hero">
        <div className="tb-deal-hero__top">
          <p className="tb-deal-stamp">New RFQ</p>
          <p className="tb-deal-status">Create RFQ</p>
          <div className="tb-deal-hero__actions">
            <BackLink href={ROUTES.procurement}>Procurement</BackLink>
          </div>
        </div>
        <h1 className="tb-deal-title">Build the ask across the table</h1>
        <ol className="tb-deal-rail tb-rfq-flow__rail" aria-label="RFQ steps">
          {STEPS.map((meta, i) => (
            <li
              key={meta.label}
              data-state={i === step ? "now" : i < step ? "done" : undefined}
            >
              <button
                type="button"
                className="tb-rfq-flow__rail-btn"
                onClick={() => {
                  if (i < step) goTo(i);
                }}
              >
                <span>{meta.em}</span>
                <strong>{meta.label}</strong>
                <em>{meta.hint}</em>
              </button>
            </li>
          ))}
        </ol>
      </header>

      {error ? (
        <FeedbackBanner tone="error" title="Could not continue">
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-deal-table tb-rfq-flow__table" aria-label="Parties at the table">
        <DealMiniSeat name={buyerName} role="Buyer" you />
        <div className="tb-deal-cloth" aria-hidden>
          <span>At the table</span>
        </div>
        <DealMiniSeat
          name={seated[0]?.name || "Supplier"}
          role={selectedSuppliers.length > 1 ? `${selectedSuppliers.length} seats` : "Supplier"}
        />
      </div>

      <div className="tb-deal-paper tb-rfq-flow__stage" data-dir={stepDir}>
        {step === 0 ? (
          <section key="basics" className="tb-rfq-flow__panel">
            <p className="tb-deal-kicker">Step 01</p>
            <h2>Name what sits on the table</h2>
            <p className="tb-rfq-flow__lead">
              A clear title helps the other side recognise the deal in their inbox.
            </p>
            <div className="tb-inv-form-stack">
              <label data-state={basicsLive.errors.title ? "error" : undefined}>
                Title
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  onBlur={() => basicsLive.touch("title")}
                  placeholder="Wireless accessories Q3"
                  autoFocus
                />
                <FieldError error={basicsLive.errors.title} />
              </label>
              <label>
                Notes
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  onBlur={() => basicsLive.touch("notes")}
                  rows={3}
                  placeholder="Optional notes for suppliers"
                />
                <FieldError error={basicsLive.errors.notes} />
              </label>
            </div>
            <div className="tb-rfq-flow__footer">
              <InventoryBtn
                tone="accent"
                onClick={() => {
                  if (!basicsLive.finish()) return;
                  goTo(1);
                }}
              >
                Next · goods →
              </InventoryBtn>
            </div>
          </section>
        ) : null}

        {step === 1 ? (
          <section key="products" className="tb-rfq-flow__panel">
            <p className="tb-deal-kicker">Step 02</p>
            <h2>Lay goods on the table</h2>
            <p className="tb-rfq-flow__lead">
              Tap marketplace products, then set quantity and your target price.
            </p>

            <label className="tb-inv-field">
              Search marketplace
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Product name or SKU…"
                className="tb-inv-inline-input mt-1"
                autoFocus
              />
            </label>

            {catalogLoading ? (
              <LoadingEntity entity="products" className="mt-3" />
            ) : catalog.length === 0 ? (
              <p className="tb-inv-muted mt-3">
                No products found. Try another search, or{" "}
                <InventoryLinkBtn href={ROUTES.inventoryProducts} tone="ghost">
                  browse the marketplace
                </InventoryLinkBtn>
                .
              </p>
            ) : (
              <ul className="tb-rfq-product-pick">
                {catalog.map((p) => {
                  const selected = selectedProductIds.has(p.id);
                  const img =
                    p.primary_image_url ||
                    p.images?.find((i) => i.is_primary)?.url ||
                    p.images?.[0]?.url;
                  return (
                    <li key={p.id}>
                      <button
                        type="button"
                        data-selected={selected}
                        className="tb-rfq-product-pick__card"
                        onClick={() => toggleProduct(p)}
                        aria-pressed={selected}
                      >
                        <span className="tb-rfq-product-pick__thumb" aria-hidden>
                          {img ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(img)} alt="" />
                          ) : (
                            <span>{p.name.slice(0, 2).toUpperCase()}</span>
                          )}
                        </span>
                        <span className="tb-rfq-product-pick__body">
                          <strong>{p.name}</strong>
                          <em>
                            {p.supplier_name ?? "Supplier"}
                            {p.sku ? ` · ${p.sku}` : ""}
                          </em>
                          <em>
                            MOQ {p.moq}
                            {p.prices?.[0]?.unit_price
                              ? ` · ${p.prices[0].currency} ${p.prices[0].unit_price}`
                              : ""}
                          </em>
                        </span>
                        <span className="tb-rfq-product-pick__badge">
                          {selected ? "On table" : "Add"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}

            <h3 className="tb-inv-subhead mt-6">On the table · {named.length}</h3>
            {named.length === 0 ? (
              <p className="tb-inv-muted">Nothing yet — tap products above.</p>
            ) : (
              <div className="tb-inv-line-grid">
                {named.map((it) => {
                  const errors = showLineErrors(it) ? lineErrors(it) : {};
                  return (
                    <div key={it.key} className="tb-inv-line">
                      <div className="tb-rfq-item">
                        <span className="tb-rfq-item__thumb" aria-hidden>
                          {it.primary_image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(it.primary_image_url)} alt="" />
                          ) : (
                            <span>{(it.product_name || "PR").slice(0, 2).toUpperCase()}</span>
                          )}
                        </span>
                        <div>
                          <p className="font-semibold text-foreground">{it.product_name}</p>
                          {it.sku ? <p className="tb-inv-muted text-xs">{it.sku}</p> : null}
                        </div>
                      </div>
                      <div>
                        <NumberInput
                          kind="integer"
                          value={it.quantity}
                          onChange={(e) => updateItem(it.key, { quantity: e.target.value })}
                          onBlur={() => setItemTouched((prev) => ({ ...prev, [it.key]: true }))}
                          placeholder="Qty"
                          className="tb-inv-inline-input"
                        />
                        <FieldError error={errors.quantity} />
                      </div>
                      <div>
                        <p className="tb-inv-muted mb-1 text-xs">
                          Listed {it.catalog_unit_price || "—"}
                        </p>
                        <NumberInput
                          kind="decimal"
                          value={it.target_unit_price ?? ""}
                          onChange={(e) =>
                            updateItem(it.key, { target_unit_price: e.target.value })
                          }
                          onBlur={() => setItemTouched((prev) => ({ ...prev, [it.key]: true }))}
                          placeholder="Your offer"
                          className="tb-inv-inline-input"
                        />
                        <FieldError error={errors.target_unit_price} />
                      </div>
                      <InventoryBtn
                        tone="ghost"
                        onClick={() => setItems((p) => p.filter((x) => x.key !== it.key))}
                      >
                        Remove
                      </InventoryBtn>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="tb-rfq-flow__footer">
              <BackLink onClick={() => goTo(0)}>Back</BackLink>
              <InventoryBtn tone="soft" busy={busy} disabled={busy} onClick={() => void saveDraft()}>
                Save draft
              </InventoryBtn>
              <InventoryBtn
                tone="accent"
                busy={busy}
                disabled={busy || named.length === 0}
                onClick={() => void goSuppliers()}
              >
                Next · seats →
              </InventoryBtn>
            </div>
          </section>
        ) : null}

        {step === 2 ? (
          <section key="suppliers" className="tb-rfq-flow__panel">
            <p className="tb-deal-kicker">Step 03</p>
            <h2>Who sits opposite</h2>
            <p className="tb-rfq-flow__lead">
              Choose which suppliers to invite.
            </p>
            {eligible.length === 0 ? (
              <p className="tb-inv-muted">
                No suppliers matched these products yet. Check that catalog lines have a supplier
                owner.
              </p>
            ) : (
              <ul className="tb-rfq-flow__seats">
                {eligible.map((s) => {
                  const inviteable = s.can_invite ?? s.verified;
                  const checked = selectedSuppliers.includes(s.supplier_business_id);
                  return (
                    <li key={s.supplier_business_id}>
                      <button
                        type="button"
                        className="tb-rfq-flow__seat"
                        data-on={checked || undefined}
                        data-blocked={!inviteable || undefined}
                        aria-pressed={checked}
                        disabled={!inviteable}
                        title={
                          inviteable
                            ? undefined
                            : `Cannot invite — verification is ${s.verification_status || "pending"}`
                        }
                        onClick={() => {
                          if (!inviteable) return;
                          setSelectedSuppliers((prev) =>
                            checked
                              ? prev.filter((id) => id !== s.supplier_business_id)
                              : [...prev, s.supplier_business_id],
                          );
                        }}
                      >
                        <span className="tb-rfq-flow__seat-mark" aria-hidden>
                          {(s.name || "S").slice(0, 1).toUpperCase()}
                        </span>
                        <span className="tb-rfq-flow__seat-copy">
                          <strong>{s.name || "Supplier"}</strong>
                          {!inviteable ? (
                            <em>
                              Not inviteable · {s.verification_status || "unverified"}
                            </em>
                          ) : null}
                          {s.products?.length ? (
                            <em>
                              {s.products
                                .map((p) => `${p.product_name || "Product"} × ${p.quantity || ""}`)
                                .join(" · ")}
                            </em>
                          ) : null}
                        </span>
                        <span className="tb-rfq-flow__seat-flag">
                          {!inviteable ? "Blocked" : checked ? "Seated" : "Seat"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {eligible.some((s) => !(s.can_invite ?? s.verified)) ? (
              <p className="tb-inv-muted mt-3">
                Only verified suppliers can be invited.
              </p>
            ) : null}
            <div className="tb-rfq-flow__footer">
              <BackLink onClick={() => goTo(1)}>Back</BackLink>
              <InventoryBtn tone="accent" busy={busy} disabled={busy} onClick={() => goTo(3)}>
                Next · handshake →
              </InventoryBtn>
            </div>
          </section>
        ) : null}

        {step === 3 ? (
          <section key="review" className="tb-rfq-flow__panel tb-rfq-flow__panel--handshake">
            <p className="tb-deal-kicker">Step 04</p>
            <h2>Ready for the handshake</h2>
            <p className="tb-rfq-flow__lead">
              Confirm the brief. Send puts it on their side of the table.
            </p>

            <article className="tb-rfq-flow__summary">
              <header className="tb-rfq-flow__summary-head">
                <div>
                  <em>Ask</em>
                  <strong>{title.trim() || "Untitled RFQ"}</strong>
                </div>
                <StatusBadge status="draft" />
              </header>
              {notes.trim() ? <p className="tb-rfq-flow__summary-notes">{notes}</p> : null}
              <div className="tb-rfq-flow__summary-grid">
                <div>
                  <dt>Goods</dt>
                  <dd>
                    <ul>
                      {named.map((i) => (
                        <li key={i.key}>
                          <span>{i.product_name}</span>
                          <em>
                            qty {i.quantity}
                            {i.target_unit_price ? ` · target ${i.target_unit_price}` : ""}
                          </em>
                        </li>
                      ))}
                    </ul>
                  </dd>
                </div>
                <div>
                  <dt>Opposite</dt>
                  <dd>
                    {selectedSuppliers.length
                      ? seated.map((s) => s.name || "Supplier").join(", ") ||
                        `${selectedSuppliers.length} selected`
                      : "None yet — you can still open the workspace"}
                  </dd>
                </div>
              </div>
            </article>

            <div className="tb-rfq-flow__footer">
              <BackLink onClick={() => goTo(2)}>Back</BackLink>
              <InventoryBtn
                tone="accent"
                busy={busy}
                disabled={busy || !rfqId || Boolean(handshakeTo)}
                onClick={() => void publishAndInvite()}
              >
                {selectedSuppliers.length ? "Send & handshake →" : "Open deal room →"}
              </InventoryBtn>
            </div>
            {rfqId ? (
              <p className="tb-rfq-flow__draft-note">Draft filed · ready to transmit</p>
            ) : null}
          </section>
        ) : null}
      </div>
    </div>
  );
}

function DealMiniSeat({
  name,
  role,
  you,
}: {
  name: string;
  role: string;
  you?: boolean;
}) {
  return (
    <div className="tb-deal-seat" data-you={you || undefined}>
      <span className="tb-deal-seat__mark" aria-hidden>
        {(name || "?").slice(0, 1).toUpperCase()}
      </span>
      <span className="tb-deal-seat__copy">
        <em>{you ? "You" : role}</em>
        <strong>{name}</strong>
      </span>
    </div>
  );
}
