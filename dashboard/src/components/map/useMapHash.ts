"use client";
import { useCallback, useEffect, useState } from "react";
import type { Map as MaplibreMap } from "maplibre-gl";

// OSM-style URL hash: `#zoom/lat/lon`, e.g. `#14.5/53.3385/-6.2521`.
// Read on mount; write on map `moveend` (debounced via requestAnimationFrame).

export interface Viewport {
  zoom: number;
  center: [number, number]; // [lon, lat]
}

export function parseHash(hash: string): Viewport | null {
  if (!hash) return null;
  const stripped = hash.replace(/^#/, "");
  const parts = stripped.split("/");
  if (parts.length !== 3) return null;
  const zoom = Number(parts[0]);
  const lat = Number(parts[1]);
  const lon = Number(parts[2]);
  if (!Number.isFinite(zoom) || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { zoom, center: [lon, lat] };
}

export function formatHash(v: Viewport): string {
  const [lon, lat] = v.center;
  return `#${v.zoom.toFixed(1)}/${lat.toFixed(4)}/${lon.toFixed(4)}`;
}

export function useMapHash(fallback: Viewport) {
  const [viewport, setViewport] = useState<Viewport>(() => {
    if (typeof window === "undefined") return fallback;
    return parseHash(window.location.hash) ?? fallback;
  });

  // Sync hash on external navigation changes.
  useEffect(() => {
    function onHashChange() {
      const parsed = parseHash(window.location.hash);
      if (parsed) setViewport(parsed);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const attachTo = useCallback((map: MaplibreMap) => {
    let raf = 0;
    function onMoveEnd() {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const c = map.getCenter();
        const v: Viewport = { zoom: map.getZoom(), center: [c.lng, c.lat] };
        const h = formatHash(v);
        if (window.location.hash !== h) {
          history.replaceState(null, "", `${window.location.pathname}${window.location.search}${h}`);
        }
      });
    }
    map.on("moveend", onMoveEnd);
    return () => {
      cancelAnimationFrame(raf);
      map.off("moveend", onMoveEnd);
    };
  }, []);

  return { viewport, attachTo };
}
