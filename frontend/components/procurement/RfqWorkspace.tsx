"use client";

import { StatusBadge } from "@/components/catalog/InventoryUi";
import { RfqThread } from "@/components/communication/RfqThread";
import { DealHero, DealSeat, ProductThumb } from "@/components/procurement/DealRoom";
import { RfqOfferPanel } from "@/components/procurement/RfqOfferPanel";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import {
  procurementApi,
  type PurchaseOrder,
  type QuotationLineInput,
  type RFQDetail,
  type SendRfqResult,
} from "@/lib/api/procurementApi";
import { negotiationApi } from "@/lib/api/negotiationApi";
import { ROUTES } from "@/lib/constants";
import { dealMoney, priceDelta } from "@/lib/procurement/dealRoom";
import {
  ORDER_STATUS_LABEL,
  stageLabel,
  unmatchedRequestsFromItems,
} from "@/lib/procurement/rfqLifecycle";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";
import { useLivePoll } from "@/lib/live/useLivePoll";
import { bumpLive } from "@/lib/live/bus";

type Props = { rfqId: string };
type Tab = "brief" | "table" | "talk" | "handshake";

function quoteDraftTotal(lines: QuotationLineInput[]) {
  return lines.reduce((sum, line) => {
    const qty = Number(line.quantity);
    const price = Number(line.unit_price);
    if (!Number.isFinite(qty) || !Number.isFinite(price)) return sum;
    return sum + qty * price;
  }, 0);
}

