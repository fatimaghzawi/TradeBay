"use client";

import {
  InventoryEmpty,
  InventoryLinkBtn,
  InventorySkeleton,
} from "@/components/catalog/InventoryUi";
import { LebanonSupplierMap } from "@/components/suppliers/LebanonSupplierMap";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category, type Product } from "@/lib/api/catalogApi";
import { LEBANON_REGIONS } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import {
  countActiveFilters,
  deriveFilterBounds,
  emptySupplierFilters,
  filterSuppliers,
  groupProductsIntoSuppliers,
  LEBANON_MAP_CITIES,
  mergeSavedOntoEntries,
  SUPPLIER_TRAIT_OPTIONS,
  type SupplierDirectoryEntry,
  type SupplierSegment,
  type SupplierTrait,
} from "@/lib/suppliers/directory";
import {
  listSavedSuppliers,
  removeSupplier,
  SHORTLIST_EVENT,
  toggleSupplier,
  type SavedSupplier,
} from "@/lib/supplierShortlist";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type ViewMode = "list" | "grid";

function priceLabel(p: SupplierDirectoryEntry["sampleProducts"][number]) {
  if (!p.unitPrice) return "Ask";
  const cur = p.currency || "USD";
  return `From ${cur} ${p.unitPrice}/${p.unit}`;
}

function toggleValue<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
}

