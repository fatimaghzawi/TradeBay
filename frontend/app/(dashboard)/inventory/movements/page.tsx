"use client";

import { PermissionGate, SupplierOnlyGate } from "@/components/auth/PermissionGate";
import {
  InventoryEmpty,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  InventoryToolbar,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import {
  catalogApi,
  type InventoryTransaction,
  type Product,
} from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

function MovementsInner() {
  const { business } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [txs, setTxs] = useState<(InventoryTransaction & { product_name?: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const ownId = business?.id;
    void catalogApi
      .listProducts({ page_size: 100, supplier_business_id: ownId })
      .then(async (result) => {
        const owned = ownId
          ? result.data.filter((p) => p.business_account_id === ownId)
          : result.data;
        setProducts(owned);
        const batch = owned.slice(0, 30);
        const batches = await Promise.all(
          batch.map(async (p) => {
            try {
              const page = await catalogApi.listTransactions(p.id, { page_size: 20 });
              return page.data.map((tx) => ({ ...tx, product_name: p.name }));
            } catch {
              return [] as (InventoryTransaction & { product_name?: string })[];
            }
          }),
        );
        const flat = batches.flat().sort((a, b) => {
          const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
          const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
          return tb - ta;
        });
        setTxs(flat);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load movements.");
      })
      .finally(() => setLoading(false));
  }, [business?.id]);

  const rows = useMemo(() => {
    let list = txs;
    if (productId !== "all") list = list.filter((t) => t.product_id === productId);
    if (typeFilter !== "all") {
      list = list.filter((t) => t.transaction_type === typeFilter);
    }
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (t) =>
          (t.product_name ?? "").toLowerCase().includes(q) ||
          t.transaction_type.includes(q) ||
          (t.reason ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [productId, query, txs, typeFilter]);

  const types = useMemo(() => {
    return Array.from(new Set(txs.map((t) => t.transaction_type))).sort();
  }, [txs]);

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="My movements"
        description="Stock in, reserves, releases, and sales for products you listed."
      />

      <InventoryPanel title="Movement log" subtitle="Filter by product, type, or notes">
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search product or reason…"
            className="min-w-[14rem] flex-1"
          />
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="all">All products</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="all">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t.split("_").join(" ")}
              </option>
            ))}
          </select>
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Movements failed">
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="movements" />
        ) : rows.length === 0 ? (
          <InventoryEmpty
            mark="⇄"
            title="No movements match"
            body="Record stock on a product to see history here."
          />
        ) : (
          <div className="tb-inv-table-wrap">
            <table className="tb-inv-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Product</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Balance</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((tx) => {
                  const outbound =
                    tx.transaction_type.includes("sale") ||
                    tx.transaction_type.includes("reserve");
                  return (
                    <tr key={tx.id}>
                      <td className="text-xs text-muted-foreground">
                        {tx.created_at
                          ? new Date(tx.created_at).toLocaleString()
                          : "—"}
                      </td>
                      <td>
                        <Link
                          href={ROUTES.inventoryProduct(tx.product_id)}
                          className="font-semibold text-heading hover:underline"
                        >
                          {tx.product_name ?? "Product"}
                        </Link>
                      </td>
                      <td className="capitalize">
                        {tx.transaction_type.split("_").join(" ")}
                      </td>
                      <td
                        className={`font-semibold ${outbound ? "text-destructive" : "text-success"}`}
                      >
                        {outbound ? `−${tx.quantity}` : `+${tx.quantity}`}
                      </td>
                      <td>
                        {tx.new_available} avail · {tx.new_reserved} res
                      </td>
                      <td className="text-sm text-muted-foreground">{tx.reason ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </InventoryPanel>
    </div>
  );
}

export default function InventoryMovementsPage() {
  return (
    <PermissionGate permission="inventory.read">
      <SupplierOnlyGate>
        <MovementsInner />
      </SupplierOnlyGate>
    </PermissionGate>
  );
}
