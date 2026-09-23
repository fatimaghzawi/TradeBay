"use client";

import { StatusBadge } from "@/components/catalog/InventoryUi";
import { DealMoveWho } from "@/components/procurement/DealRoom";
import { DealHandshake } from "@/components/procurement/DealHandshake";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { NumberInput } from "@/components/ui/FormField";
import { BusyText } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import { negotiationApi, type Negotiation, type NegotiationOffer } from "@/lib/api/negotiationApi";
import { procurementApi, type Quotation, type RFQItem } from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { dealMoney } from "@/lib/procurement/dealRoom";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { bumpLive } from "@/lib/live/bus";

type Props = {
  rfqId: string;
  quotation: Quotation;
  items: RFQItem[];
  currency: string;
  buyerBusinessId?: string | null;
  buyerName?: string;
  supplierName?: string;
  buyerLogoUrl?: string | null;
  supplierLogoUrl?: string | null;
  onChanged?: () => void;
  /** Fired after OK — always open Handshake (orderId set when buyer prepared a draft PO). */
  onDealLocked?: (orderId?: string) => void;
};

function offerHeadline(offer: NegotiationOffer, currency: string) {
  const first = offer.items[0];
  if (!first) return dealMoney(currency, offer.total_price);
  const more = offer.items.length > 1 ? ` +${offer.items.length - 1}` : "";
  return `${first.quantity} × ${dealMoney(currency, first.unit_price)}${more}`;
}

function isLiveNegotiation(status?: string | null) {
  return status === "OPEN" || status === "IN_PROGRESS";
}

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

/** Opening quotation is the supplier's number; counters are owned by whoever proposed them. */
function isCounterpartMove(
  offer: NegotiationOffer | null,
  index: number,
  opts: {
    myBusinessId?: string | null;
    supplierId?: string | null;
    buyerId?: string | null;
    isBuyer: boolean;
  },
): boolean {
  if (!offer) {
    // No counters yet — opening quote is from the supplier.
    return opts.isBuyer;
  }
  if (!opts.myBusinessId) return false;
  const side = offerSide(offer, index, opts.supplierId, opts.buyerId);
  if (side === "supplier") return opts.myBusinessId === opts.buyerId;
  return opts.myBusinessId === opts.supplierId;
}

