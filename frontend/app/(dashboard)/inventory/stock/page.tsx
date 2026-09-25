"use client";

import { PermissionGate, SupplierOnlyGate } from "@/components/auth/PermissionGate";
import {
  InventoryEmpty,
  InventoryPageHeader,
  InventoryPanel,
  InventorySkeleton,
  InventoryToolbar,
  StatusBadge,
} from "@/components/catalog/InventoryUi";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

function StockInner() {
  const { business } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [stockFilter, setStockFilter] = useState<"all" | "in" | "low" | "out">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const ownId = business?.id;
    void catalogApi
      .listProducts({
        include_details: true,
        page_size: 100,
        supplier_business_id: ownId,
      })
      .then((result) => {
        const rows = ownId
          ? result.data.filter((p) => p.business_account_id === ownId)
          : result.data;
        setProducts(rows);
        setError(null);
      })
      .catch((err) => {
        setProducts([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load stock.");
      })
      .finally(() => setLoading(false));
  }, [business?.id]);

  const rows = useMemo(() => {
    let list = products;
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q),
      );
    }
    list = list.filter((p) => {
      const avail = Number(p.inventory?.available_quantity ?? 0);
      if (stockFilter === "in") return avail > 0;
      if (stockFilter === "out") return avail <= 0;
      if (stockFilter === "low") return avail > 0 && avail < p.moq;
      return true;
    });
    return list.sort(
      (a, b) =>
        Number(a.inventory?.available_quantity ?? 0) -
        Number(b.inventory?.available_quantity ?? 0),
    );
  }, [products, query, stockFilter]);

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        title="My stock"
        description="Available and reserved quantities for products you listed."
        meta={
          rows.length > 0 ? (
            <span className="tb-inv-chip">{rows.length} SKUs</span>
          ) : null
        }
      />

      <InventoryPanel title="Stock board" subtitle="Thinnest shelves first — restock what buyers will request">
        <InventoryToolbar>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name or SKU…"
            className="min-w-[14rem] flex-1"
          />
          <select
            value={stockFilter}
            onChange={(e) => setStockFilter(e.target.value as typeof stockFilter)}
          >
            <option value="all">All stock</option>
            <option value="in">In stock</option>
            <option value="low">Below MOQ</option>
            <option value="out">Out of stock</option>
          </select>
        </InventoryToolbar>

        {error ? (
          <FeedbackBanner tone="error" title="Stock load failed">
            {error}
          </FeedbackBanner>
        ) : null}

        {loading ? (
          <InventorySkeleton entity="stock" />
        ) : rows.length === 0 ? (
          <InventoryEmpty
            mark="▤"
            title="No stock rows match"
            body="Adjust search or stock filters to see more SKUs."
          />
        ) : (
          <div className="tb-inv-table-wrap">
            <table className="tb-inv-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Available</th>
                  <th>Reserved</th>
                  <th>MOQ</th>
                  <th>Health</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => {
                  const avail = Number(p.inventory?.available_quantity ?? 0);
                  const stockStatus =
                    avail <= 0 ? "out" : avail < p.moq ? "low" : "ok";
                  return (
                    <tr key={p.id}>
                      <td>
                        <Link
                          href={ROUTES.inventoryProduct(p.id)}
                          className="font-semibold text-heading hover:underline"
                        >
                          {p.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">SKU {p.sku}</p>
                      </td>
                      <td className="font-semibold">
                        {p.inventory?.available_quantity ?? "0"}
                      </td>
                      <td>{p.inventory?.reserved_quantity ?? "0"}</td>
                      <td>{p.moq}</td>
                      <td>
                        <StatusBadge status={stockStatus} />
                      </td>
                      <td>
                        <Link
                          href={ROUTES.inventoryProduct(p.id)}
                          className="text-sm font-bold text-link hover:underline"
                        >
                          Open
                        </Link>
                      </td>
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

export default function InventoryStockPage() {
  return (
    <PermissionGate permission="inventory.read">
      <SupplierOnlyGate>
        <StockInner />
      </SupplierOnlyGate>
    </PermissionGate>
  );
}
