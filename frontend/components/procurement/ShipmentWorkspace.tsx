"use client";

import { StatusBadge } from "@/components/catalog/InventoryUi";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import { procurementApi, type Shipment } from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { formatEta, SHIPMENT_STATUS_LABEL } from "@/lib/procurement/rfqLifecycle";
import { issuesToFieldMap, validateUpload } from "@/lib/validation/common";
import {
  evidenceUrlSchema,
  receiveQtySchema,
} from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useState } from "react";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";

const TRACK = [
  "preparing",
  "shipped",
  "in_transit",
  "out_for_delivery",
  "delivered",
] as const;

type Props = { shipmentId: string };

export function ShipmentWorkspace({ shipmentId }: Props) {
  const { business } = useAuth();
  const isSupplier = business?.type === "supplier";
  const isBuyer = business?.type === "buyer";
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [receiveQty, setReceiveQty] = useState<Record<string, string>>({});
  const [fileError, setFileError] = useState<string | null>(null);
  const [receiveErrors, setReceiveErrors] = useState<Record<string, string>>({});
  const evidenceLive = useLiveFields(evidenceUrlSchema, { url: evidenceUrl });

  async function load() {
    try {
      const data = await procurementApi.getShipment(shipmentId);
      setShipment(data);
      setReceiveQty(
        Object.fromEntries(data.items.map((i) => [i.order_item_id || i.id, i.quantity])),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load shipment");
    }
  }

  useEffect(() => {
    void load();
  }, [shipmentId]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That step didn't complete. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!shipment && !error) return <LoadingEntity entity="shipment" />;
  if (!shipment) {
    return (
      <FeedbackBanner tone="error" title="Shipment not found">
        {error}
      </FeedbackBanner>
    );
  }

  const stageIdx = Math.max(
    0,
    TRACK.findIndex((s) => s === shipment.status),
  );

  return (
    <div className="tb-inv-page">
      <DirectoryMast
        title={shipment.shipment_number}
        size="page"
        mark="Shipment"
        lede={
          <>
            {shipment.carrier_name || "Carrier TBD"}
            <span className="mt-1 block text-sm opacity-80">
              {shipment.estimated_delivery_at
                ? `Estimated arrival · ${formatEta(shipment.estimated_delivery_at)}`
                : "Estimated arrival not set"}
            </span>
          </>
        }
        meta={<StatusBadge status={shipment.status} />}
      />

      {error ? (
        <FeedbackBanner tone="error" title="Something went wrong">
          {error}
        </FeedbackBanner>
      ) : null}

      <dl className="tb-inv-meta-strip">
        <div>
          <dt>Status</dt>
          <dd>{SHIPMENT_STATUS_LABEL[shipment.status] || shipment.status}</dd>
        </div>
        <div>
          <dt>Estimated arrival</dt>
          <dd>{formatEta(shipment.estimated_delivery_at) || "—"}</dd>
        </div>
        <div>
          <dt>Shipped</dt>
          <dd>{formatEta(shipment.shipped_at) || "—"}</dd>
        </div>
        <div>
          <dt>Delivered</dt>
          <dd>{formatEta(shipment.delivered_at) || "—"}</dd>
        </div>
      </dl>

      <ol className="tb-inv-lifecycle">
        {TRACK.map((stage, i) => (
          <li key={stage} className={i <= stageIdx ? "is-done" : undefined} data-current={i === stageIdx}>
            {stage.replaceAll("_", " ")}
          </li>
        ))}
      </ol>

      <div className="tb-inv-split">
        <section className="tb-inv-panel">
          <h2>Shipment items</h2>
          <ul className="tb-inv-entity-list">
            {shipment.items.map((item) => (
              <li key={item.id} className="tb-inv-entity-row">
                <div>
                  <strong>{item.product_name_snapshot}</strong>
                  <span>{item.sku_snapshot}</span>
                </div>
                <span>
                  {item.quantity} {item.unit}
                </span>
              </li>
            ))}
          </ul>

          <h3 className="tb-inv-subhead">Timeline</h3>
          <ol className="tb-inv-timeline">
            {shipment.tracking_events.map((ev, i) => (
              <li key={`${ev.status}-${i}`}>
                <strong>{ev.status.replaceAll("_", " ")}</strong>
                <span>{ev.description || ev.location || "—"}</span>
                <time>{ev.occurred_at ? new Date(ev.occurred_at).toLocaleString() : ""}</time>
              </li>
            ))}
          </ol>
        </section>

        <section className="tb-inv-panel">
          {isSupplier && shipment.status === "delivered" ? (
            <>
              <h2>Delivery evidence</h2>
              <label>
                Proof URL
                <input
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  onBlur={() => evidenceLive.touch("url")}
                  placeholder="https://…"
                />
                <FieldError error={evidenceLive.errors.url} />
              </label>
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
                disabled={busy || !evidenceUrl.trim()}
                onClick={() => {
                  if (!evidenceLive.finish()) return;
                  void run(() =>
                    procurementApi
                      .addDeliveryEvidence(shipmentId, {
                        evidence_type: "pod",
                        url: evidenceUrl.trim(),
                      })
                      .then(() => undefined),
                  );
                }}
              >
                <BusyText busy={busy}>Save evidence link</BusyText></button>
              <label>
                Or upload file
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const message = validateUpload(file, {
                      kinds: "document",
                      label: "Evidence file",
                    });
                    if (message) {
                      setFileError(message);
                      e.target.value = "";
                      return;
                    }
                    setFileError(null);
                    void run(async () => {
                      const form = new FormData();
                      form.append("file", file);
                      form.append("evidence_type", "pod");
                      const res = await fetch(
                        `/api/v1/shipments/${shipmentId}/delivery-evidence/upload`,
                        { method: "POST", body: form, credentials: "include" },
                      );
                      if (!res.ok) {
                        const body = await res.json().catch(() => null);
                        throw new ApiError(body?.error?.message || "Upload failed", {
                          code: "UPLOAD",
                          status: res.status,
                        });
                      }
                    });
                  }}
                />
                <FieldError error={fileError} />
              </label>
            </>
          ) : null}

          {shipment.delivery_evidence.length > 0 ? (
            <>
              <h3 className="tb-inv-subhead">Evidence on file</h3>
              <ul className="tb-inv-entity-list">
                {shipment.delivery_evidence.map((e, i) => (
                  <li key={`${e.url}-${i}`}>
                    <a href={mediaUrl(e.url)} target="_blank" rel="noreferrer">
                      {e.evidence_type}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {isBuyer && shipment.status === "delivered" && !shipment.received_at ? (
            <>
              <h2>Confirm receipt</h2>
              {shipment.items.map((item) => {
                const key = item.order_item_id || item.id;
                return (
                  <label key={item.id}>
                    Accepted qty — {item.product_name_snapshot}
                    <NumberInput
                      kind="integer"
                      value={receiveQty[key] ?? item.quantity}
                      onChange={(e) =>
                        setReceiveQty((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                    <FieldError error={receiveErrors[key]} />
                  </label>
                );
              })}
              <button
                type="button"
                className="tb-inv-btn tb-inv-btn-accent"
                disabled={busy}
                onClick={() => {
                  const next: Record<string, string> = {};
                  for (const item of shipment.items) {
                    const key = item.order_item_id || item.id;
                    const accepted = receiveQty[key] ?? item.quantity;
                    const parsed = receiveQtySchema.safeParse({ quantity: accepted });
                    if (!parsed.success) {
                      next[key] = issuesToFieldMap(parsed.error.issues).quantity ?? "Invalid quantity";
                    }
                  }
                  setReceiveErrors(next);
                  if (Object.keys(next).length) return;
                  void run(() =>
                    procurementApi
                      .receiveShipment(shipmentId, {
                        complete_order: true,
                        lines: shipment.items.map((item) => {
                          const key = item.order_item_id || item.id;
                          const accepted = receiveQty[key] ?? item.quantity;
                          const shipped = Number(item.quantity);
                          const recv = Number(accepted);
                          const missing = Math.max(shipped - recv, 0);
                          return {
                            order_item_id: item.order_item_id!,
                            received_quantity: String(recv),
                            damaged_quantity: "0",
                            missing_quantity: String(missing),
                            rejected_quantity: "0",
                          };
                        }),
                      })
                      .then(() => undefined),
                  );
                }}
              >
                <BusyText busy={busy}>Confirm receipt</BusyText></button>
            </>
          ) : null}

          {shipment.received_at ? (
            <p className="tb-inv-muted">
              Received {new Date(shipment.received_at).toLocaleString()}
            </p>
          ) : null}

          {shipment.order_id ? (
            <p className="tb-inv-foot">
              <Link href={ROUTES.procurementOrder(shipment.order_id)}>← Back to purchase order</Link>
            </p>
          ) : (
            <p className="tb-inv-foot">
              <Link href={ROUTES.procurement}>← Back to procurement</Link>
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
