import type { Category, Product } from "@/lib/api/catalogApi";
import { isSupplierSaved, type SavedSupplier } from "@/lib/supplierShortlist";
import {
  LEBANON_MAP_PLACES,
  type LebanonMapPlace,
} from "@/lib/suppliers/lebanonGeo";

export type { LebanonMapPlace };
export { LEBANON_MAP_PLACES };

export type SupplierSegment = "all" | "saved" | "low_moq" | "multi_category" | "near";

export type SupplierTrait =
  | "low_moq"
  | "fast_lead"
  | "in_stock"
  | "open_pricing"
  | "multi_category"
  | "has_media"
  | "broad_catalog";

export const SUPPLIER_TRAIT_OPTIONS: {
  id: SupplierTrait;
  label: string;
  hint: string;
}[] = [
  { id: "low_moq", label: "Low MOQ", hint: "Minimum order ≤ 20" },
  { id: "fast_lead", label: "Fast lead time", hint: "Average lead ≤ 7 days" },
  { id: "in_stock", label: "In stock now", hint: "Available quantity on at least one product" },
  { id: "open_pricing", label: "Open pricing", hint: "Published wholesale prices" },
  { id: "multi_category", label: "Multi-category", hint: "Lists in 2+ categories" },
  { id: "has_media", label: "Has product photos", hint: "At least one product image" },
  { id: "broad_catalog", label: "Broad catalog", hint: "5+ active products" },
];

export type SupplierDirectoryEntry = {
  id: string;
  name: string;
  logoUrl: string | null;
  productCount: number;
  categories: string[];
  categoryIds: string[];
  origins: string[];
  primaryOrigin: string | null;
  city: string | null;
  governorate: string | null;
  locationLabel: string | null;
  mapPlaceId: string | null;
  minMoq: number | null;
  maxMoq: number | null;
  avgLeadTime: number | null;
  minPrice: number | null;
  maxPrice: number | null;
  currency: string | null;
  units: string[];
  traits: SupplierTrait[];
  sampleProducts: {
    id: string;
    name: string;
    imageUrl: string | null;
    unitPrice: string | null;
    currency: string | null;
    unit: string;
  }[];
  coverImage: string | null;
  saved: boolean;
  lowMoq: boolean;
  verified: boolean;
};

export type SupplierFilterState = {
  segment: SupplierSegment;
  query: string;
  categoryIds: string[];
  location: string;
  nearHint?: string | null;
  traits: SupplierTrait[];
  maxMoq: number | null;
  maxLeadDays: number | null;
  minProducts: number;
  minPrice: number | null;
  maxPrice: number | null;
  units: string[];
  savedOnly: boolean;
};

export function emptySupplierFilters(
  overrides: Partial<SupplierFilterState> = {},
): SupplierFilterState {
  return {
    segment: "all",
    query: "",
    categoryIds: [],
    location: "",
    nearHint: null,
    traits: [],
    maxMoq: null,
    maxLeadDays: null,
    minProducts: 0,
    minPrice: null,
    maxPrice: null,
    units: [],
    savedOnly: false,
    ...overrides,
  };
}