export function RfqOfferPanel({
  rfqId,
  quotation,
  items,
  currency,
  buyerBusinessId,
  buyerName = "Buyer",
  supplierName = "Supplier",
  buyerLogoUrl,
  supplierLogoUrl,
  onChanged,
  onDealLocked,
}: Props) {
  const { hasPermission, business } = useAuth();
  const router = useRouter();
  const isBuyer = business?.type === "buyer";
  const isSupplier = business?.type === "supplier";
  const [negotiation, setNegotiation] = useState<Negotiation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, { quantity: string; unit_price: string }>>({});
  const [handshake, setHandshake] = useState<{
    mode: "ok" | "order";
    orderId?: string;
    amount?: string;
  } | null>(null);

  const canManage = hasPermission("negotiations.manage") || hasPermission("negotiations.create");

  const finishHandshake = useCallback(() => {
    if (!handshake) return;
    const next = handshake;
    setHandshake(null);
    if (next.mode === "order") {
      // Orders are out of this release — celebrate the deal, then show Coming Soon.
      router.push(ROUTES.orders);
      return;
    }
    if (next.mode === "ok") {
      onDealLocked?.(next.orderId);
      return;
    }
    onChanged?.();
  }, [handshake, onChanged, onDealLocked, router]);

  async function loadExisting() {
    try {
      const rows = await negotiationApi.listForRfq(rfqId);
      const forQuote = rows.filter((row) => row.quotation_id === quotation.id);
      const match =
        forQuote.find((row) => isLiveNegotiation(row.status)) ?? forQuote[0] ?? null;
      setNegotiation(match);
      setError(null);
      const source = match?.offers.at(-1)?.items?.length
        ? match.offers.at(-1)!.items
        : match?.baseline_lines ??
          quotation.lines?.map((line) => ({
            rfq_item_id: line.rfq_item_id,
            product_name_snapshot: line.product_name_snapshot,
            quantity: line.quantity,
            unit_price: line.unit_price,
            line_total: line.line_total,
          })) ??
          [];
      const next: Record<string, { quantity: string; unit_price: string }> = {};
      for (const line of source) {
        if (!line.rfq_item_id) continue;
        next[line.rfq_item_id] = { quantity: line.quantity, unit_price: line.unit_price };
      }
      setDrafts(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this negotiation");
    }
  }

  useEffect(() => {
    void loadExisting();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rfqId, quotation.id]);

  useLivePoll(
    async () => {
      if (busy || handshake) return;
      await loadExisting();
    },
    { intervalMs: 3500, enabled: Boolean(rfqId && quotation.id), paused: busy || Boolean(handshake) },
  );

  const current = useMemo(() => {
    if (negotiation?.offers.length) return negotiation.offers[negotiation.offers.length - 1] ?? null;
    return null;
  }, [negotiation]);

  async function run(action: () => Promise<void>, opts?: { holdRefresh?: boolean }) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (!opts?.holdRefresh) onChanged?.();
      bumpLive({ source: "rfq-offer", referenceType: "rfq", referenceId: rfqId });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That step didn't complete. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const tableClosed = ["AGREED", "REJECTED", "CANCELLED", "EXPIRED"].includes(
    negotiation?.status || "",
  );
  const quoteClosed = ["accepted", "withdrawn", "expired", "rejected"].includes(quotation.status);
  const quoteLive = ["submitted", "negotiating"].includes(quotation.status);
  const numberLocked =
    tableClosed ||
    quoteClosed ||
    current?.status.toLowerCase() === "accepted";
  const latestIdx = (negotiation?.offers.length ?? 0) - 1;
  const latestIsCounterpart = isCounterpartMove(current, Math.max(latestIdx, 0), {
    myBusinessId: business?.id,
    supplierId: quotation.supplier_id,
    buyerId: buyerBusinessId,
    isBuyer,
  });
  const canBargain = !numberLocked && canManage && latestIsCounterpart;
  const canOk =
    !numberLocked &&
    canManage &&
    hasPermission("negotiations.manage") &&
    latestIsCounterpart;
  const canOrder =
    isBuyer &&
    hasPermission("quotations.accept") &&
    (numberLocked || (latestIsCounterpart && (quoteClosed || quoteLive)));
  const canEnd =
    !numberLocked &&
    quoteLive &&
    latestIsCounterpart &&
    ((isBuyer && hasPermission("quotations.accept")) ||
      (isSupplier && hasPermission("quotations.update")));

  if (quoteClosed && !negotiation) {
    return null;
  }

  async function liveOrOpen() {
    if (negotiation && isLiveNegotiation(negotiation.status)) return negotiation;
    return negotiationApi.open(rfqId, quotation.id);
  }

  function offerIsActionable(offer?: NegotiationOffer | null) {
    if (!offer) return quoteLive && !numberLocked && isBuyer;
    return offer.status.toLowerCase() === "proposed";
  }

  async function lockOffer(offer: NegotiationOffer) {
    if (offer.status.toLowerCase() === "accepted") return;
    if (!negotiation) throw new Error("Open the table before locking a number");
    const next = await negotiationApi.acceptOffer(negotiation.id, offer.id);
    setNegotiation(next);
  }

  async function okNumber(offer: NegotiationOffer | null) {
    if (offer && offer.status.toLowerCase() !== "accepted") {
      await lockOffer(offer);
    }
    const amount = offer
      ? offerHeadline(offer, currency)
      : dealMoney(currency, quotation.total);
    if (isBuyer && hasPermission("quotations.accept")) {
      const order = await procurementApi.handshake(rfqId, quotation.id);
      setHandshake({ mode: "ok", orderId: order.id, amount });
      return;
    }
    // Supplier OK — lock the number and send them to Handshake to wait on the draft PO.
    setHandshake({ mode: "ok", amount });
  }

  async function orderNumber(offer: NegotiationOffer | null) {
    if (offer && offer.status.toLowerCase() === "proposed") {
      await lockOffer(offer);
    }
    const order = await procurementApi.award(rfqId, quotation.id);
    setHandshake({
      mode: "order",
      orderId: order.id,
      amount: offer ? offerHeadline(offer, currency) : dealMoney(currency, quotation.total),
    });
  }

  async function endQuotation() {
    if (isSupplier) await procurementApi.withdrawQuotation(quotation.id);
    else await procurementApi.rejectQuotation(quotation.id);
    setConfirmKey(null);
  }

  /** Actions only on the counterpart's latest live number — never on your own counter.
   *  After the number is locked, the buyer may still Order regardless of who last proposed. */
  function tableActions(offer: NegotiationOffer | null, rowKey: string, offerIndex = 0) {
    const counterpart = isCounterpartMove(offer, offerIndex, {
      myBusinessId: business?.id,
      supplierId: quotation.supplier_id,
      buyerId: buyerBusinessId,
      isBuyer,
    });
    if (!numberLocked && !counterpart) return null;

    if (numberLocked) {
      if (!canOrder) return null;
      const confirmOrder = confirmKey === `order:${rowKey}`;
      if (confirmOrder) {
        return (
          <div className="tb-inv-form-actions">
            <p className="tb-inv-muted">Create the purchase order at this number?</p>
            <button
              type="button"
              className="tb-inv-btn tb-inv-btn-accent"
              disabled={busy}
              onClick={() => void run(() => orderNumber(offer ?? current), { holdRefresh: true })}
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
          </div>
        );
      }
      return (
        <div className="tb-inv-form-actions">
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-accent"
            disabled={busy}
            onClick={() => setConfirmKey(`order:${rowKey}`)}
          >
            Order · make the PO
          </button>
        </div>
      );
    }

    if (!offerIsActionable(offer) || (!canOk && !canOrder && !canEnd)) return null;
    const confirmOrder = confirmKey === `order:${rowKey}`;
    const confirmEnd = confirmKey === `end:${rowKey}`;
    if (confirmOrder) {
      return (
        <div className="tb-inv-form-actions">
          <p className="tb-inv-muted">Create the purchase order at this number?</p>
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-accent"
            disabled={busy}
            onClick={() => void run(() => orderNumber(offer), { holdRefresh: true })}
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
        </div>
      );
    }
    if (confirmEnd) {
      return (
        <div className="tb-inv-form-actions">
          <p className="tb-inv-muted">This ends the whole quotation.</p>
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-soft"
            disabled={busy}
            onClick={() => void run(endQuotation)}
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
        </div>
      );
    }
    return (
      <div className="tb-inv-form-actions">
        {canOk && (!offer || offer.status.toLowerCase() === "proposed") ? (
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-accent"
            disabled={busy}
            onClick={() => void run(() => okNumber(offer), { holdRefresh: true })}
          >
            <BusyText busy={busy}>OK</BusyText>
          </button>
        ) : null}
        {canOrder ? (
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-accent"
            disabled={busy}
            onClick={() => setConfirmKey(`order:${rowKey}`)}
          >
            Order
          </button>
        ) : null}
        {canEnd ? (
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-soft"
            disabled={busy}
            onClick={() => setConfirmKey(`end:${rowKey}`)}
          >
            End quotation
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="tb-deal-bargain" data-locked={numberLocked || undefined}>
      {handshake ? (
        <DealHandshake
          buyerName={buyerName}
          supplierName={supplierName}
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

      <div className="tb-deal-bargain__head">
        <div>
          <p className="tb-deal-kicker">Across the table</p>
          <h4>{numberLocked ? "Number locked" : "The exchange"}</h4>
          <p className="tb-inv-muted">
            {numberLocked
              ? isBuyer
                ? "Both sides agreed. Review the draft on Handshake, then issue the purchase order."
                : "Both sides agreed. Waiting on the buyer to issue the purchase order."
              : latestIsCounterpart
                ? isBuyer
                  ? "OK accepts their number and prepares a draft PO. Order issues it. Or slide a counter."
                  : "OK accepts their counter and closes the table — or slide your own number back."
                : "Waiting for the other company to respond."}
          </p>
        </div>
        <div
          className="tb-deal-live"
          data-locked={numberLocked || undefined}
          data-waiting={!numberLocked && !latestIsCounterpart ? true : undefined}
        >
          <span className="tb-deal-live__pulse" aria-hidden />
          <em>{numberLocked ? "Agreed" : latestIsCounterpart ? "Your move" : "Their move"}</em>
          <strong>
            {current
              ? offerHeadline(current, currency)
              : dealMoney(currency, quotation.total)}
          </strong>
        </div>
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Negotiation">
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-deal-thread" data-locked={numberLocked || undefined}>
        <div className="tb-deal-thread__rail" aria-hidden />
        <ol className="tb-deal-moves">
          <li
            className="tb-deal-move"
            data-side="supplier"
            data-latest={!negotiation?.offers.length || undefined}
            data-opening="true"
            style={{ ["--move-i" as string]: 0 }}
          >
            <DealMoveWho
              side="supplier"
              name={supplierName}
              you={isSupplier}
              logoUrl={supplierLogoUrl}
            />
            <div className="tb-deal-bubble">
              <header>
                <span className="tb-deal-bubble__tag">Opening counter</span>
                <strong>{dealMoney(currency, quotation.total)}</strong>
              </header>
              <ul>
                {(quotation.lines?.length
                  ? quotation.lines
                  : items.map((item) => ({
                      rfq_item_id: item.id,
                      product_name_snapshot: item.product_name,
                      quantity: item.quantity,
                      unit_price: item.catalog_unit_price || item.target_unit_price || "0",
                      line_total: null as string | null,
                    }))
                ).map((line, lineIdx) => (
                  <li key={`opening-${line.rfq_item_id || lineIdx}`}>
                    <span>{line.product_name_snapshot || "Item"}</span>
                    <em>
                      {line.quantity} × {dealMoney(currency, line.unit_price)}
                      {"line_total" in line && line.line_total
                        ? ` = ${dealMoney(currency, line.line_total)}`
                        : ""}
                    </em>
                  </li>
                ))}
              </ul>
              <footer>
                <StatusBadge
                  status={
                    numberLocked && !negotiation?.offers.length
                      ? "accepted"
                      : quotation.status === "negotiating"
                        ? "negotiating"
                        : "submitted"
                  }
                />
              </footer>
              {!negotiation?.offers.length ? tableActions(null, "opening", 0) : null}
            </div>
          </li>

          {negotiation?.offers.map((offer, idx) => {
            const side = offerSide(offer, idx, quotation.supplier_id, buyerBusinessId);
            const actor = side === "supplier" ? supplierName : buyerName;
            const you = Boolean(
              business?.id &&
                ((side === "supplier" && quotation.supplier_id === business.id) ||
                  (side === "buyer" && buyerBusinessId === business.id)),
            );
            const isLatest = idx === latestIdx;
            return (
              <li
                key={offer.id}
                className="tb-deal-move"
                data-side={side}
                data-latest={isLatest || undefined}
                style={{ ["--move-i" as string]: idx + 1 }}
              >
                <DealMoveWho
                  side={side}
                  name={actor}
                  you={you}
                  logoUrl={side === "supplier" ? supplierLogoUrl : buyerLogoUrl}
                />
                <div className="tb-deal-bubble">
                  <header>
                    <span className="tb-deal-bubble__tag">Counter {idx + 1}</span>
                    <strong>{offerHeadline(offer, currency)}</strong>
                  </header>
                  <ul>
                    {offer.items.map((line) => (
                      <li key={`${offer.id}-${line.rfq_item_id}`}>
                        <span>{line.product_name_snapshot || "Item"}</span>
                        <em>
                          {line.quantity} × {dealMoney(currency, line.unit_price)}
                          {line.line_total ? ` = ${dealMoney(currency, line.line_total)}` : ""}
                        </em>
                      </li>
                    ))}
                  </ul>
                  <footer>
                    <StatusBadge status={offer.status} />
                    {offer.total_price ? (
                      <span className="tb-deal-bubble__total">
                        {dealMoney(currency, offer.total_price)}
                      </span>
                    ) : null}
                  </footer>
                  {isLatest ? tableActions(offer, offer.id, idx) : null}
                </div>
              </li>
            );
          })}
        </ol>

        {!numberLocked && !latestIsCounterpart ? (
          <p className="tb-deal-waiting" aria-live="polite">
            <span className="tb-deal-waiting__dots" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            Waiting for {isBuyer ? supplierName : buyerName} to move…
          </p>
        ) : null}
      </div>

      {canBargain ? (
        <div className="tb-deal-next">
          <div className="tb-deal-next__head">
            <strong>Your next move</strong>
            <p className="tb-inv-muted">
              Send a counter with updated quantities or unit prices.
            </p>
          </div>
          {(items.length ? items : quotation.lines || []).map((item) => {
            const rfqItemId =
              "id" in item && item.id
                ? item.id
                : "rfq_item_id" in item
                  ? item.rfq_item_id
                  : null;
            const name =
              "product_name" in item && item.product_name
                ? item.product_name
                : "product_name_snapshot" in item
                  ? item.product_name_snapshot
                  : "Item";
            if (!rfqItemId) return null;
            const draft = drafts[rfqItemId] ?? { quantity: "", unit_price: "" };
            return (
              <label key={rfqItemId}>
                {name}
                <span className="tb-inv-muted">Qty × unit price</span>
                <div className="flex gap-2">
                  <NumberInput
                    kind="integer"
                    value={draft.quantity}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [rfqItemId]: { ...draft, quantity: e.target.value },
                      }))
                    }
                  />
                  <NumberInput
                    kind="decimal"
                    value={draft.unit_price}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [rfqItemId]: { ...draft, unit_price: e.target.value },
                      }))
                    }
                  />
                </div>
              </label>
            );
          })}
          <button
            type="button"
            className="tb-inv-btn tb-inv-btn-accent tb-deal-next__send"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const open = await liveOrOpen();
                const lines = Object.entries(drafts)
                  .filter(([, line]) => line.quantity && line.unit_price)
                  .map(([rfq_item_id, line]) => ({
                    rfq_item_id,
                    quantity: line.quantity,
                    unit_price: line.unit_price,
                    product_name: items.find((i) => i.id === rfq_item_id)?.product_name,
                  }));
                if (!lines.length) {
                  throw new Error("Enter quantity and unit price for at least one line");
                }
                const next = await negotiationApi.proposeOffer(open.id, {
                  parent_offer_id: open.offers.at(-1)?.id,
                  lines,
                });
                setNegotiation(next);
              })
            }
          >
            <BusyText busy={busy}>
              {negotiation ? "Slide this counter across" : "Open with this counter"}
            </BusyText>
          </button>
        </div>
      ) : null}
    </div>
  );
}