export function RfqWorkspace({ rfqId }: Props) {
  const { business, hasPermission } = useAuth();
  const isSupplier = business?.type === "supplier";
  const isBuyer = business?.type === "buyer";
  const isPlatform = business?.type === "platform";
  const router = useRouter();
  const search = useSearchParams();
  const sentCount = Number(search.get("sent") || 0);
  const [rfq, setRfq] = useState<RFQDetail | null>(null);
  const [tab, setTab] = useState<Tab>("brief");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [quoteLines, setQuoteLines] = useState<QuotationLineInput[]>([]);
  const [paymentTerms, setPaymentTerms] = useState("Net 30");
  const [deliveryTerms, setDeliveryTerms] = useState("");
  const [issuePaymentMethod, setIssuePaymentMethod] = useState("Bank transfer");
  const [issuePaymentTerms, setIssuePaymentTerms] = useState("Net 30");
  const [issueDeliveryTerms, setIssueDeliveryTerms] = useState("");
  const [draftTargets, setDraftTargets] = useState<Record<string, string>>({});
  const [requiredBy, setRequiredBy] = useState("");
  const [chatSupplierId, setChatSupplierId] = useState<string | null>(null);
  const [confirmAwardId, setConfirmAwardId] = useState<string | null>(null);
  const [draftOrder, setDraftOrder] = useState<PurchaseOrder | null>(null);
  const [openedHandshake, setOpenedHandshake] = useState(false);
  const [dealAgreed, setDealAgreed] = useState(false);

  async function load() {
    try {
      const data = await procurementApi.getRfq(rfqId);
      setRfq(data);
      setError(null);
      if (data.required_by) setRequiredBy(data.required_by.slice(0, 10));
      const soleInvite = data.invites.length === 1 ? data.invites[0] : undefined;
      if (soleInvite?.supplier_business_id) {
        setChatSupplierId(soleInvite.supplier_business_id);
      }
      if (data.order_id) {
        try {
          const order = await procurementApi.getOrder(data.order_id);
          setDraftOrder(order);
          setIssuePaymentMethod(order.payment_method || "Bank transfer");
          setIssuePaymentTerms(order.payment_terms || "Net 30");
          setIssueDeliveryTerms(order.delivery_terms || "");
        } catch {
          setDraftOrder(null);
        }
      } else {
        setDraftOrder(null);
      }
      if (
        !["awarded", "cancelled", "expired"].includes(data.status) &&
        (data.invites?.length ?? 0) === 0
      ) {
        const targets: Record<string, string> = {};
        for (const item of data.items) {
          targets[item.id] = item.target_unit_price ?? "";
        }
        setDraftTargets(targets);
      }
      if (isSupplier) {
        const mine = data.quotations.find((q) => q.supplier_id === business?.id);
        if (mine) {
          if (mine.payment_terms) setPaymentTerms(mine.payment_terms);
          if (mine.delivery_terms) setDeliveryTerms(mine.delivery_terms);
          if (mine.lines?.length) {
            setQuoteLines(
              mine.lines.map((line) => ({
                rfq_item_id: line.rfq_item_id || "",
                quantity: line.quantity,
                unit_price: line.unit_price,
                moq: line.moq ?? 1,
                lead_time_days: line.lead_time_days ?? 7,
                discount: line.discount ?? "0",
                tax: line.tax ?? "0",
                shipping_allocation: line.shipping_allocation ?? "0",
                notes: line.notes ?? undefined,
              })),
            );
          }
        } else if (data.items.length && quoteLines.length === 0) {
          setQuoteLines(
            data.items.map((item) => ({
              rfq_item_id: item.id,
              quantity: item.quantity,
              unit_price: item.catalog_unit_price || item.target_unit_price || "0",
              moq: 1,
              lead_time_days: 7,
              discount: "0",
              tax: "0",
              shipping_allocation: "0",
            })),
          );
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this RFQ");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rfqId, business?.id]);

  // Quiet live refresh — updates RFQ/quotation status without wiping in-progress edits.
  useLivePoll(
    async () => {
      if (busy) return;
      try {
        const data = await procurementApi.getRfq(rfqId);
        setRfq(data);
        if (data.order_id) {
          try {
            const order = await procurementApi.getOrder(data.order_id);
            setDraftOrder(order);
          } catch {
            /* keep prior draft order snapshot */
          }
        }
        const rows = await negotiationApi.listForRfq(rfqId);
        if (rows.some((row) => row.status === "AGREED")) {
          setDealAgreed(true);
        }
      } catch {
        /* keep last good RFQ on screen */
      }
    },
    { intervalMs: 4000, enabled: Boolean(rfqId), paused: busy },
  );

  useEffect(() => {
    const requested = search.get("tab");
    if (requested === "handshake") {
      setDealAgreed(true);
      setOpenedHandshake(true);
      setTab("handshake");
    } else if (requested === "table" || requested === "talk" || requested === "brief") {
      setTab(requested);
    }
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await negotiationApi.listForRfq(rfqId);
        if (cancelled) return;
        if (rows.some((row) => row.status === "AGREED")) {
          setDealAgreed(true);
        }
      } catch {
        /* Handshake still opens from draft / accepted quote */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rfqId]);

  useEffect(() => {
    if (!openedHandshake && draftOrder?.status === "draft") {
      setTab("handshake");
      setOpenedHandshake(true);
    }
  }, [draftOrder?.status, draftOrder?.id, openedHandshake]);

  const myInvite = useMemo(() => {
    if (!rfq || !business?.id) return null;
    return rfq.invites.find((i) => i.supplier_business_id === business.id) ?? null;
  }, [rfq, business?.id]);

  const unsent = Boolean(
    rfq &&
      !["awarded", "cancelled", "expired"].includes(rfq.status) &&
      (rfq.invites?.length ?? 0) === 0,
  );
  const canEditDraft = Boolean(isBuyer && unsent && hasPermission("rfqs.update"));
  const canSendDraft = Boolean(isBuyer && unsent && hasPermission("rfqs.update"));
  const canQuote = Boolean(
    isSupplier &&
      rfq &&
      hasPermission("quotations.create") &&
      myInvite &&
      ["invited", "viewed", "accepted"].includes(myInvite.status) &&
      !["awarded", "cancelled", "expired", "draft"].includes(rfq.status),
  );
  const myQuotation = useMemo(() => {
    if (!rfq || !business?.id) return null;
    return rfq.quotations.find((q) => q.supplier_id === business.id) ?? null;
  }, [rfq, business?.id]);
  const quoteLocked = Boolean(myQuotation && myQuotation.status !== "draft");
  const canOpenTable = Boolean(!unsent || canQuote || (rfq?.quotations.length ?? 0) > 0);
  const canTalk = Boolean(!unsent && !isPlatform);
  const canHandshake = Boolean(
    rfq?.order_id ||
      rfq?.status === "awarded" ||
      draftOrder ||
      dealAgreed ||
      rfq?.quotations.some((q) => q.status === "accepted"),
  );
  const awardedQuote = useMemo(() => {
    if (!rfq) return null;
    if (rfq.awarded_quotation_id) {
      return rfq.quotations.find((q) => q.id === rfq.awarded_quotation_id) ?? null;
    }
    return rfq.quotations.find((q) => q.status === "accepted") ?? null;
  }, [rfq]);
  const buyerName = rfq?.buyer_name?.trim() || "Buyer";
  const buyerProfileHref = rfq?.buyer_business_id
    ? isPlatform
      ? ROUTES.admin.businessDetail(rfq.buyer_business_id)
      : ROUTES.companyProfile(rfq.buyer_business_id)
    : null;
  const supplierName =
    rfq?.invites.find((i) => i.supplier_business_id)?.supplier_name ||
    rfq?.supplier_name ||
    (isSupplier ? business?.name : null) ||
    "Supplier";
  const supplierLogoUrl =
    (isSupplier ? business?.logo_url : null) ||
    rfq?.supplier_logo_url ||
    rfq?.invites.find((i) => i.supplier_business_id)?.supplier_logo_url ||
    null;
  const chatPeer = useMemo(() => {
    if (!rfq) return null;
    if (isSupplier && rfq.buyer_business_id) {
      return {
        id: rfq.buyer_business_id,
        name: buyerName,
        logoUrl: rfq.buyer_logo_url || null,
      };
    }
    if (!isBuyer) return null;
    const invited = rfq.invites.filter((i) => i.supplier_business_id);
    const sid =
      chatSupplierId ||
      invited[0]?.supplier_business_id ||
      rfq.supplier_business_id ||
      null;
    if (!sid) return null;
    const invite = invited.find((i) => i.supplier_business_id === sid);
    const name = invite?.supplier_name || rfq.supplier_name || "Supplier";
    return {
      id: sid,
      name,
      logoUrl:
        invite?.supplier_logo_url ||
        (sid === rfq.supplier_business_id ? rfq.supplier_logo_url : null) ||
        null,
    };
  }, [rfq, isSupplier, isBuyer, chatSupplierId, buyerName]);

  const negotiating = Boolean(
    rfq?.status === "negotiating" ||
      rfq?.quotations.some((q) => q.status === "negotiating"),
  );
  const liveQuoteTotal = quoteDraftTotal(quoteLines);

  async function draftItemPayload(items = rfq?.items ?? []) {
    return items.map((item) => ({
      product_id: item.product_id,
      category_id: item.category_id,
      product_name: item.product_name,
      sku: item.sku,
      quantity: item.quantity,
      unit: item.unit,
      catalog_unit_price: item.catalog_unit_price,
      target_unit_price: (draftTargets[item.id] ?? item.target_unit_price ?? "").trim() || null,
      requirements: item.requirements,
      notes: item.notes,
      supplier_business_id: item.supplier_business_id,
    }));
  }

  async function saveDraftPrices() {
    if (!rfq || !unsent) return;
    await procurementApi.updateRfq(rfqId, {
      items: await draftItemPayload(),
      required_by: requiredBy ? new Date(`${requiredBy}T12:00:00`).toISOString() : null,
    });
  }

  async function removeDraftItem(itemId: string) {
    if (!rfq || !unsent) return;
    const remaining = rfq.items.filter((item) => item.id !== itemId);
    if (remaining.length === 0) {
      throw new Error("Keep at least one product, or cancel this request.");
    }
    await procurementApi.updateRfq(rfqId, { items: await draftItemPayload(remaining) });
  }

  async function applySendResult(result: SendRfqResult) {
    const sent = result.sent ?? [];
    const nextId = result.rfq?.id || rfqId;
    const message =
      sent.length > 1
        ? `Your request is on ${sent.length} supplier desks.`
        : sent.length === 1
          ? "Your request is on the supplier’s desk."
          : "Your request has been sent.";
    if (nextId !== rfqId) {
      router.replace(`${ROUTES.procurementRfq(nextId)}?sent=${Math.max(sent.length, 1)}`);
      return false;
    }
    if (result.rfq?.status === "cancelled" && sent[0]?.id) {
      router.replace(`${ROUTES.procurementRfq(sent[0].id)}?sent=${sent.length}`);
      return false;
    }
    return message;
  }

  async function recoverIfAlreadySent(latest?: RFQDetail | null) {
    const current = latest ?? (await procurementApi.getRfq(rfqId).catch(() => null));
    if (!current || (current.status !== "cancelled" && (current.invites?.length ?? 0) === 0)) {
      return null;
    }
    if (current.status === "cancelled") {
      return "This draft was split into one RFQ per supplier. Open Active RFQs to track them.";
    }
    setRfq(current);
    return "Request sent to suppliers";
  }

  async function sendDraftToSuppliers() {
    const already = await recoverIfAlreadySent();
    if (already !== null) return already;
    try {
      await saveDraftPrices();
    } catch (err) {
      const recovered = await recoverIfAlreadySent();
      if (recovered !== null) return recovered;
      throw err;
    }
    try {
      return await applySendResult(await procurementApi.sendRfq(rfqId));
    } catch (err) {
      const recovered = await recoverIfAlreadySent();
      if (recovered !== null) return recovered;
      throw err;
    }
  }

  async function run(action: () => Promise<string | false | void>, fallback?: string) {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const result = await action();
      if (result === false) return;
      if (typeof result === "string") setInfo(result);
      else if (fallback) setInfo(fallback);
      await load();
      bumpLive({ source: "rfq-workspace", referenceType: "rfq", referenceId: rfqId });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That step didn't complete. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!rfq && !error) return <LoadingEntity entity="RFQ" />;
  if (!rfq) {
    return (
      <FeedbackBanner tone="error" title="Couldn't open this deal">
        {error}
      </FeedbackBanner>
    );
  }

  const counterpartName = isSupplier ? buyerName : supplierName;
  const leftSeat = (
    <DealSeat
      name={isSupplier ? buyerName : business?.name || "Your company"}
      role="Buyer"
      you={isBuyer}
      logoUrl={isSupplier ? rfq.buyer_logo_url : business?.logo_url}
      href={isSupplier ? buyerProfileHref : null}
    />
  );
  const rightSeat = (
    <DealSeat
      name={isSupplier ? business?.name || "Your company" : supplierName}
      role="Supplier"
      you={isSupplier}
      logoUrl={
        isSupplier
          ? business?.logo_url
          : rfq.supplier_logo_url ||
            rfq.invites.find((i) => i.supplier_business_id === rfq.supplier_business_id)
              ?.supplier_logo_url ||
            rfq.invites[0]?.supplier_logo_url ||
            null
      }
      href={
        !isSupplier && rfq.supplier_business_id
          ? ROUTES.companyProfile(rfq.supplier_business_id)
          : rfq.invites[0]?.supplier_business_id
            ? ROUTES.companyProfile(rfq.invites[0].supplier_business_id)
            : null
      }
    />
  );

  return (
    <div className="tb-inv-page tb-deal">
      <DealHero
        number={rfq.rfq_number}
        title={rfq.title}
        status={rfq.status}
        hasQuote={rfq.quotations.length > 0}
        negotiating={negotiating}
        left={leftSeat}
        right={rightSeat}
        actions={
          <>
            {canSendDraft ? (
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
                disabled={busy}
                onClick={() => void run(sendDraftToSuppliers)}
              >
                <BusyText busy={busy}>{busy ? "Sending…" : "Put this on their desk"}</BusyText>
              </button>
            ) : null}
            {isPlatform && rfq.buyer_business_id ? (
              <Link
                href={ROUTES.admin.businessDetail(rfq.buyer_business_id)}
                className="tb-inv-btn tb-inv-btn-soft"
              >
                Buyer profile
              </Link>
            ) : null}
          </>
        }
      />

      {isPlatform ? (
        <FeedbackBanner tone="info" title="Read-only">
          Quoting and awarding stay with the trading companies.
        </FeedbackBanner>
      ) : null}
      {sentCount > 0 || (info && info.toLowerCase().includes("desk")) ? (
        <FeedbackBanner tone="success" title="On the supplier’s desk">
          {info ||
            `Sent to ${sentCount} supplier${sentCount === 1 ? "" : "s"}. The table opens when they quote.`}
        </FeedbackBanner>
      ) : null}
      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}
      {info && !info.toLowerCase().includes("desk") && !info.startsWith("Your RFQ has been sent") ? (
        <FeedbackBanner tone="success" title="Updated">
          {info}
        </FeedbackBanner>
      ) : null}

      {canOpenTable || canTalk || canHandshake ? (
        <nav className="tb-deal-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            className="tb-deal-tab"
            data-active={tab === "brief"}
            onClick={() => setTab("brief")}
          >
            The brief
          </button>
          {canOpenTable ? (
            <button
              type="button"
              role="tab"
              className="tb-deal-tab"
              data-active={tab === "table"}
              onClick={() => setTab("table")}
            >
              {isSupplier && !quoteLocked ? "Your offer" : "The table"}
            </button>
          ) : null}
          {canTalk ? (
            <button
              type="button"
              role="tab"
              className="tb-deal-tab"
              data-active={tab === "talk"}
              onClick={() => setTab("talk")}
            >
              Talk it through
            </button>
          ) : null}
          {canHandshake ? (
            <button
              type="button"
              role="tab"
              className="tb-deal-tab"
              data-active={tab === "handshake"}
              onClick={() => setTab("handshake")}
            >
              Handshake
            </button>
          ) : null}
        </nav>
      ) : null}

      {tab === "brief" ? (
        <div className="tb-inv-split">
          <article className="tb-deal-paper">
            <p className="tb-deal-kicker">Commercial brief</p>
            <h2>{isSupplier ? `${buyerName} is asking` : "What you are asking for"}</h2>
            <p className="tb-inv-muted">
              {rfq.description || "No extra notes — the lines below are the request."}
            </p>
            <dl className="tb-deal-meta">
              <div>
                <dt>Needed by</dt>
                <dd>
                  {canEditDraft ? (
                    <input
                      type="date"
                      value={requiredBy}
                      onChange={(e) => setRequiredBy(e.target.value)}
                      className="tb-inv-inline-input"
                    />
                  ) : rfq.required_by ? (
                    new Date(rfq.required_by).toLocaleDateString()
                  ) : (
                    "Flexible"
                  )}
                </dd>
              </div>
              <div>
                <dt>Ship to</dt>
                <dd>
                  {[rfq.destination?.city, rfq.destination?.governorate, rfq.destination?.country]
                    .filter(Boolean)
                    .join(", ") || "—"}
                </dd>
              </div>
              <div>
                <dt>Currency</dt>
                <dd>{rfq.currency}</dd>
              </div>
            </dl>
            <div className="tb-deal-lines">
              {rfq.items.map((item) => (
                <div key={item.id} className="tb-deal-line">
                  <div className="tb-rfq-item">
                    <ProductThumb name={item.product_name} imageUrl={item.primary_image_url} />
                    <div>
                      <strong>{item.product_name}</strong>
                      <div className="tb-inv-muted">
                        {item.quantity} {item.unit}
                        {item.sku ? ` · ${item.sku}` : ""}
                        {item.supplier_name ? ` · ${item.supplier_name}` : ""}
                      </div>
                    </div>
                  </div>
                  <div className="tb-deal-line__figures">
                    <div className="tb-deal-price" data-tone="list">
                      <em>List</em>
                      <strong>{dealMoney(rfq.currency, item.catalog_unit_price)}</strong>
                    </div>
                    <div className="tb-deal-price" data-tone="ask">
                      <em>Buyer wants</em>
                      <strong>
                        {canEditDraft ? (
                          <NumberInput
                            kind="decimal"
                            className="w-28 max-w-full rounded-lg border border-[var(--tb-line)] bg-white px-2 py-1.5 text-sm font-semibold"
                            value={draftTargets[item.id] ?? ""}
                            disabled={busy}
                            aria-label={`Target price for ${item.product_name}`}
                            onChange={(e) =>
                              setDraftTargets((prev) => ({
                                ...prev,
                                [item.id]: e.target.value,
                              }))
                            }
                          />
                        ) : (
                          dealMoney(rfq.currency, item.target_unit_price)
                        )}
                      </strong>
                    </div>
                    {canEditDraft && rfq.items.length > 1 ? (
                      <button
                        type="button"
                        className="text-sm font-semibold text-[var(--tb-danger)] disabled:opacity-50"
                        disabled={busy}
                        onClick={() =>
                          void run(() => removeDraftItem(item.id), "Product removed")
                        }
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
            {canEditDraft ? (
              <div className="tb-inv-form-actions mt-4">
                <button
                  type="button"
                  className="tb-inv-btn tb-inv-btn-soft"
                  disabled={busy}
                  onClick={() => void run(saveDraftPrices, "Brief saved")}
                >
                  <BusyText busy={busy}>Save brief</BusyText>
                </button>
                {canSendDraft ? (
                  <button
                    type="button"
                    className="tb-inv-btn tb-inv-btn-accent"
                    disabled={busy}
                    onClick={() => void run(sendDraftToSuppliers)}
                  >
                    <BusyText busy={busy}>Send to the table</BusyText>
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>

          <aside className="tb-deal-sheet">
            <p className="tb-deal-kicker">{isSupplier ? "Your move" : unsent ? "Who sits opposite" : "Across the table"}</p>
            <h2>{isSupplier ? "Respond" : "Suppliers"}</h2>
            {isSupplier ? (
              <div className="tb-inv-stack">
                <p>
                  {buyerName} sent this request. Read the brief, talk if you need to, then put a
                  quotation on the table. Once submitted, the numbers lock.
                </p>
                {canQuote && !quoteLocked ? (
                  <button type="button" className="tb-inv-btn tb-inv-btn-accent" onClick={() => setTab("table")}>
                    Write your quotation
                  </button>
                ) : null}
                {quoteLocked ? (
                  <button type="button" className="tb-inv-btn tb-inv-btn-soft" onClick={() => setTab("table")}>
                    Open the table
                  </button>
                ) : null}
                {rfq.order_id ? (
                  <Link href={ROUTES.orders} className="tb-inv-btn tb-inv-btn-soft">
                    Orders coming soon →
                  </Link>
                ) : null}
                {myInvite &&
                !quoteLocked &&
                ["invited", "viewed", "accepted"].includes(myInvite.status) ? (
                  <button
                    type="button"
                    className="tb-inv-btn tb-inv-btn-soft"
                    disabled={busy}
                    onClick={() =>
                      void run(
                        () =>
                          procurementApi.declineInvite(rfqId, "Unable to fulfil").then(() => undefined),
                        "Invitation declined",
                      )
                    }
                  >
                    <BusyText busy={busy}>Pass on this request</BusyText>
                  </button>
                ) : null}
              </div>
            ) : (
              <ul className="tb-deal-seats">
                {(rfq.supplier_requests?.length
                  ? rfq.supplier_requests
                  : unmatchedRequestsFromItems(rfq.items)
                ).map((req) => (
                  <li key={req.supplier_business_id || req.supplier_name}>
                    <DealSeat
                      name={req.supplier_name || "Supplier"}
                      role={stageLabel(req.stage)}
                      href={
                        req.supplier_business_id
                          ? ROUTES.companyProfile(req.supplier_business_id)
                          : null
                      }
                    />
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      ) : null}

      {tab === "table" && canOpenTable ? (
        <div className="tb-inv-split">
          {isSupplier && canQuote ? (
            <section className="tb-deal-paper tb-deal-quote" data-locked={quoteLocked || undefined}>
              <div className="tb-deal-quotehead">
                <div>
                  <p className="tb-deal-kicker">{quoteLocked ? "On the table" : "Your quotation"}</p>
                  <h2>{quoteLocked ? myQuotation?.quotation_number : "Prepare the offer"}</h2>
                  <p className="tb-inv-muted">
                    {quoteLocked
                      ? "Submitted. Bargain from here — do not rewrite the original sheet."
                      : `Addressed to ${buyerName}. List price is frozen; their ask is the target.`}
                  </p>
                </div>
                <div className="tb-deal-total">
                  {dealMoney(rfq.currency, String(liveQuoteTotal || myQuotation?.total || "0"))}
                </div>
              </div>
              <fieldset disabled={quoteLocked} className="contents">
                <div className="tb-inv-form-grid">
                  <label>
                    Payment terms
                    <input
                      value={paymentTerms}
                      disabled={quoteLocked}
                      onChange={(e) => setPaymentTerms(e.target.value)}
                    />
                  </label>
                  <label>
                    Delivery terms
                    <input
                      value={deliveryTerms}
                      disabled={quoteLocked}
                      onChange={(e) => setDeliveryTerms(e.target.value)}
                    />
                  </label>
                </div>
                <div className="tb-deal-lines mt-4">
                  {quoteLines.map((line, idx) => {
                    const item = rfq.items.find((i) => i.id === line.rfq_item_id);
                    const gap = priceDelta(line.unit_price, item?.target_unit_price);
                    return (
                      <div key={line.rfq_item_id} className="tb-deal-line">
                        <div className="tb-rfq-item">
                          <ProductThumb
                            name={item?.product_name || "Product"}
                            imageUrl={item?.primary_image_url}
                          />
                          <div>
                            <strong>{item?.product_name}</strong>
                            <div className="tb-inv-muted">
                              {item?.quantity} {item?.unit}
                            </div>
                            {gap && !gap.even ? (
                              <span className="tb-deal-gap" data-tone={gap.under ? "under" : "over"}>
                                {gap.under ? "Under their ask" : "Above their ask"}{" "}
                                {Math.abs(gap.pct).toFixed(1)}%
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="tb-deal-line__figures">
                          <div className="tb-deal-price" data-tone="list">
                            <em>List</em>
                            <strong>{dealMoney(rfq.currency, item?.catalog_unit_price)}</strong>
                          </div>
                          <div className="tb-deal-price" data-tone="ask">
                            <em>They want</em>
                            <strong>{dealMoney(rfq.currency, item?.target_unit_price)}</strong>
                          </div>
                          <div className="tb-deal-price" data-tone="bid">
                            <em>You offer</em>
                            <NumberInput
                              kind="decimal"
                              value={line.unit_price}
                              disabled={quoteLocked}
                              onChange={(e) =>
                                setQuoteLines((prev) =>
                                  prev.map((l, i) =>
                                    i === idx ? { ...l, unit_price: e.target.value } : l,
                                  ),
                                )
                              }
                              aria-label={`Your unit price for ${item?.product_name || "item"}`}
                            />
                            <NumberInput
                              kind="integer"
                              value={line.quantity}
                              disabled={quoteLocked}
                              onChange={(e) =>
                                setQuoteLines((prev) =>
                                  prev.map((l, i) =>
                                    i === idx ? { ...l, quantity: e.target.value } : l,
                                  ),
                                )
                              }
                              placeholder="Qty"
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </fieldset>
              <div className="tb-inv-form-actions">
                {quoteLocked ? null : (
                  <button
                    type="button"
                    className="tb-inv-btn tb-inv-btn-soft"
                    disabled={busy}
                    onClick={() =>
                      void run(
                        () =>
                          procurementApi
                            .upsertQuotation(
                              rfqId,
                              {
                                payment_terms: paymentTerms,
                                delivery_terms: deliveryTerms,
                                lines: quoteLines,
                              },
                              false,
                            )
                            .then(() => undefined),
                        "Draft saved",
                      )
                    }
                  >
                    <BusyText busy={busy}>Keep as draft</BusyText>
                  </button>
                )}
                <button
                  type="button"
                  className="tb-inv-btn tb-inv-btn-accent"
                  disabled={busy || quoteLocked}
                  onClick={() => {
                    if (quoteLocked) return;
                    void run(
                      () =>
                        procurementApi
                          .upsertQuotation(
                            rfqId,
                            {
                              payment_terms: paymentTerms,
                              delivery_terms: deliveryTerms,
                              lines: quoteLines,
                            },
                            true,
                          )
                          .then(() => undefined),
                      "Quotation is on the table",
                    );
                  }}
                >
                  <BusyText busy={busy}>
                    {quoteLocked ? "Quotation submitted" : "Put it on the table"}
                  </BusyText>
                </button>
              </div>
            </section>
          ) : (
            <section className="tb-deal-sheet">
              <p className="tb-deal-kicker">Waiting</p>
              <h2>No quotation from you yet</h2>
              <p className="tb-inv-muted">Open the brief first, then write your offer.</p>
            </section>
          )}

          <section className="tb-deal-sheet">
            <p className="tb-deal-kicker">{isSupplier ? "The exchange" : "Offers on the table"}</p>
            <h2>{isSupplier ? "Bargain" : "Quotations"}</h2>
            {rfq.quotations.length === 0 ? (
              <p className="tb-inv-muted">
                {isSupplier
                  ? "Once you submit, the buyer can shake on it or counter."
                  : unsent
                    ? "Send the brief first."
                    : `Waiting on ${counterpartName}.`}
              </p>
            ) : (
              <ul className="tb-inv-entity-list">
                {rfq.quotations.map((q) => (
                  <li key={q.id} className="tb-rfq-quote-card">
                    <div className="tb-deal-quotehead">
                      <div>
                        <p className="tb-deal-kicker">Opening counter</p>
                        <strong>{q.quotation_number}</strong>
                        <div className="tb-inv-muted">
                          {q.supplier_name || "Supplier"}
                          {q.payment_terms ? ` · ${q.payment_terms}` : ""}
                        </div>
                      </div>
                      <div>
                        <div className="tb-deal-total">{dealMoney(q.currency, q.total)}</div>
                        <StatusBadge status={q.status} />
                      </div>
                    </div>
                    {q.lines?.length ? (
                      <div className="tb-deal-lines">
                        {q.lines.map((line) => {
                          const item = rfq.items.find((i) => i.id === line.rfq_item_id);
                          const gap = priceDelta(line.unit_price, item?.target_unit_price);
                          return (
                            <div key={line.id} className="tb-deal-line tb-deal-line--compare">
                              <div className="tb-deal-line__item">
                                <strong>{line.product_name_snapshot || item?.product_name}</strong>
                                <span className="tb-inv-muted">
                                  {line.quantity} {line.unit}
                                  {line.lead_time_days != null
                                    ? ` · ${line.lead_time_days}d lead`
                                    : ""}
                                </span>
                              </div>
                              <div className="tb-deal-line__figures">
                                <div className="tb-deal-price" data-tone="ask">
                                  <em>Ask</em>
                                  <strong>
                                    {dealMoney(rfq.currency, item?.target_unit_price)}
                                  </strong>
                                </div>
                                <div className="tb-deal-price" data-tone="bid">
                                  <em>Offer</em>
                                  <strong>{dealMoney(q.currency, line.unit_price)}</strong>
                                </div>
                                {gap && !gap.even ? (
                                  <span
                                    className="tb-deal-gap"
                                    data-tone={gap.under ? "under" : "over"}
                                  >
                                    {gap.under ? "Better than ask" : "Above ask"}
                                  </span>
                                ) : (
                                  <a
                                    className="tb-deal-line__pdf"
                                    href={procurementApi.quotationPdfUrl(q.id)}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    PDF
                                  </a>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                    {isBuyer &&
                    hasPermission("quotations.accept") &&
                    ["submitted", "negotiating"].includes(q.status) ? (
                      <div className="tb-inv-form-actions">
                        {confirmAwardId === q.id ? (
                          <>
                            <p className="tb-inv-muted">
                              Confirm the deal — prepares a draft purchase order from this quotation.
                            </p>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  await procurementApi.handshake(rfqId, q.id);
                                  setConfirmAwardId(null);
                                  setDealAgreed(true);
                                  setOpenedHandshake(true);
                                  setTab("handshake");
                                }, "Deal confirmed — draft PO ready")
                              }
                            >
                              <BusyText busy={busy}>Confirm deal — draft PO</BusyText>
                            </button>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-soft"
                              onClick={() => setConfirmAwardId(null)}
                            >
                              Not yet
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-accent"
                              disabled={busy}
                              onClick={() => setConfirmAwardId(q.id)}
                            >
                              Accept this offer
                            </button>
                            <button
                              type="button"
                              className="tb-inv-btn tb-inv-btn-soft"
                              disabled={busy}
                              onClick={() =>
                                void run(
                                  () => procurementApi.rejectQuotation(q.id).then(() => undefined),
                                  "Walked away from this quote",
                                )
                              }
                            >
                              <BusyText busy={busy}>Walk away</BusyText>
                            </button>
                          </>
                        )}
                      </div>
                    ) : null}
                    {q.status === "accepted" ||
                    (dealAgreed && ["submitted", "negotiating"].includes(q.status)) ? (
                      <button
                        type="button"
                        className="tb-inv-btn tb-inv-btn-accent"
                        onClick={() => {
                          setDealAgreed(true);
                          setOpenedHandshake(true);
                          setTab("handshake");
                        }}
                      >
                        Open handshake
                        {rfq.order_number ? ` · ${rfq.order_number}` : " · prepare PO"}
                      </button>
                    ) : null}
                    <RfqOfferPanel
                      rfqId={rfqId}
                      quotation={q}
                      items={rfq.items.filter(
                        (item) =>
                          !q.supplier_id ||
                          item.supplier_business_id === q.supplier_id ||
                          rfq.items.length === q.lines?.length,
                      )}
                      currency={q.currency}
                      buyerBusinessId={rfq.buyer_business_id}
                      buyerName={buyerName}
                      supplierName={q.supplier_name || supplierName}
                      buyerLogoUrl={rfq.buyer_logo_url}
                      supplierLogoUrl={
                        q.supplier_logo_url ||
                        (q.supplier_id === business?.id ? business?.logo_url : null) ||
                        rfq.invites.find((i) => i.supplier_business_id === q.supplier_id)
                          ?.supplier_logo_url ||
                        supplierLogoUrl
                      }
                      onChanged={() => void load()}
                      onDealLocked={() => {
                        setDealAgreed(true);
                        setOpenedHandshake(true);
                        void load().then(() => setTab("handshake"));
                      }}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : null}

      {tab === "handshake" && canHandshake ? (
        <section className="tb-deal-paper tb-deal-quote" data-locked={draftOrder?.status !== "draft" || undefined}>
          <div className="tb-deal-quotehead">
            <div>
              <p className="tb-deal-kicker">Handshake</p>
              <h2>
                {draftOrder?.status === "draft"
                  ? "Draft purchase order"
                  : draftOrder
                    ? `Purchase order ${draftOrder.order_number}`
                    : "Number locked"}
              </h2>
              <p className="tb-inv-muted">
                {draftOrder?.status === "draft"
                  ? isBuyer
                    ? "Review the agreed lines, then issue the PO to the supplier."
                    : "The buyer locked the number. Waiting for them to issue the purchase order."
                  : draftOrder
                    ? isBuyer
                      ? "The purchase order is live. Track fulfilment from the order page."
                      : "Acknowledge the purchase order when you are ready to fulfil."
                    : isBuyer
                      ? "Both sides agreed. Prepare the draft purchase order from the locked quotation."
                      : "Both sides agreed. Waiting for the buyer to prepare and issue the purchase order."}
              </p>
            </div>
            <div className="text-right">
              {draftOrder ? (
                <>
                  <div className="tb-deal-total">
                    {dealMoney(draftOrder.currency, draftOrder.total)}
                  </div>
                  <StatusBadge status={draftOrder.status} />
                </>
              ) : (
                <StatusBadge status="accepted" />
              )}
            </div>
          </div>

          {!draftOrder ? (
            <div className="tb-inv-stack">
              {(awardedQuote || rfq.quotations.find((q) => ["submitted", "negotiating", "accepted"].includes(q.status))) ? (
                <>
                  <dl className="tb-deal-meta">
                    <div>
                      <dt>Quotation</dt>
                      <dd>
                        {(awardedQuote || rfq.quotations[0])?.quotation_number || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Agreed total</dt>
                      <dd>
                        {dealMoney(
                          (awardedQuote || rfq.quotations[0])?.currency || rfq.currency,
                          (awardedQuote || rfq.quotations[0])?.total,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Supplier</dt>
                      <dd>
                        {(awardedQuote || rfq.quotations[0])?.supplier_name || supplierName}
                      </dd>
                    </div>
                  </dl>
                  {isBuyer && hasPermission("quotations.accept") ? (
                    <div className="tb-inv-form-actions">
                      <button
                        type="button"
                        className="tb-inv-btn tb-inv-btn-accent"
                        disabled={busy}
                        onClick={() => {
                          const quoteId =
                            awardedQuote?.id ||
                            rfq.awarded_quotation_id ||
                            rfq.quotations.find((q) =>
                              ["submitted", "negotiating", "accepted"].includes(q.status),
                            )?.id;
                          if (!quoteId) return;
                          void run(async () => {
                            const order = await procurementApi.handshake(rfqId, quoteId);
                            setDraftOrder(order);
                            setIssuePaymentMethod(order.payment_method || "Bank transfer");
                            setIssuePaymentTerms(order.payment_terms || "Net 30");
                            setIssueDeliveryTerms(order.delivery_terms || "");
                            setDealAgreed(true);
                          }, "Draft purchase order prepared");
                        }}
                      >
                        <BusyText busy={busy}>Prepare draft purchase order</BusyText>
                      </button>
                    </div>
                  ) : (
                    <p className="tb-inv-muted">
                      Sit tight — the buyer will prepare the draft PO on this Handshake tab.
                    </p>
                  )}
                </>
              ) : (
                <p className="tb-inv-muted">Loading the agreed number…</p>
              )}
            </div>
          ) : (
            <>
              <dl className="tb-deal-meta">
                <div>
                  <dt>PO number</dt>
                  <dd>{draftOrder.order_number}</dd>
                </div>
                <div>
                  <dt>Quotation</dt>
                  <dd>{draftOrder.quotation_number || awardedQuote?.quotation_number || "—"}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    {ORDER_STATUS_LABEL[draftOrder.status] || draftOrder.status}
                  </dd>
                </div>
                <div>
                  <dt>Supplier</dt>
                  <dd>{awardedQuote?.supplier_name || supplierName}</dd>
                </div>
              </dl>

              {isBuyer && draftOrder.status === "draft" ? (
                <div className="tb-inv-form-grid mt-4">
                  <label>
                    Payment method
                    <input
                      value={issuePaymentMethod}
                      onChange={(e) => setIssuePaymentMethod(e.target.value)}
                      placeholder="Bank transfer, cheque, cash on delivery…"
                    />
                  </label>
                  <label>
                    Payment terms
                    <input
                      value={issuePaymentTerms}
                      onChange={(e) => setIssuePaymentTerms(e.target.value)}
                      placeholder="Net 30"
                    />
                  </label>
                  <label>
                    Delivery terms
                    <input
                      value={issueDeliveryTerms}
                      onChange={(e) => setIssueDeliveryTerms(e.target.value)}
                      placeholder="Ex Works, DAP…"
                    />
                  </label>
                </div>
              ) : (
                <dl className="tb-deal-meta mt-4">
                  <div>
                    <dt>Payment method</dt>
                    <dd>{draftOrder.payment_method || "Awaiting buyer"}</dd>
                  </div>
                  <div>
                    <dt>Payment terms</dt>
                    <dd>{draftOrder.payment_terms || awardedQuote?.payment_terms || "—"}</dd>
                  </div>
                  <div>
                    <dt>Delivery terms</dt>
                    <dd>{draftOrder.delivery_terms || awardedQuote?.delivery_terms || "—"}</dd>
                  </div>
                </dl>
              )}

              <div className="tb-deal-lines">
                {draftOrder.items.map((item) => (
                  <div key={item.id} className="tb-deal-line tb-deal-line--compare">
                    <div className="tb-deal-line__item">
                      <strong>{item.product_name_snapshot}</strong>
                      <span className="tb-inv-muted">
                        {item.quantity} {item.unit}
                        {item.sku_snapshot ? ` · ${item.sku_snapshot}` : ""}
                      </span>
                    </div>
                    <div className="tb-deal-line__figures">
                      <div className="tb-deal-price" data-tone="bid">
                        <em>Unit</em>
                        <strong>{dealMoney(draftOrder.currency, item.unit_price)}</strong>
                      </div>
                      <div className="tb-deal-price" data-tone="list">
                        <em>Line</em>
                        <strong>{dealMoney(draftOrder.currency, item.line_total)}</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="tb-inv-form-actions">
                {isBuyer &&
                draftOrder.status === "draft" &&
                hasPermission("quotations.accept") ? (
                  <button
                    type="button"
                    className="tb-inv-btn tb-inv-btn-accent"
                    disabled={busy || !issuePaymentMethod.trim()}
                    onClick={() =>
                      void run(async () => {
                        const issued = await procurementApi.issueOrder(draftOrder.id, {
                          payment_method: issuePaymentMethod.trim(),
                          payment_terms: issuePaymentTerms.trim() || undefined,
                          delivery_terms: issueDeliveryTerms.trim() || undefined,
                        });
                        setDraftOrder(issued);
                        router.push(ROUTES.orders);
                        return false;
                      }, "Deal confirmed — orders are coming soon")
                    }
                  >
                    <BusyText busy={busy}>Confirm deal (orders soon)</BusyText>
                  </button>
                ) : null}
                {draftOrder.status !== "draft" ? (
                  <Link
                    href={ROUTES.orders}
                    className="tb-inv-btn tb-inv-btn-accent"
                  >
                    Orders coming soon →
                  </Link>
                ) : null}
                {isSupplier && draftOrder.status === "pending" ? (
                  <Link
                    href={ROUTES.orders}
                    className="tb-inv-btn tb-inv-btn-soft"
                  >
                    Orders coming soon →
                  </Link>
                ) : null}
              </div>
            </>
          )}
        </section>
      ) : null}

      {tab === "talk" && canTalk ? (
        <section className="tb-deal-sheet tb-deal-talk-shell">
          <div className="tb-deal-talk-shell__intro">
            <p className="tb-deal-kicker">Sidebar</p>
            <h2>Talk it through</h2>
            <p className="tb-inv-muted">
              A quiet lane with {chatPeer?.name || counterpartName} — for nuance the quotation
              does not need to carry.
            </p>
          </div>
          {isBuyer && rfq.invites.length > 1 ? (
            <label className="tb-inv-field tb-deal-talk-shell__pick">
              Who is sitting opposite
              <select
                value={chatPeer?.id || ""}
                onChange={(e) => setChatSupplierId(e.target.value)}
              >
                {rfq.invites
                  .filter((inv) => inv.supplier_business_id)
                  .map((inv) => (
                    <option key={inv.supplier_business_id!} value={inv.supplier_business_id!}>
                      {inv.supplier_name || "Supplier"}
                    </option>
                  ))}
              </select>
            </label>
          ) : null}
          {chatPeer ? (
            <RfqThread
              rfqId={rfqId}
              counterpartyId={chatPeer.id}
              counterpartyName={chatPeer.name}
              counterpartyLogoUrl={chatPeer.logoUrl}
              myLogoUrl={business?.logo_url}
              subject={rfq.title}
            />
          ) : (
            <p className="tb-inv-muted">Chat opens once a supplier is on this request.</p>
          )}
        </section>
      ) : null}

      <p className="tb-inv-foot">
        <Link href={ROUTES.procurement}>← Back to the desk</Link>
      </p>
    </div>
  );
}
