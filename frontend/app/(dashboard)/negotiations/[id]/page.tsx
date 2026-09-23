"use client";

import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventoryPageHeader,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { DealMoveWho } from "@/components/procurement/DealRoom";
import { DealHandshake } from "@/components/procurement/DealHandshake";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import { negotiationApi, type NegotiationOffer } from "@/lib/api/negotiationApi";
import { procurementApi } from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { dealMoney } from "@/lib/procurement/dealRoom";
import { issuesToFieldMap } from "@/lib/validation/common";
import { offerLineSchema } from "@/lib/validation/forms";
import { useAuth } from "@/providers/AuthProvider";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";
import { bumpLive } from "@/lib/live/bus";
import { useLivePoll } from "@/lib/live/useLivePoll";

function offerSide(
  offer: NegotiationOffer,
  index: number,
  supplierId?: string | null,
  buyerId?: string | null,
): "buyer" | "supplier" {
  const actor = offer.created_by_business_id;
  if (actor && supplierId && actor === supplierId) return "supplier";
  if (actor && buyerId && actor === buyerId) return "buyer";
  return index % 2 === 0 ? "supplier" : "buyer";
}

export default function NegotiationDetailPage() {
  const params = useParams<{ id: string }>();
  const negotiationId = params.id;
  const router = useRouter();
  const { hasPermission, business } = useAuth();
  const isBuyer = business?.type === "buyer";
  const isSupplier = business?.type === "supplier";
  const [neg, setNeg] = useState<Awaited<ReturnType<typeof negotiationApi.get>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [paymentTerms, setPaymentTerms] = useState("Net 30");
  const [lines, setLines] = useState<
    { rfq_item_id: string; product_name?: string; quantity: string; unit_price: string }[]
  >([]);
  const [lineErrors, setLineErrors] = useState<
    Record<string, { quantity?: string; unit_price?: string }>
  >({});
  const [handshake, setHandshake] = useState<{
    mode: "ok" | "order";
    orderId?: string;
    rfqId?: string;
    amount?: string;
  } | null>(null);

  const reload = useCallback(async () => {
    if (!hasPermission("negotiations.read")) return;
    try {
      const data = await negotiationApi.get(negotiationId);
      setNeg(data);
      setError(null);
      const latest = data.offers[data.offers.length - 1];
      const sourceItems = latest?.items?.length ? latest.items : (data.baseline_lines ?? []);
      if (sourceItems.length) {
        setLines(
          sourceItems
            .filter((i) => i.rfq_item_id)
            .map((i) => ({
              rfq_item_id: i.rfq_item_id as string,
              product_name: i.product_name_snapshot ?? undefined,
              quantity: i.quantity,
              unit_price: i.unit_price,
            })),
        );
      }
      if (latest?.payment_terms) setPaymentTerms(latest.payment_terms);
      else if (data.payment_terms) setPaymentTerms(data.payment_terms);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this negotiation");
    }
  }, [hasPermission, negotiationId]);

  const finishHandshake = useCallback(() => {
    if (!handshake) return;
    const next = handshake;
    setHandshake(null);
    if (next.mode === "order") {
      router.push(ROUTES.orders);
      return;
    }
    if (next.mode === "ok" && next.rfqId) {
      router.push(`${ROUTES.procurementRfq(next.rfqId)}?tab=handshake`);
      return;
    }
    void reload();
  }, [handshake, reload, router]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useLivePoll(
    async () => {
      if (busy || handshake) return;
      try {
        const data = await negotiationApi.get(negotiationId);
        setNeg(data);
        setError(null);
      } catch {
        /* keep last good negotiation on screen */
      }
    },
    {
      intervalMs: 3500,
      enabled: Boolean(negotiationId) && hasPermission("negotiations.read"),
      paused: busy || Boolean(handshake),
    },
  );

  async function run(action: () => Promise<void>, opts?: { holdRefresh?: boolean }) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (!opts?.holdRefresh) await reload();
      bumpLive({
        source: "negotiation",
        referenceType: "negotiation",
        referenceId: negotiationId,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That step didn't complete. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!hasPermission("negotiations.read")) {
    return (
      <div className="tb-inv-page">
        <InventoryPageHeader
          title="Negotiation"
          description="You don't have access to this negotiation."
        />
      </div>
    );
  }

  const openOffers = (neg?.offers ?? []).filter((o) => o.status.toUpperCase() === "PROPOSED");
  const tableClosed = ["AGREED", "REJECTED", "CANCELLED", "EXPIRED"].includes(neg?.status || "");
  const latestOffer = neg?.offers?.length ? neg.offers[neg.offers.length - 1] : null;
  const numberLocked =
    tableClosed || latestOffer?.status.toUpperCase() === "ACCEPTED";
  const latestIdx = (neg?.offers.length ?? 0) - 1;
  const latestSide = latestOffer
    ? offerSide(
        latestOffer,
        latestIdx,
        neg?.supplier_business_id,
        neg?.buyer_business_id,
      )
    : null;
  // No counters yet → Opening counter is the supplier quotation; only the buyer can act.
  const latestIsCounterpart = latestOffer
    ? Boolean(
        business?.id &&
          ((latestSide === "supplier" && business.id === neg?.buyer_business_id) ||
            (latestSide === "buyer" && business.id === neg?.supplier_business_id)),
      )
    : Boolean(isBuyer);
  const canManage = hasPermission("negotiations.manage");
  const canPropose =
    canManage &&
    neg &&
    ["OPEN", "IN_PROGRESS"].includes(neg.status) &&
    lines.length > 0 &&
    !numberLocked &&
    latestIsCounterpart;
  const canOk =
    canManage &&
    latestIsCounterpart &&
    ["OPEN", "IN_PROGRESS"].includes(neg?.status || "") &&
    !numberLocked &&
    (latestOffer ? latestOffer.status.toUpperCase() === "PROPOSED" : Boolean(neg?.quotation_id));
  const canOrder =
    isBuyer &&
    hasPermission("quotations.accept") &&
    Boolean(neg?.rfq_id && neg?.quotation_id) &&
    (numberLocked || latestIsCounterpart);
  const canEnd =
    !numberLocked &&
    latestIsCounterpart &&
    Boolean(neg?.quotation_id) &&
    ((isBuyer && hasPermission("quotations.accept")) ||
      (isSupplier && hasPermission("quotations.update")));

  return (
    <div className="tb-inv-page tb-deal">
      {handshake ? (
        <DealHandshake
          buyerName={neg?.buyer_name || "Buyer"}
          supplierName={neg?.supplier_name || "Supplier"}
          headline={handshake.mode === "order" ? "Deal closed" : "Number locked"}
          detail={
            handshake.mode === "order"
              ? `${handshake.amount || "Agreed"} · opening the purchase order…`
              : `${handshake.amount || "Agreed"} · preparing the agreement…`
          }
          onDone={finishHandshake}
          durationMs={handshake.mode === "order" ? 2800 : 2200}
        />
      ) : null}
      <InventoryPageHeader
        eyebrow="At the table"
        title="Offer history"
        description={
          numberLocked
            ? "Agreed. The buyer can prepare the purchase order."
            : "Review the latest offer from the other company, then accept, counter, or close."
        }
        meta={neg ? <StatusBadge status={neg.status} /> : null}
        actions={
          <div className="flex flex-wrap gap-2">
            {neg?.rfq_id ? (
              <InventoryLinkBtn href={ROUTES.procurementRfq(neg.rfq_id)} tone="soft">
                ← Back to the deal
              </InventoryLinkBtn>
            ) : (
              <InventoryLinkBtn href={ROUTES.procurement} tone="soft">
                ← Procurement
              </InventoryLinkBtn>
            )}
          </div>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}

      {!neg ? (
        <LoadingEntity entity="negotiation" />
      ) : (
        <>
          <section className="tb-deal-paper">
            <p className="tb-deal-kicker">The exchange</p>
            <h2>Who moved last</h2>
            <div className="tb-deal-thread">
              <div className="tb-deal-thread__rail" aria-hidden />
            <ol className="tb-deal-moves">
              {neg.baseline_lines?.length ? (
                <li
                  className="tb-deal-move"
                  data-side="supplier"
                  data-latest={!neg.offers.length || undefined}
                  data-opening="true"
                >
                  <DealMoveWho
                    side="supplier"
                    name={neg.supplier_name || "Supplier"}
                    you={isSupplier}
                    logoUrl={neg.supplier_logo_url}
                  />
                  <header>
                    <strong>
                      Opening counter ·{" "}
                      {dealMoney(
                        neg.offers[0]?.currency || "USD",
                        neg.baseline_lines
                          .reduce((sum, line) => {
                            const lineTotal = Number(line.line_total);
                            if (Number.isFinite(lineTotal) && lineTotal > 0) return sum + lineTotal;
                            return sum + Number(line.quantity) * Number(line.unit_price);
                          }, 0)
                          .toFixed(2),
                      )}
                    </strong>
                  </header>
                  <ul>
                    {neg.baseline_lines.map((item, itemIdx) => (
                      <li key={`opening-${item.rfq_item_id || itemIdx}`}>
                        {item.product_name_snapshot || "Product"} — {item.quantity} ×{" "}
                        {dealMoney(neg.offers[0]?.currency || "USD", item.unit_price)}
                      </li>
                    ))}
                  </ul>
                  <StatusBadge
                    status={numberLocked && !neg.offers.length ? "accepted" : "submitted"}
                  />
                  {!neg.offers.length &&
                  (numberLocked ? canOrder : canOk || canOrder || canEnd) ? (
                    <div className="tb-inv-form-actions">
                      {confirmKey === "order:opening" ? (
                        <>
                          <p className="tb-inv-muted">Create the purchase order at this number?</p>
                          <button
                            type="button"
                            className="tb-inv-btn tb-inv-btn-accent"
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                const order = await procurementApi.award(
                                  neg.rfq_id as string,
                                  neg.quotation_id as string,
                                );
                                setHandshake({
                                  mode: "order",
                                  orderId: order.id,
                                  amount: dealMoney(
                                    neg.offers[0]?.currency || "USD",
                                    neg.baseline_lines
                                      ?.reduce((sum, line) => {
                                        const lineTotal = Number(line.line_total);
                                        if (Number.isFinite(lineTotal) && lineTotal > 0)
                                          return sum + lineTotal;
                                        return (
                                          sum + Number(line.quantity) * Number(line.unit_price)
                                        );
                                      }, 0)
                                      .toFixed(2),
                                  ),
                                });
                              }, { holdRefresh: true })
                            }
                          >
                            <BusyText busy={busy}>Order</BusyText>
                          </button>
                          <button
                            type="button"
                            className="tb-inv-btn tb-inv-btn-soft"
                            onClick={() => setConfirmKey(null)}
                          >
                            Not yet
                          </button>
                        </>
                      ) : confirmKey === "end:opening" ? (
                        <>
                          <p className="tb-inv-muted">This ends the whole quotation.</p>
                          <button
                            type="button"
                            className="tb-inv-btn tb-inv-btn-soft"
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                if (isSupplier) {
                                  await procurementApi.withdrawQuotation(
                                    neg.quotation_id as string,
                                  );
                                } else {
                                  await procurementApi.rejectQuotation(
                                    neg.quotation_id as string,
                                  );
                                }
                                router.push(
                                  neg.rfq_id
                                    ? ROUTES.procurementRfq(neg.rfq_id)
                                    : ROUTES.procurement,
                                );
                              })
                            }
                          >
                            <BusyText busy={busy}>End quotation</BusyText>
                          </button>
                          <button
                            type="button"
                            className="tb-inv-btn tb-inv-btn-accent"
                            onClick={() => setConfirmKey(null)}
                          >
                            Keep bargaining
                          </button>
                        </>
                      ) : (
                        <>
                          {canOrder ? (
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              disabled={busy}
                              onClick={() => setConfirmKey("order:opening")}
                            >
                              {numberLocked ? "Order · make the PO" : "Order"}
                            </button>
                          ) : null}
                          {!numberLocked && canOk ? (
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  if (isBuyer && neg.rfq_id && neg.quotation_id) {
                                    await procurementApi.handshake(neg.rfq_id, neg.quotation_id);
                                  }
                                  setHandshake({
                                    mode: "ok",
                                    rfqId: neg.rfq_id || undefined,
                                    amount: dealMoney(
                                      neg.offers[0]?.currency || "USD",
                                      neg.baseline_lines
                                        ?.reduce((sum, line) => {
                                          const lineTotal = Number(line.line_total);
                                          if (Number.isFinite(lineTotal) && lineTotal > 0)
                                            return sum + lineTotal;
                                          return (
                                            sum + Number(line.quantity) * Number(line.unit_price)
                                          );
                                        }, 0)
                                        .toFixed(2),
                                    ),
                                  });
                                }, { holdRefresh: true })
                              }
                            >
                              <BusyText busy={busy}>OK</BusyText>
                            </button>
                          ) : null}
                          {!numberLocked && canEnd ? (
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-soft"
                              disabled={busy}
                              onClick={() => setConfirmKey("end:opening")}
                            >
                              End quotation
                            </button>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : null}
                </li>
              ) : null}

              {neg.offers.map((o: NegotiationOffer, idx) => {
                const side = offerSide(
                  o,
                  idx,
                  neg.supplier_business_id,
                  neg.buyer_business_id,
                );
                const actor =
                  side === "supplier"
                    ? neg.supplier_name || "Supplier"
                    : neg.buyer_name || "Buyer";
                const you = Boolean(
                  business?.id &&
                    ((side === "supplier" && neg.supplier_business_id === business.id) ||
                      (side === "buyer" && neg.buyer_business_id === business.id)),
                );
                return (
                  <li
                    key={o.id}
                    className="tb-deal-move"
                    data-side={side}
                    data-latest={idx === latestIdx || undefined}
                  >
                    <DealMoveWho
                      side={side}
                      name={actor}
                      you={you}
                      logoUrl={
                        side === "supplier" ? neg.supplier_logo_url : neg.buyer_logo_url
                      }
                    />
                    <header>
                      <strong>
                        Counter {idx + 1} · {dealMoney(o.currency, o.total_price)}
                      </strong>
                    </header>
                    <ul>
                      {o.items.map((item, itemIdx) => (
                        <li key={`${o.id}-${itemIdx}`}>
                          {item.product_name_snapshot || "Product"} — {item.quantity} ×{" "}
                          {dealMoney(o.currency, item.unit_price)}
                        </li>
                      ))}
                    </ul>
                    <StatusBadge status={o.status} />
                    {idx === latestIdx &&
                    (numberLocked
                      ? canOrder
                      : o.status.toUpperCase() === "PROPOSED" &&
                        latestIsCounterpart &&
                        (canOk || canOrder || canEnd)) ? (
                      <div className="tb-inv-form-actions">
                        {confirmKey === `order:${o.id}` ? (
                          <>
                            <p className="tb-inv-muted">Create the purchase order at this number?</p>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  if (o.status.toUpperCase() === "PROPOSED") {
                                    await negotiationApi.acceptOffer(negotiationId, o.id);
                                  }
                                  const order = await procurementApi.award(
                                    neg.rfq_id as string,
                                    neg.quotation_id as string,
                                  );
                                  setHandshake({
                                    mode: "order",
                                    orderId: order.id,
                                    amount: dealMoney(o.currency, o.total_price),
                                  });
                                }, { holdRefresh: true })
                              }
                            >
                              <BusyText busy={busy}>Order</BusyText>
                            </button>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-soft"
                              onClick={() => setConfirmKey(null)}
                            >
                              Not yet
                            </button>
                          </>
                        ) : confirmKey === `end:${o.id}` ? (
                          <>
                            <p className="tb-inv-muted">This ends the whole quotation.</p>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-soft"
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  if (isSupplier) {
                                    await procurementApi.withdrawQuotation(
                                      neg.quotation_id as string,
                                    );
                                  } else {
                                    await procurementApi.rejectQuotation(
                                      neg.quotation_id as string,
                                    );
                                  }
                                  router.push(
                                    neg.rfq_id
                                      ? ROUTES.procurementRfq(neg.rfq_id)
                                      : ROUTES.procurement,
                                  );
                                })
                              }
                            >
                              <BusyText busy={busy}>End quotation</BusyText>
                            </button>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              onClick={() => setConfirmKey(null)}
                            >
                              Keep bargaining
                            </button>
                          </>
                        ) : (
                          <>
                            {canOrder ? (
                              <button
                                type="button"
                                className="tb-inv-btn tb-inv-btn-accent"
                                disabled={busy}
                                onClick={() => setConfirmKey(`order:${o.id}`)}
                              >
                                {numberLocked ? "Order · make the PO" : "Order"}
                              </button>
                            ) : null}
                            {!numberLocked && canOk && o.status.toUpperCase() === "PROPOSED" ? (
                              <button
                                type="button"
                                className="tb-inv-btn tb-inv-btn-accent"
                                disabled={busy}
                                onClick={() =>
                                  void run(async () => {
                                    await negotiationApi.acceptOffer(negotiationId, o.id);
                                    if (isBuyer && neg.rfq_id && neg.quotation_id) {
                                      await procurementApi.handshake(
                                        neg.rfq_id,
                                        neg.quotation_id,
                                      );
                                      setHandshake({
                                        mode: "ok",
                                        rfqId: neg.rfq_id,
                                        amount: dealMoney(o.currency, o.total_price),
                                      });
                                      return;
                                    }
                                    setHandshake({
                                      mode: "ok",
                                      rfqId: neg.rfq_id || undefined,
                                      amount: dealMoney(o.currency, o.total_price),
                                    });
                                  }, { holdRefresh: true })
                                }
                              >
                                <BusyText busy={busy}>OK</BusyText>
                              </button>
                            ) : null}
                            {!numberLocked && canEnd ? (
                              <button
                                type="button"
                                className="tb-inv-btn tb-inv-btn-soft"
                                disabled={busy}
                                onClick={() => setConfirmKey(`end:${o.id}`)}
                              >
                                End quotation
                              </button>
                            ) : null}
                          </>
                        )}
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ol>
            {!neg.baseline_lines?.length && neg.offers.length === 0 ? (
              <InventoryEmpty
                title="No Opening counter yet"
                body="Open the table from the deal room once the supplier quotation is in."
              />
            ) : null}
            </div>
          </section>

          {canPropose ? (
            <section className="tb-deal-next">
              <p className="tb-deal-kicker">Your next move</p>
              <strong>Slide a counter across</strong>
              <div className="tb-inv-form-grid">
                <label>
                  Payment terms
                  <input
                    value={paymentTerms}
                    onChange={(e) => setPaymentTerms(e.target.value)}
                    disabled={busy}
                  />
                </label>
              </div>
              <div className="tb-deal-lines">
                {lines.map((line, idx) => (
                  <div key={line.rfq_item_id} className="tb-deal-line">
                    <div className="tb-deal-line__item">
                      <strong>{line.product_name || "Product"}</strong>
                    </div>
                    <div className="tb-deal-line__figures">
                      <label>
                        Qty
                        <NumberInput
                          kind="integer"
                          value={line.quantity}
                          onChange={(e) =>
                            setLines((prev) =>
                              prev.map((l, i) =>
                                i === idx ? { ...l, quantity: e.target.value } : l,
                              ),
                            )
                          }
                          onBlur={() => {
                            const parsed = offerLineSchema.safeParse({
                              quantity: line.quantity,
                              unit_price: line.unit_price,
                            });
                            setLineErrors((prev) => ({
                              ...prev,
                              [line.rfq_item_id]: parsed.success
                                ? {}
                                : issuesToFieldMap(parsed.error.issues),
                            }));
                          }}
                          disabled={busy}
                        />
                        <FieldError error={lineErrors[line.rfq_item_id]?.quantity} />
                      </label>
                      <label>
                        Unit price
                        <NumberInput
                          kind="decimal"
                          value={line.unit_price}
                          onChange={(e) =>
                            setLines((prev) =>
                              prev.map((l, i) =>
                                i === idx ? { ...l, unit_price: e.target.value } : l,
                              ),
                            )
                          }
                          onBlur={() => {
                            const parsed = offerLineSchema.safeParse({
                              quantity: line.quantity,
                              unit_price: line.unit_price,
                            });
                            setLineErrors((prev) => ({
                              ...prev,
                              [line.rfq_item_id]: parsed.success
                                ? {}
                                : issuesToFieldMap(parsed.error.issues),
                            }));
                          }}
                          disabled={busy}
                        />
                        <FieldError error={lineErrors[line.rfq_item_id]?.unit_price} />
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
                disabled={busy || openOffers.length > 20}
                onClick={() => {
                  const next: Record<string, { quantity?: string; unit_price?: string }> = {};
                  for (const line of lines) {
                    const parsed = offerLineSchema.safeParse({
                      quantity: line.quantity,
                      unit_price: line.unit_price,
                    });
                    if (!parsed.success) {
                      next[line.rfq_item_id] = issuesToFieldMap(parsed.error.issues);
                    }
                  }
                  setLineErrors(next);
                  if (Object.keys(next).length) return;
                  void run(async () => {
                    await negotiationApi.proposeOffer(negotiationId, {
                      payment_terms: paymentTerms,
                      lines: lines.map((l) => ({
                        rfq_item_id: l.rfq_item_id,
                        quantity: l.quantity,
                        unit_price: l.unit_price,
                        product_name: l.product_name,
                      })),
                    });
                  });
                }}
              >
                <BusyText busy={busy}>Slide this counter across</BusyText>
              </button>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