function parsePrice(value: string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function groupProductsIntoSuppliers(
  products: Product[],
  categories: Category[],
  savedIds?: Set<string>,
): SupplierDirectoryEntry[] {
  const catName = new Map(categories.map((c) => [c.id, c.name]));
  const bySupplier = new Map<string, Product[]>();

  for (const p of products) {
    const id = p.business_account_id || p.supplier_id;
    if (!id) continue;
    const list = bySupplier.get(id) ?? [];
    list.push(p);
    bySupplier.set(id, list);
  }

  const entries: SupplierDirectoryEntry[] = [];

  for (const [id, items] of bySupplier) {
    const name =
      items.find((p) => p.supplier_name)?.supplier_name?.trim() || "Supplier";
    const logoUrl =
      items.find((p) => p.supplier_logo_url)?.supplier_logo_url ?? null;

    const categoryIds = [
      ...new Set(items.map((p) => p.category_id).filter(Boolean)),
    ];
    const categoriesLabels = categoryIds
      .map((cid) => catName.get(cid))
      .filter((n): n is string => Boolean(n));

    const origins = [
      ...new Set(
        items
          .map((p) => p.origin?.trim())
          .filter((o): o is string => Boolean(o)),
      ),
    ];

    const city =
      items.find((p) => p.supplier_city?.trim())?.supplier_city?.trim() || null;
    const governorate =
      items.find((p) => p.supplier_governorate?.trim())?.supplier_governorate?.trim() ||
      null;
    const locationLabel = [city, governorate].filter(Boolean).join(", ") || null;
    const mapPlaceId = resolveLebanonMapPlace({ city, governorate, origins });

    const moqs = items.map((p) => p.moq).filter((n) => Number.isFinite(n) && n > 0);
    const minMoq = moqs.length ? Math.min(...moqs) : null;
    const maxMoq = moqs.length ? Math.max(...moqs) : null;
    const leads = items
      .map((p) => p.lead_time_days)
      .filter((n) => Number.isFinite(n) && n >= 0);
    const avgLeadTime = leads.length
      ? Math.round(leads.reduce((a, b) => a + b, 0) / leads.length)
      : null;

    const prices: number[] = [];
    let currency: string | null = null;
    for (const p of items) {
      const price = p.prices?.find((pr) => pr.is_active) ?? p.prices?.[0];
      const n = parsePrice(price?.unit_price);
      if (n != null) {
        prices.push(n);
        currency = price?.currency || currency;
      }
    }
    const minPrice = prices.length ? Math.min(...prices) : null;
    const maxPrice = prices.length ? Math.max(...prices) : null;

    const units = [
      ...new Set(items.map((p) => (p.unit || "unit").toLowerCase()).filter(Boolean)),
    ];

    const inStock = items.some(
      (p) => Number(p.inventory?.available_quantity ?? 0) > 0,
    );
    const hasMedia = items.some(
      (p) =>
        Boolean(p.primary_image_url) ||
        Boolean(p.images?.length) ||
        Boolean(logoUrl),
    );
    const openPricing = prices.length > 0;
    const lowMoq = minMoq != null && minMoq <= 20;
    const fastLead = avgLeadTime != null && avgLeadTime <= 7;
    const multiCategory = categoryIds.length >= 2;
    const broadCatalog = items.length >= 5;

    const traits: SupplierTrait[] = [];
    if (lowMoq) traits.push("low_moq");
    if (fastLead) traits.push("fast_lead");
    if (inStock) traits.push("in_stock");
    if (openPricing) traits.push("open_pricing");
    if (multiCategory) traits.push("multi_category");
    if (hasMedia) traits.push("has_media");
    if (broadCatalog) traits.push("broad_catalog");

    const sampleProducts = items.slice(0, 4).map((p) => {
      const image =
        p.primary_image_url ||
        p.images?.find((img) => img.is_primary)?.url ||
        p.images?.[0]?.url ||
        null;
      const price = p.prices?.find((pr) => pr.is_active) ?? p.prices?.[0];
      return {
        id: p.id,
        name: p.name,
        imageUrl: image,
        unitPrice: price?.unit_price ?? null,
        currency: price?.currency ?? null,
        unit: p.unit || "unit",
      };
    });

    const coverImage =
      sampleProducts.find((s) => s.imageUrl)?.imageUrl || logoUrl || null;

    const saved = savedIds ? savedIds.has(id) : isSupplierSaved(id);
    const verified = items.some((p) => Boolean(p.supplier_verified));

    entries.push({
      id,
      name,
      logoUrl,
      productCount: items.length,
      categories: categoriesLabels,
      categoryIds,
      origins,
      primaryOrigin: locationLabel || origins[0] || null,
      city,
      governorate,
      locationLabel,
      mapPlaceId,
      minMoq,
      maxMoq,
      avgLeadTime,
      minPrice,
      maxPrice,
      currency,
      units,
      traits,
      sampleProducts,
      coverImage,
      saved,
      lowMoq,
      verified,
    });
  }

  return entries.sort((a, b) => {
    if (b.productCount !== a.productCount) return b.productCount - a.productCount;
    return a.name.localeCompare(b.name);
  });
}

export function filterSuppliers(
  entries: SupplierDirectoryEntry[],
  opts: SupplierFilterState,
): SupplierDirectoryEntry[] {
  const q = opts.query.trim().toLowerCase();
  return entries.filter((s) => {
    if (opts.savedOnly && !s.saved) return false;
    if (opts.segment === "saved" && !s.saved) return false;
    if (opts.segment === "low_moq" && !s.lowMoq) return false;
    if (opts.segment === "multi_category" && !s.traits.includes("multi_category")) {
      return false;
    }
    if (opts.segment === "near") {
      const hint = (opts.nearHint || "").toLowerCase();
      if (!hint) return false;
      const hay = locationHaystack(s);
      if (!hay.includes(hint) && !hint.includes(hay)) return false;
    }
    if (opts.categoryIds.length > 0) {
      const hit = opts.categoryIds.some((id) => s.categoryIds.includes(id));
      if (!hit) return false;
    }
    if (opts.location) {
      const loc = opts.location.toLowerCase();
      const hay = locationHaystack(s);
      const placeMatch =
        s.mapPlaceId?.toLowerCase() === loc ||
        s.city?.toLowerCase() === loc ||
        s.governorate?.toLowerCase() === loc;
      if (!placeMatch && !hay.includes(loc)) return false;
    }
    if (opts.traits.length > 0) {
      const hit = opts.traits.every((t) => s.traits.includes(t));
      if (!hit) return false;
    }
    if (opts.maxMoq != null) {
      if (s.minMoq == null || s.minMoq > opts.maxMoq) return false;
    }
    if (opts.maxLeadDays != null) {
      if (s.avgLeadTime == null || s.avgLeadTime > opts.maxLeadDays) return false;
    }
    if (opts.minProducts > 0 && s.productCount < opts.minProducts) return false;
    if (opts.minPrice != null) {
      if (s.minPrice == null || s.minPrice < opts.minPrice) return false;
    }
    if (opts.maxPrice != null) {
      if (s.minPrice == null || s.minPrice > opts.maxPrice) return false;
    }
    if (opts.units.length > 0) {
      const hit = opts.units.some((u) => s.units.includes(u.toLowerCase()));
      if (!hit) return false;
    }
    if (q) {
      const hay = [
        s.name,
        ...s.categories,
        ...s.origins,
        s.city,
        s.governorate,
        s.locationLabel,
        ...s.sampleProducts.map((p) => p.name),
        ...s.units,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export function mergeSavedOntoEntries(
  entries: SupplierDirectoryEntry[],
  saved: SavedSupplier[],
): SupplierDirectoryEntry[] {
  const savedMap = new Map(saved.map((s) => [s.id, s]));
  const fromCatalog = entries.map((e) => ({
    ...e,
    saved: savedMap.has(e.id),
  }));

  const known = new Set(fromCatalog.map((e) => e.id));
  const extras: SupplierDirectoryEntry[] = saved
    .filter((s) => !known.has(s.id))
    .map((s) => ({
      id: s.id,
      name: s.name,
      logoUrl: null,
      productCount: 0,
      categories: [],
      categoryIds: [],
      origins: [],
      primaryOrigin: null,
      city: null,
      governorate: null,
      locationLabel: null,
      mapPlaceId: null,
      minMoq: null,
      maxMoq: null,
      avgLeadTime: null,
      minPrice: null,
      maxPrice: null,
      currency: null,
      units: [],
      traits: [],
      sampleProducts: [],
      coverImage: null,
      saved: true,
      lowMoq: false,
      verified: false,
    }));

  return [...fromCatalog, ...extras];
}

export function deriveFilterBounds(entries: SupplierDirectoryEntry[]) {
  const moqs = entries.map((e) => e.minMoq).filter((n): n is number => n != null);
  const leads = entries
    .map((e) => e.avgLeadTime)
    .filter((n): n is number => n != null);
  const prices = entries
    .map((e) => e.minPrice)
    .filter((n): n is number => n != null);
  const units = [...new Set(entries.flatMap((e) => e.units))].sort();
  const maxProducts = Math.max(0, ...entries.map((e) => e.productCount));

  return {
    moqMax: moqs.length ? Math.max(50, Math.ceil(Math.max(...moqs) / 10) * 10) : 100,
    leadMax: leads.length ? Math.max(14, Math.ceil(Math.max(...leads) / 7) * 7) : 30,
    priceMax: prices.length ? Math.ceil(Math.max(...prices)) : 1000,
    priceMin: prices.length ? Math.floor(Math.min(...prices)) : 0,
    units,
    maxProducts: Math.max(maxProducts, 10),
  };
}

export function countActiveFilters(filters: SupplierFilterState): number {
  let n = 0;
  if (filters.categoryIds.length) n += 1;
  if (filters.location) n += 1;
  if (filters.traits.length) n += 1;
  if (filters.maxMoq != null) n += 1;
  if (filters.maxLeadDays != null) n += 1;
  if (filters.minProducts > 0) n += 1;
  if (filters.minPrice != null || filters.maxPrice != null) n += 1;
  if (filters.units.length) n += 1;
  if (filters.savedOnly) n += 1;
  if (filters.query.trim()) n += 1;
  return n;
}

/** Filter-dropdown shape kept for existing UI. */
export const LEBANON_MAP_CITIES = LEBANON_MAP_PLACES.map((p) => ({
  id: p.id,
  label: p.label,
  x: p.lng,
  y: p.lat,
}));

function locationHaystack(s: SupplierDirectoryEntry): string {
  return [s.city, s.governorate, s.locationLabel, s.primaryOrigin, ...s.origins]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function resolveLebanonMapPlace(input: {
  city?: string | null;
  governorate?: string | null;
  origins?: string[];
}): string | null {
  const tokens = [input.city, input.governorate, ...(input.origins || [])]
    .filter(Boolean)
    .map((t) => t!.toLowerCase().trim());
  if (!tokens.length) return null;

  for (const place of LEBANON_MAP_PLACES) {
    for (const token of tokens) {
      if (
        token === place.id.toLowerCase() ||
        place.aliases.some((a) => token === a || token.includes(a) || a.includes(token))
      ) {
        return place.id;
      }
    }
  }
  return null;
}

export function suppliersAtMapPlace(
  suppliers: SupplierDirectoryEntry[],
  placeId: string,
): SupplierDirectoryEntry[] {
  const needle = placeId.toLowerCase();
  return suppliers.filter(
    (s) =>
      s.mapPlaceId?.toLowerCase() === needle ||
      s.city?.toLowerCase() === needle ||
      s.governorate?.toLowerCase() === needle ||
      locationHaystack(s).includes(needle),
  );
}
