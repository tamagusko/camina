"use client";
import { useCallback, useEffect, useState } from "react";
import type { Map as MaplibreMap } from "maplibre-gl";

// Query-string viewport: `?zoom=14&lat=53.3385&lon=-6.2521`.
// Chosen over the OSM-style hash because named params are more self-documenting
// and easier to link from docs / emails / PRs.
//
// We use `history.replaceState` instead of Next's router so pan/zoom does NOT
// retrigger server rendering. The query only shows up in the address bar and
// in outgoing shareable links.

export interface Viewport {
  zoom: number;
  center: [number, number]; // [lon, lat]
}

const KEYS = { zoom: "zoom", lat: "lat", lon: "lon" } as const;

export function parseSearch(search: string): Viewport | null {
  if (!search) return null;
  const params = new URLSearchParams(search.replace(/^\?/, ""));
  const zoom = Number(params.get(KEYS.zoom));
  const lat = Number(params.get(KEYS.lat));
  const lon = Number(params.get(KEYS.lon));
  if (!Number.isFinite(zoom) || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { zoom, center: [lon, lat] };
}

export function formatSearch(v: Viewport, existing?: string): string {
  const params = new URLSearchParams((existing ?? "").replace(/^\?/, ""));
  params.set(KEYS.zoom, v.zoom.toFixed(1));
  params.set(KEYS.lat, v.center[1].toFixed(4));
  params.set(KEYS.lon, v.center[0].toFixed(4));
  return `?${params.toString()}`;
}

export function useMapQuery(fallback: Viewport) {
  const [viewport, setViewport] = useState<Viewport>(() => {
    if (typeof window === "undefined") return fallback;
    return parseSearch(window.location.search) ?? fallback;
  });

  useEffect(() => {
    function onPopState() {
      const parsed = parseSearch(window.location.search);
      if (parsed) setViewport(parsed);
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const attachTo = useCallback((map: MaplibreMap) => {
    let raf = 0;
    function onMoveEnd() {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const c = map.getCenter();
        const next: Viewport = { zoom: map.getZoom(), center: [c.lng, c.lat] };
        const search = formatSearch(next, window.location.search);
        history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
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
