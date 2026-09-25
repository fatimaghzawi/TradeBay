"use client";

import { LebanonMapCanvas } from "@/components/suppliers/LebanonMapCanvas";
import type { Business } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { LEBANON_MAP_PLACES, resolveLebanonMapPlace } from "@/lib/suppliers/directory";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

type LocatedBusiness = Business & { mapPlaceId: string };

type Props = {
  businesses: Business[];
  truncated?: boolean;
};

export function AdminLebanonMap({ businesses, truncated = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [focusPlace, setFocusPlace] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const located = useMemo(() => {
    const rows: LocatedBusiness[] = [];
    for (const business of businesses) {
      const mapPlaceId = resolveLebanonMapPlace({
        city: business.address?.city,
        governorate: business.address?.governorate,
      });
      if (mapPlaceId) rows.push({ ...business, mapPlaceId });
    }
    return rows;
  }, [businesses]);

  const pins = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of located) {
      counts.set(row.mapPlaceId, (counts.get(row.mapPlaceId) || 0) + 1);
    }
    return LEBANON_MAP_PLACES.filter((place) => (counts.get(place.id) || 0) > 0).map(
      (place) => ({
        ...place,
        count: counts.get(place.id) || 0,
      }),
    );
  }, [located]);

  const visible = useMemo(() => {
    if (!focusPlace) return located;
    const needle = focusPlace.toLowerCase();
    return located.filter((row) => row.mapPlaceId.toLowerCase() === needle);
  }, [focusPlace, located]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [expanded]);

  function selectPlace(id: string) {
    setFocusPlace((current) => (current.toLowerCase() === id.toLowerCase() ? "" : id));
    setExpanded(true);
  }

  function renderMap(mode: "inline" | "overlay") {
    return (
      <div className={`tb-lb-map ${mode === "overlay" ? "is-expanded" : ""}`}>
        <div className="tb-lb-map__stage">
          <LebanonMapCanvas
            pins={pins}
            activePlace={focusPlace}
            onSelectPlace={selectPlace}
            resizeKey={mode}
          />
          <button
            type="button"
            className="tb-lb-map__expand"
            aria-label={expanded ? "Close map" : "Open map"}
            onClick={() => setExpanded((open) => !open)}
          >
            {expanded ? (
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
        {mode === "inline" ? (
          <>
            <button type="button" className="tb-lb-map__cta" onClick={() => setExpanded(true)}>
              Open map
              <span aria-hidden>→</span>
            </button>
            <p className="tb-lb-map__hint">
              {pins.length === 0
                ? "No company addresses on the map yet"
                : focusPlace
                  ? `${visible.length} ${visible.length === 1 ? "company" : "companies"} in ${focusPlace}`
                  : `${located.length} ${located.length === 1 ? "company" : "companies"} plotted${truncated ? " from the latest 100" : ""}`}
            </p>
          </>
        ) : null}
      </div>
    );
  }

  const dialog = expanded ? (
    <div
      className="tb-lb-map-overlay tb-cc-map-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="TradeBay across Lebanon"
    >
      <button
        type="button"
        className="tb-lb-map-overlay__backdrop"
        aria-label="Close map"
        onClick={() => setExpanded(false)}
      />
      <div className="tb-lb-map-overlay__shell has-panel">
        <div className="tb-lb-map-overlay__panel">{renderMap("overlay")}</div>
        <aside className="tb-lb-map-panel" aria-label="Companies on the map">
          <div className="tb-lb-map-panel__head">
            <div>
              <h2>{focusPlace ? `Companies in ${focusPlace}` : "Companies on the map"}</h2>
              <p>
                {visible.length} {visible.length === 1 ? "company" : "companies"} with a known
                Lebanon address
                {truncated ? ". Showing the latest 100." : "."}
              </p>
            </div>
            <button type="button" onClick={() => setExpanded(false)} aria-label="Close">
              ×
            </button>
          </div>
          {pins.length > 0 ? (
            <div className="tb-lb-map-panel__chips">
              <button
                type="button"
                className={!focusPlace ? "is-active" : ""}
                onClick={() => setFocusPlace("")}
              >
                All ({located.length})
              </button>
              {pins.map((pin) => (
                <button
                  key={pin.id}
                  type="button"
                  className={focusPlace.toLowerCase() === pin.id.toLowerCase() ? "is-active" : ""}
                  onClick={() => setFocusPlace(pin.id)}
                >
                  {pin.label} ({pin.count})
                </button>
              ))}
            </div>
          ) : null}
          {visible.length === 0 ? (
            <p className="tb-lb-map-panel__empty">
              No companies with a mapped address yet. Zoom the map or pick another city.
            </p>
          ) : (
            <ul className="tb-lb-map-panel__list">
              {visible.map((business) => {
                const place = business.address?.city || business.address?.governorate || business.mapPlaceId;
                return (
                  <li key={business.id} className="tb-lb-map-panel__card">
                    <div className="tb-lb-map-panel__media" aria-hidden>
                      {(business.name || "?").slice(0, 1)}
                    </div>
                    <div className="tb-lb-map-panel__body">
                      <h3>{business.name}</h3>
                      <p className="tb-lb-map-panel__loc">{place}</p>
                      <p className="tb-lb-map-panel__meta">
                        {business.type || "Business"}
                        {business.verification_status ? ` · ${business.verification_status}` : ""}
                      </p>
                      <div className="tb-lb-map-panel__actions">
                        <Link href={ROUTES.admin.businessDetail(business.id)}>Open company →</Link>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
      </div>
    </div>
  ) : null;

  return (
    <div className="tb-cc-lebanon">
      {expanded ? <div className="tb-lb-map__spacer" aria-hidden /> : renderMap("inline")}
      {mounted && dialog ? createPortal(dialog, document.body) : null}
    </div>
  );
}