export function SupplierExplorer() {
  const { business } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [saved, setSaved] = useState<SavedSupplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState(() => emptySupplierFilters());
  const [view, setView] = useState<ViewMode>("list");
  const [sort, setSort] = useState<"relevant" | "products" | "name" | "moq" | "lead">(
    "relevant",
  );

  const refreshSaved = useCallback(() => {
    setSaved(listSavedSuppliers());
  }, []);

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
    void Promise.all([
      catalogApi.listProducts({
        status: "active",
        include_details: true,
        page: 1,
        page_size: 100,
      }),
      catalogApi.listCategories({ page_size: 100 }),
    ])
      .then(([prod, cats]) => {
        setProducts(prod.data);
        setCategories(cats.data.filter((c) => c.is_active));
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load suppliers.");
        setProducts([]);
        setCategories([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const nearHint = business?.address?.city || business?.address?.governorate || null;

  const allEntries = useMemo(() => {
    const grouped = groupProductsIntoSuppliers(products, categories);
    return mergeSavedOntoEntries(grouped, saved);
  }, [products, categories, saved]);

  const bounds = useMemo(() => deriveFilterBounds(allEntries), [allEntries]);

  const filterState = useMemo(
    () => ({ ...filters, nearHint }),
    [filters, nearHint],
  );

  const filtered = useMemo(() => {
    const rows = filterSuppliers(allEntries, filterState);
    const sorted = [...rows];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "products") sorted.sort((a, b) => b.productCount - a.productCount);
    else if (sort === "moq") {
      sorted.sort((a, b) => (a.minMoq ?? 99999) - (b.minMoq ?? 99999));
    } else if (sort === "lead") {
      sorted.sort((a, b) => (a.avgLeadTime ?? 99999) - (b.avgLeadTime ?? 99999));
    }
    return sorted;
  }, [allEntries, filterState, sort]);

  const featured = useMemo(
    () => allEntries.filter((s) => s.productCount > 0).slice(0, 4),
    [allEntries],
  );

  const categoryCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of allEntries) {
      for (const id of s.categoryIds) {
        map.set(id, (map.get(id) || 0) + 1);
      }
    }
    return map;
  }, [allEntries]);

  const traitCounts = useMemo(() => {
    const map = new Map<SupplierTrait, number>();
    for (const opt of SUPPLIER_TRAIT_OPTIONS) {
      map.set(
        opt.id,
        allEntries.filter((s) => s.traits.includes(opt.id)).length,
      );
    }
    return map;
  }, [allEntries]);

  const unitCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const u of bounds.units) {
      map.set(
        u,
        allEntries.filter((s) => s.units.includes(u)).length,
      );
    }
    return map;
  }, [allEntries, bounds.units]);

  const counts = useMemo(() => {
    const savedCount = allEntries.filter((s) => s.saved).length;
    const lowMoq = allEntries.filter((s) => s.lowMoq).length;
    const multi = allEntries.filter((s) => s.traits.includes("multi_category")).length;
    const near = nearHint
      ? filterSuppliers(allEntries, {
          ...emptySupplierFilters({ segment: "near", nearHint }),
        }).length
      : 0;
    return {
      all: allEntries.length,
      saved: savedCount,
      low_moq: lowMoq,
      multi_category: multi,
      near,
    };
  }, [allEntries, nearHint]);

  const cityCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const place of LEBANON_MAP_CITIES) {
      const n = allEntries.filter((s) => s.mapPlaceId === place.id).length;
      map.set(place.id, n);
    }
    return map;
  }, [allEntries]);

  const mapSuppliers = useMemo(
    () => filterSuppliers(allEntries, { ...filterState, location: "" }),
    [allEntries, filterState],
  );

  const activeFilterCount = countActiveFilters(filterState);
  const showFeatured =
    filters.segment === "all" &&
    activeFilterCount === 0 &&
    featured.length > 0;

  function patchFilters(patch: Partial<typeof filters>) {
    setFilters((prev) => ({ ...prev, ...patch }));
  }

  function clearFilters() {
    setFilters(emptySupplierFilters({ segment: "all" }));
  }

  function onToggleSave(entry: SupplierDirectoryEntry) {
    toggleSupplier({ id: entry.id, name: entry.name });
    refreshSaved();
  }

  const segments: { id: SupplierSegment; label: string; count: number; hint?: string }[] = [
    { id: "all", label: "All suppliers", count: counts.all },
    { id: "saved", label: "Saved", count: counts.saved },
    { id: "low_moq", label: "Low MOQ", count: counts.low_moq },
    { id: "multi_category", label: "Multi-category", count: counts.multi_category },
    {
      id: "near",
      label: nearHint ? `Near ${nearHint}` : "Near you",
      count: counts.near,
      hint: nearHint ? undefined : "Set your company location to use this filter",
    },
  ];

  const moqSlider = filters.maxMoq ?? bounds.moqMax;
  const leadSlider = filters.maxLeadDays ?? bounds.leadMax;

  return (
    <div className="tb-mkt-explore tb-sup-explore">
      <DirectoryMast
        title="Suppliers"
        lede="Find suppliers across Lebanon."
        searchId="sup-search"
        searchValue={filters.query}
        searchPlaceholder="Search suppliers, products, or categories…"
        onSearchChange={(v) => patchFilters({ query: v })}
        stats={[
          { value: loading ? "—" : allEntries.length, label: "suppliers" },
          { value: loading ? "—" : products.length, label: "live products" },
          { value: loading ? "—" : saved.length, label: "shortlisted" },
        ]}
      />

      <div className="tb-mkt-segments tb-sup-segments" role="tablist" aria-label="Supplier segments">
        {segments.map((seg) => (
          <button
            key={seg.id}
            type="button"
            role="tab"
            aria-selected={filters.segment === seg.id}
            className={filters.segment === seg.id ? "is-active" : ""}
            title={seg.hint}
            disabled={seg.id === "near" && !nearHint}
            onClick={() => patchFilters({ segment: seg.id })}
          >
            <strong>{seg.label}</strong>
            <span>{seg.count}</span>
          </button>
        ))}
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load directory">
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <InventorySkeleton entity="suppliers" />
      ) : (
        <div className="tb-sup-layout">
          <div className="tb-sup-rail">
          <aside className="tb-sup-filters" aria-label="Refine search">
            <div className="tb-sup-filters__head">
              <h2>Refine your search</h2>
              {activeFilterCount > 0 ? (
                <span className="tb-sup-filters__count">{activeFilterCount} active</span>
              ) : null}
            </div>

            <fieldset className="tb-sup-filter-block">
              <legend>Location</legend>
              <label className="tb-sup-filter-field">
                <span className="sr-only">Region or city</span>
                <select
                  value={filters.location}
                  onChange={(e) => patchFilters({ location: e.target.value })}
                >
                  <option value="">All Lebanon</option>
                  <optgroup label="Governorates">
                    {LEBANON_REGIONS.map((r) => (
                      <option key={r.value} value={r.label}>
                        {r.label}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Cities">
                    {LEBANON_MAP_CITIES.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label} ({cityCounts.get(c.id) || 0})
                      </option>
                    ))}
                  </optgroup>
                </select>
              </label>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Categories</legend>
              <div className="tb-sup-check-list">
                {categories.length === 0 ? (
                  <p className="tb-sup-filter-empty">No categories yet.</p>
                ) : (
                  categories.map((c) => {
                    const count = categoryCounts.get(c.id) || 0;
                    const checked = filters.categoryIds.includes(c.id);
                    return (
                      <label key={c.id} className={!count ? "is-muted" : undefined}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={!count && !checked}
                          onChange={() =>
                            patchFilters({
                              categoryIds: toggleValue(filters.categoryIds, c.id),
                            })
                          }
                        />
                        <span>{c.name}</span>
                        <em>{count}</em>
                      </label>
                    );
                  })
                )}
              </div>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Capabilities</legend>
              <div className="tb-sup-check-list">
                {SUPPLIER_TRAIT_OPTIONS.map((opt) => {
                  const count = traitCounts.get(opt.id) || 0;
                  const checked = filters.traits.includes(opt.id);
                  return (
                    <label
                      key={opt.id}
                      title={opt.hint}
                      className={!count ? "is-muted" : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!count && !checked}
                        onChange={() =>
                          patchFilters({
                            traits: toggleValue(filters.traits, opt.id),
                          })
                        }
                      />
                      <span>{opt.label}</span>
                      <em>{count}</em>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Minimum order quantity</legend>
              <div className="tb-sup-slider">
                <div className="tb-sup-slider__meta">
                  <span>Up to {moqSlider}</span>
                  <button
                    type="button"
                    className="tb-sup-slider__reset"
                    hidden={filters.maxMoq == null}
                    onClick={() => patchFilters({ maxMoq: null })}
                  >
                    Any
                  </button>
                </div>
                <input
                  type="range"
                  min={1}
                  max={bounds.moqMax}
                  step={1}
                  value={moqSlider}
                  onChange={(e) => patchFilters({ maxMoq: Number(e.target.value) })}
                />
                <div className="tb-sup-slider__ends">
                  <span>1</span>
                  <span>{bounds.moqMax}+</span>
                </div>
              </div>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Lead time</legend>
              <div className="tb-sup-slider">
                <div className="tb-sup-slider__meta">
                  <span>Up to {leadSlider} days</span>
                  <button
                    type="button"
                    className="tb-sup-slider__reset"
                    hidden={filters.maxLeadDays == null}
                    onClick={() => patchFilters({ maxLeadDays: null })}
                  >
                    Any
                  </button>
                </div>
                <input
                  type="range"
                  min={1}
                  max={bounds.leadMax}
                  step={1}
                  value={leadSlider}
                  onChange={(e) => patchFilters({ maxLeadDays: Number(e.target.value) })}
                />
                <div className="tb-sup-slider__ends">
                  <span>1d</span>
                  <span>{bounds.leadMax}d</span>
                </div>
              </div>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Catalog size</legend>
              <div className="tb-sup-pill-row">
                {[0, 1, 3, 5, 10].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={filters.minProducts === n ? "is-active" : ""}
                    onClick={() => patchFilters({ minProducts: n })}
                  >
                    {n === 0 ? "Any" : `${n}+`}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset className="tb-sup-filter-block">
              <legend>Unit price range</legend>
              <div className="tb-sup-price-row">
                <label>
                  <span>Min</span>
                  <NumberInput
                    kind="decimal"
                    min={0}
                    placeholder={String(bounds.priceMin)}
                    value={filters.minPrice ?? ""}
                    onChange={(e) =>
                      patchFilters({
                        minPrice: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  <span>Max</span>
                  <NumberInput
                    kind="decimal"
                    min={0}
                    placeholder={String(bounds.priceMax)}
                    value={filters.maxPrice ?? ""}
                    onChange={(e) =>
                      patchFilters({
                        maxPrice: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
            </fieldset>

            {bounds.units.length > 0 ? (
              <fieldset className="tb-sup-filter-block">
                <legend>Units</legend>
                <div className="tb-sup-check-list tb-sup-check-list--compact">
                  {bounds.units.map((u) => {
                    const count = unitCounts.get(u) || 0;
                    const checked = filters.units.includes(u);
                    return (
                      <label key={u} className={!count ? "is-muted" : undefined}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={!count && !checked}
                          onChange={() =>
                            patchFilters({
                              units: toggleValue(filters.units, u),
                            })
                          }
                        />
                        <span>{u}</span>
                        <em>{count}</em>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ) : null}

            <fieldset className="tb-sup-filter-block">
              <legend>Shortlist</legend>
              <label className="tb-sup-switch">
                <input
                  type="checkbox"
                  checked={filters.savedOnly}
                  onChange={(e) => patchFilters({ savedOnly: e.target.checked })}
                />
                <span>Saved suppliers only</span>
              </label>
            </fieldset>

            <div className="tb-sup-filters__actions">
              <a href="#all-suppliers-title" className="tb-sup-filters__apply">
                Show {filtered.length} result{filtered.length === 1 ? "" : "s"}
              </a>
              <button type="button" className="tb-sup-filters__clear" onClick={clearFilters}>
                Clear all filters
              </button>
            </div>

            <div className="tb-sup-filters__saved">
              <h3>Your shortlist</h3>
              {saved.length === 0 ? (
                <p>Saved for later.</p>
              ) : (
                <ul>
                  {saved.slice(0, 6).map((s) => (
                    <li key={s.id}>
                      <Link href={ROUTES.supplierProfile(s.id)}>{s.name}</Link>
                      <button
                        type="button"
                        onClick={() => {
                          removeSupplier(s.id);
                          refreshSaved();
                        }}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </aside>

          <LebanonSupplierMap
            suppliers={mapSuppliers}
            selectedCity={filters.location}
            onSelectCity={(city) => patchFilters({ location: city })}
          />
          </div>

          <div className="tb-sup-main">
            {showFeatured ? (
              <section className="tb-sup-featured" aria-labelledby="featured-title">
                <div className="tb-sup-section-head">
                  <h2 id="featured-title">Featured suppliers</h2>
                  <p>Featured suppliers</p>
                </div>
                <div className="tb-sup-featured__rail">
                  {featured.map((s) => (
                    <article key={s.id} className="tb-sup-card">
                      <div className="tb-sup-card__media" aria-hidden>
                        {s.coverImage ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={mediaUrl(s.coverImage)} alt="" />
                        ) : (
                          <span>{s.name.slice(0, 1)}</span>
                        )}
                        {s.saved ? <em className="tb-sup-badge is-saved">Saved</em> : null}
                      </div>
                      <div className="tb-sup-card__body">
                        <h3 className="tb-verified-inline">
                          {s.name}
                          <VerifiedBadge
                            verified={s.verified}
                            showWhenUnverified={false}
                          />
                        </h3>
                        <p>
                          {s.categories[0] || "General"}
                          {s.locationLabel
                            ? ` · ${s.locationLabel}`
                            : s.primaryOrigin
                              ? ` · ${s.primaryOrigin}`
                              : ""}
                        </p>
                        <div className="tb-sup-card__tags">
                          <span>{s.productCount} products</span>
                          {s.lowMoq ? <span>Low MOQ</span> : null}
                          {s.minMoq != null ? <span>MOQ {s.minMoq}</span> : null}
                        </div>
                        <div className="tb-sup-card__actions">
                          <Link href={ROUTES.supplierProfile(s.id)}>View profile</Link>
                          <button type="button" onClick={() => onToggleSave(s)}>
                            {s.saved ? "♥" : "♡"}
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

              <section className="tb-sup-directory" aria-labelledby="all-suppliers-title">
                <div className="tb-sup-directory__head">
                  <div className="tb-sup-directory__intro">
                    <h2 id="all-suppliers-title">All suppliers</h2>
                    <p>
                      <span>
                        {filtered.length} supplier{filtered.length === 1 ? "" : "s"} found
                      </span>
                      {activeFilterCount > 0 ? (
                        <span>
                          {" "}
                          · {activeFilterCount} filter{activeFilterCount === 1 ? "" : "s"}
                        </span>
                      ) : null}
                      {products.length ? (
                        <span className="tb-sup-directory__meta-soft">
                          {" "}
                          · from {products.length} live products
                        </span>
                      ) : null}
                    </p>
                  </div>
                  <div className="tb-sup-directory__controls">
                    <label className="tb-sup-directory__sort">
                      <span>Sort</span>
                      <select
                        value={sort}
                        onChange={(e) => setSort(e.target.value as typeof sort)}
                      >
                        <option value="relevant">Most relevant</option>
                        <option value="products">Most products</option>
                        <option value="moq">Lowest MOQ</option>
                        <option value="lead">Fastest lead time</option>
                        <option value="name">Name A–Z</option>
                      </select>
                    </label>
                    <div className="tb-sup-view-toggle" role="group" aria-label="View mode">
                      <button
                        type="button"
                        className={view === "list" ? "is-active" : ""}
                        onClick={() => setView("list")}
                      >
                        List
                      </button>
                      <button
                        type="button"
                        className={view === "grid" ? "is-active" : ""}
                        onClick={() => setView("grid")}
                      >
                        Grid
                      </button>
                    </div>
                  </div>
                </div>

                {filtered.length === 0 ? (
                  <InventoryEmpty
                    title="No suppliers match"
                    body="Try clearing filters or search."
                    action={
                      <>
                        <button type="button" className="tb-inv-btn tb-inv-btn-soft" onClick={clearFilters}>
                          Clear filters
                        </button>
                        <InventoryLinkBtn href={ROUTES.aiSourcing} tone="soft">
                          Ask the Bay
                        </InventoryLinkBtn>
                      </>
                    }
                  />
                ) : view === "grid" ? (
                  <div className="tb-sup-grid">
                    {filtered.map((s) => (
                      <SupplierGridCard key={s.id} entry={s} onToggleSave={onToggleSave} />
                    ))}
                  </div>
                ) : (
                  <ul className="tb-sup-list">
                    {filtered.map((s) => (
                      <SupplierListRow key={s.id} entry={s} onToggleSave={onToggleSave} />
                    ))}
                  </ul>
                )}
              </section>
          </div>
        </div>
      )}
    </div>
  );
}

function SupplierGridCard({
  entry,
  onToggleSave,
}: {
  entry: SupplierDirectoryEntry;
  onToggleSave: (e: SupplierDirectoryEntry) => void;
}) {
  return (
    <article className="tb-sup-card">
      <div className="tb-sup-card__media" aria-hidden>
        {entry.coverImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl(entry.coverImage)} alt="" />
        ) : (
          <span>{entry.name.slice(0, 1)}</span>
        )}
        {entry.saved ? <em className="tb-sup-badge is-saved">Saved</em> : null}
        {entry.lowMoq ? <em className="tb-sup-badge tb-sup-badge--media">Low MOQ</em> : null}
      </div>
      <div className="tb-sup-card__body">
        <h3 className="tb-verified-inline">
          {entry.name}
          <VerifiedBadge
            verified={entry.verified}
            showWhenUnverified={false}
          />
        </h3>
        <p>
          {entry.categories[0] || "General"}
          {entry.primaryOrigin ? ` · ${entry.primaryOrigin}` : ""}
        </p>
        <div className="tb-sup-card__tags">
          <span>{entry.productCount} products</span>
          {entry.minMoq != null ? <span>MOQ {entry.minMoq}</span> : null}
          {entry.avgLeadTime != null ? <span>~{entry.avgLeadTime}d lead</span> : null}
        </div>
        <div className="tb-sup-card__actions">
          <Link href={ROUTES.supplierProfile(entry.id)}>View profile →</Link>
          <button type="button" onClick={() => onToggleSave(entry)}>
            {entry.saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </article>
  );
}

function SupplierListRow({
  entry,
  onToggleSave,
}: {
  entry: SupplierDirectoryEntry;
  onToggleSave: (e: SupplierDirectoryEntry) => void;
}) {
  return (
    <li className="tb-sup-row">
      <div className="tb-sup-row__media" aria-hidden>
        {entry.coverImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl(entry.coverImage)} alt="" />
        ) : (
          <span>{entry.name.slice(0, 2).toUpperCase()}</span>
        )}
      </div>

      <div className="tb-sup-row__main">
        <div className="tb-sup-row__title">
          <h3 className="tb-verified-inline">
            <Link href={ROUTES.supplierProfile(entry.id)}>{entry.name}</Link>
            <VerifiedBadge
              verified={entry.verified}
              showWhenUnverified={false}
            />
          </h3>
          {entry.saved ? <span className="tb-sup-badge is-saved">Saved</span> : null}
          {entry.lowMoq ? <span className="tb-sup-badge">Low MOQ</span> : null}
          {entry.traits.includes("fast_lead") ? (
            <span className="tb-sup-badge">Fast lead</span>
          ) : null}
          {entry.traits.includes("in_stock") ? (
            <span className="tb-sup-badge">In stock</span>
          ) : null}
        </div>

        <p className="tb-sup-row__meta">
          {entry.categories.slice(0, 3).join(" · ") || "General catalog"}
          {entry.primaryOrigin ? ` · ${entry.primaryOrigin}` : ""}
          {entry.productCount ? ` · ${entry.productCount} products` : " · Shortlisted"}
        </p>

        {entry.sampleProducts.length > 0 ? (
          <ul className="tb-sup-row__products">
            {entry.sampleProducts.map((p) => (
              <li key={p.id}>
                <Link href={ROUTES.inventoryProduct(p.id)}>
                  <span className="tb-sup-row__thumb" aria-hidden>
                    {p.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(p.imageUrl)} alt="" />
                    ) : (
                      p.name.slice(0, 1)
                    )}
                  </span>
                  <span className="tb-sup-row__product-copy">
                    <strong>{p.name}</strong>
                    <em>{priceLabel(p)}</em>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="tb-sup-row__side">
        <div className="tb-sup-row__facts">
          <div>
            <span>Min order</span>
            <strong>{entry.minMoq != null ? entry.minMoq : "—"}</strong>
          </div>
          <div>
            <span>Lead time</span>
            <strong>{entry.avgLeadTime != null ? `~${entry.avgLeadTime}d` : "—"}</strong>
          </div>
          <div>
            <span>Listings</span>
            <strong>{entry.productCount}</strong>
          </div>
        </div>
        <div className="tb-sup-row__cta">
          <Link href={ROUTES.supplierProfile(entry.id)} className="tb-sup-row__primary">
            View profile
          </Link>
          <Link href={ROUTES.supplierProducts(entry.id)} className="tb-sup-row__ghost">
            Products
          </Link>
          <button type="button" className="tb-sup-row__ghost" onClick={() => onToggleSave(entry)}>
            {entry.saved ? "Saved ✓" : "Save"}
          </button>
        </div>
      </div>
    </li>
  );
}
