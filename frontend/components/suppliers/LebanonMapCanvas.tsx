"use client";

import {
  LEBANON_VIEW,
  type LebanonMapPlace,
} from "@/lib/suppliers/lebanonGeo";
import type { Map as LeafletMap, Marker } from "leaflet";
import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

export type MapPin = LebanonMapPlace & { count: number };

type Props = {
  pins: MapPin[];
  activePlace: string;
  onSelectPlace: (placeId: string) => void;
  className?: string;
  
  resizeKey?: string | number;
};

export function LebanonMapCanvas({
  pins,
  activePlace,
  onSelectPlace,
  className,
  resizeKey,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const onSelectRef = useRef(onSelectPlace);
  onSelectRef.current = onSelectPlace;
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || mapRef.current) return;

    let cancelled = false;

    async function boot() {
      const L = (await import("leaflet")).default;
      if (cancelled || !hostRef.current || mapRef.current) return;

      const map = L.map(hostRef.current, {
        center: LEBANON_VIEW.center,
        zoom: LEBANON_VIEW.zoom,
        minZoom: LEBANON_VIEW.minZoom,
        maxZoom: LEBANON_VIEW.maxZoom,
        zoomControl: false,
        attributionControl: true,
        scrollWheelZoom: true,
      });

      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
          attribution:
            "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
          maxZoom: 18,
          className: "tb-lb-tiles",
        },
      ).addTo(map);

      L.control.zoom({ position: "bottomleft" }).addTo(map);

      mapRef.current = map;
      setReady(true);
      requestAnimationFrame(() => map.invalidateSize());
    }

    void boot();

    return () => {
      cancelled = true;
      setReady(false);
      markersRef.current = [];
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current) return;

    let cancelled = false;

    async function syncMarkers() {
      const L = (await import("leaflet")).default;
      const map = mapRef.current;
      if (cancelled || !map) return;

      for (const m of markersRef.current) {
        map.removeLayer(m);
      }
      markersRef.current = [];

      for (const pin of pins) {
        const active = activePlace.toLowerCase() === pin.id.toLowerCase();
        const icon = L.divIcon({
          className: `tb-lb-marker ${active ? "is-active" : ""}`,
          html: `<span class="tb-lb-marker__dot"></span><span class="tb-lb-marker__label">${escapeHtml(pin.label)}<em>${pin.count}</em></span>`,
          iconSize: [120, 28],
          iconAnchor: [8, 14],
        });

        const marker = L.marker([pin.lat, pin.lng], {
          icon,
          riseOnHover: true,
          keyboard: true,
          title: `${pin.label} · ${pin.count} suppliers`,
        });
        marker.on("click", () => onSelectRef.current(pin.id));
        marker.addTo(map);
        markersRef.current.push(marker);
      }

      if (pins.length === 1) {
        const only = pins[0]!;
        map.setView([only.lat, only.lng], 9, { animate: true });
      } else if (pins.length > 1) {
        const bounds = L.latLngBounds(
          pins.map((p) => [p.lat, p.lng] as [number, number]),
        );
        map.fitBounds(bounds.pad(0.45), { animate: true, maxZoom: 9 });
      } else {
        map.setView(LEBANON_VIEW.center, LEBANON_VIEW.zoom, { animate: true });
      }

      requestAnimationFrame(() => map.invalidateSize());
    }

    void syncMarkers();
    return () => {
      cancelled = true;
    };
  }, [pins, activePlace, ready]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    const t = window.setTimeout(() => map.invalidateSize(), 120);
    return () => window.clearTimeout(t);
  }, [ready, className, resizeKey]);

  return <div ref={hostRef} className={`tb-lb-leaflet ${className || ""}`} />;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
