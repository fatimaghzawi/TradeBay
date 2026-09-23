"use client";

import { LebanonMapCanvas } from "@/components/suppliers/LebanonMapCanvas";
import { mediaUrl } from "@/lib/media";
import { ROUTES } from "@/lib/constants";
import {
  LEBANON_MAP_PLACES,
  suppliersAtMapPlace,
  type SupplierDirectoryEntry,
} from "@/lib/suppliers/directory";
import Link from "next/link";
import { useEffect, useId, useMemo, useState } from "react";

type Props = {
  suppliers: SupplierDirectoryEntry[];
  selectedCity: string;
  onSelectCity: (city: string) => void;
};

export function LebanonSupplierMap({
  suppliers,
  selectedCity,
  onSelectCity,
}: Props) {
  const titleId = useId();
  const [expanded, setExpanded] = useState(false);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [focusPlace, setFocusPlace] = useState<string>("");

  const mappedSuppliers = useMemo(
    () => suppliers.filter((s) => s.mapPlaceId),
    [suppliers],
  );

  const placePins = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of mappedSuppliers) {
      if (!s.mapPlaceId) continue;
      counts.set(s.mapPlaceId, (counts.get(s.mapPlaceId) || 0) + 1);
    }
    return LEBANON_MAP_PLACES.filter((p) => (counts.get(p.id) || 0) > 0).map((p) => ({
      ...p,
      count: counts.get(p.id) || 0,
    }));
  }, [mappedSuppliers]);

  const activePlace = focusPlace || selectedCity;

  const panelSuppliers = useMemo(() => {
    if (activePlace) return suppliersAtMapPlace(mappedSuppliers, activePlace);
    return mappedSuppliers;
  }, [activePlace, mappedSuppliers]);

  const overlayOpen = expanded || browseOpen;

  useEffect(() => {
    if (!overlayOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setExpanded(false);
        setBrowseOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [overlayOpen]);

  function togglePlace(id: string) {
    const next = selectedCity.toLowerCase() === id.toLowerCase() ? "" : id;
    onSelectCity(next);
    setFocusPlace(next);
    if (next) {
      setBrowseOpen(true);
      setExpanded(true);
    }
  }

  function openSupplierBrowse() {
    setBrowseOpen(true);
    setExpanded(true);
    if (!focusPlace && selectedCity) setFocusPlace(selectedCity);
  }

  function closeOverlay() {
    setExpanded(false);
    setBrowseOpen(false);
  }

  function renderShell(mode: "inline" | "overlay") {
    const isOverlay = mode === "overlay";
    return (
      <div className={`tb-lb-map ${isOverlay ? "is-expanded" : ""}`}>
        <div className="tb-lb-map__stage" aria-labelledby={titleId}>
          <p id={titleId} className="sr-only">
            Interactive Lebanon supplier map
          </p>

          <LebanonMapCanvas
            pins={placePins}
            activePlace={activePlace}
            onSelectPlace={togglePlace}
            resizeKey={isOverlay ? "overlay" : "inline"}
          />

          <button
            type="button"
            className="tb-lb-map__expand"
            aria-label={overlayOpen ? "Close map" : "Expand map"}
            onClick={() => {
              if (overlayOpen) closeOverlay();
              else setExpanded(true);
            }}
          >
            {overlayOpen ? (
              <span aria-hidden>×</span>
            ) : (
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
                <path
                  fill="currentColor"
                  d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"
                />
              </svg>
            )}
          </button>
        </div>

        {!isOverlay ? (
          <>
            <button type="button" className="tb-lb-map__cta" onClick={openSupplierBrowse}>
              View Suppliers on Map
              <span aria-hidden>→</span>
            </button>
            <p className="tb-lb-map__hint">
              {placePins.length === 0
                ? "No supplier locations on the map yet"
                : activePlace
                  ? `${panelSuppliers.length} supplier${panelSuppliers.length === 1 ? "" : "s"} in ${activePlace}`
                  : `${mappedSuppliers.length} supplier${mappedSuppliers.length === 1 ? "" : "s"} plotted from business addresses`}
            </p>
          </>
        ) : null}
      </div>
    );
  }

  return (
    <>
      {overlayOpen ? (
        <div className="tb-lb-map__spacer" aria-hidden />
      ) : (
        renderShell("inline")
      )}

      {overlayOpen ? (
        <div
          className="tb-lb-map-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Suppliers on Lebanon map"
        >
          <button
            type="button"
            className="tb-lb-map-overlay__backdrop"
            aria-label="Close map"
            onClick={closeOverlay}
          />
          <div className={`tb-lb-map-overlay__shell ${browseOpen ? "has-panel" : ""}`}>
            <div className="tb-lb-map-overlay__panel">{renderShell("overlay")}</div>

            {browseOpen ? (
              <aside className="tb-lb-map-panel" aria-label="Suppliers at this location">
                <div className="tb-lb-map-panel__head">
                  <div>
                    <h2>
                      {activePlace
                        ? `Suppliers in ${activePlace}`
                        : "Suppliers on the map"}
                    </h2>
                    <p>
                      {panelSuppliers.length} partner
                      {panelSuppliers.length === 1 ? "" : "s"} with a known Lebanon
                      address
                    </p>
                  </div>
                  <button type="button" onClick={closeOverlay} aria-label="Close">
                    ×
                  </button>
                </div>

                {placePins.length > 1 ? (
                  <div className="tb-lb-map-panel__chips">
                    <button
                      type="button"
                      className={!activePlace ? "is-active" : ""}
                      onClick={() => {
                        setFocusPlace("");
                        onSelectCity("");
                      }}
                    >
                      All ({mappedSuppliers.length})
                    </button>
                    {placePins.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        className={
                          activePlace.toLowerCase() === p.id.toLowerCase()
                            ? "is-active"
                            : ""
                        }
                        onClick={() => {
                          setFocusPlace(p.id);
                          onSelectCity(p.id);
                        }}
                      >
                        {p.label} ({p.count})
                      </button>
                    ))}
                  </div>
                ) : null}

                {panelSuppliers.length === 0 ? (
                  <p className="tb-lb-map-panel__empty">
                    No suppliers match this location. Tap another pin or clear the
                    filter.
                  </p>
                ) : (
                  <ul className="tb-lb-map-panel__list">
                    {panelSuppliers.map((s) => (
                      <li key={s.id} className="tb-lb-map-panel__card">
                        <div className="tb-lb-map-panel__media" aria-hidden>
                          {s.coverImage || s.logoUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(s.coverImage || s.logoUrl)} alt="" />
                          ) : (
                            <span>{s.name.slice(0, 1)}</span>
                          )}
                        </div>
                        <div className="tb-lb-map-panel__body">
                          <h3>{s.name}</h3>
                          <p className="tb-lb-map-panel__loc">
                            {s.locationLabel || s.mapPlaceId || "Lebanon"}
                          </p>
                          <p className="tb-lb-map-panel__meta">
                            {s.productCount} product{s.productCount === 1 ? "" : "s"}
                            {s.categories[0] ? ` · ${s.categories[0]}` : ""}
                            {s.minMoq != null ? ` · MOQ ${s.minMoq}` : ""}
                            {s.avgLeadTime != null ? ` · ~${s.avgLeadTime}d lead` : ""}
                          </p>
                          {s.sampleProducts[0] ? (
                            <p className="tb-lb-map-panel__sample">
                              e.g. {s.sampleProducts[0].name}
                              {s.sampleProducts[0].unitPrice
                                ? ` · from ${s.sampleProducts[0].currency || "USD"} ${s.sampleProducts[0].unitPrice}`
                                : ""}
                            </p>
                          ) : null}
                          <div className="tb-lb-map-panel__actions">
                            <Link href={ROUTES.supplierProfile(s.id)}>View profile →</Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </aside>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
