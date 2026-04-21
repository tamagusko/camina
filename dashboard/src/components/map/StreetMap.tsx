"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type Map as MaplibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { CITY_VIEWS, CIVIDIS_5, VIRIDIS_5, rampExpression } from "@/lib/geo";
import { ROAD_USER_CLASSES, type Metric, type MetricValue, type RoadUserClass, type StreetSummary, type TimeWindow } from "@/lib/types";
import { ClassFilter } from "./ClassFilter";
import { ColourLegend } from "./ColourLegend";
import { MetricToggle } from "./MetricToggle";
import { TimeWindowPicker } from "./TimeWindowPicker";
import { useMapQuery } from "./useMapQuery";

interface Props {
  city: string;
  streets: StreetSummary[];
  initialMetrics: MetricValue[];
  pmtilesUrl?: string;
  onSelectStreet?: (streetId: string) => void;
}

const RAMPS = { counts: VIRIDIS_5, speed: CIVIDIS_5 } as const;
const UNITS = { counts: "/ 15 min", speed: "km/h" } as const;

export function StreetMap({ city, streets, initialMetrics, onSelectStreet }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);

  const [metric, setMetric] = useState<Metric>("counts");
  const [classes, setClasses] = useState<RoadUserClass[]>([...ROAD_USER_CLASSES]);
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("1h");
  const [metrics, setMetrics] = useState<MetricValue[]>(initialMetrics);
  const [mapReady, setMapReady] = useState(false);

  const fallback = useMemo(
    () => CITY_VIEWS[city] ?? { center: [-6.26, 53.35], zoom: 13 },
    [city]
  );
  const { viewport, attachTo } = useMapQuery(fallback);

  // Re-fetch metrics when the user changes filters.
  useEffect(() => {
    const url = new URL("/api/metrics", window.location.origin);
    url.searchParams.set("city", city);
    url.searchParams.set("metric", metric);
    url.searchParams.set("window", timeWindow);
    if (classes.length !== ROAD_USER_CLASSES.length) {
      for (const c of classes) url.searchParams.append("class", c);
    }
    let cancelled = false;
    fetch(url.toString(), { cache: "no-store" })
      .then((r) => r.json())
      .then((data: MetricValue[]) => {
        if (!cancelled) setMetrics(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [city, metric, classes, timeWindow]);

  // Initialise the map on mount.
  useEffect(() => {
    if (!containerRef.current) return;
    // Diagnostic: dump every ancestor's clientHeight so we can spot the
    // element that's collapsing to the wrong height.
    {
      const parts: string[] = [];
      let el: HTMLElement | null = containerRef.current;
      while (el) {
        const tag = el.tagName.toLowerCase();
        const cls = (el.getAttribute("class") ?? "").slice(0, 30);
        parts.push(`${tag}.${cls}:${el.clientHeight}`);
        el = el.parentElement;
      }
      parts.push(`window:${window.innerHeight}`);
      console.info("[CAMINA] ancestor heights:", parts.join(" > "));
    }
    // Minimal OSM basemap (Carto Positron): pure grey/white, no coloured
    // POIs, matches the DESIGN.md monochrome aesthetic. Subdomains a/b/c/d
    // spread tile requests — the default MapLibre raster source uses them in
    // round-robin when multiple URLs are listed.
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            // Local Dublin tiles pre-downloaded by
            // `pnpm exec node scripts/download-dublin-tiles.mjs`
            // into `public/tiles/{z}/{x}/{y}.png` — instant load, no CDN
            // dependency. Re-run the script to refresh or expand coverage.
            tiles: ["/tiles/{z}/{x}/{y}.png"],
            tileSize: 256,
            minzoom: 12,
            maxzoom: 18,
            attribution:
              '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · © <a href="https://carto.com/attributions">CARTO</a>',
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: viewport.center,
      zoom: viewport.zoom,
      minZoom: 12,   // matches the lowest downloaded tile level
      maxZoom: 18,   // matches the highest downloaded tile level
      pitch: 0,
      bearing: 0,
      // Explicit interaction flags — defaults, but pinned here for clarity.
      interactive: true,
      dragPan: true,          // click-and-drag pan
      scrollZoom: true,       // mouse-wheel / trackpad zoom
      doubleClickZoom: true,  // double-click to zoom in
      boxZoom: true,          // shift+drag to zoom to a region
      keyboard: true,         // arrow keys pan, +/- zoom when map focused
      touchZoomRotate: true,
      dragRotate: false,      // keep map flat (no rotate gesture)
      pitchWithRotate: false, // keep map flat (no pitch gesture)
    });
    console.info("[CAMINA] map created; streets incoming:", streets.length);

    // Zoom in (+) / zoom out (-) buttons at bottom-right — classic maps layout.
    map.addControl(
      new maplibregl.NavigationControl({
        visualizePitch: false,
        showCompass: false,
        showZoom: true,
      }),
      "bottom-right"
    );

    map.on("load", () => {
      const fc: GeoJSON.FeatureCollection<GeoJSON.MultiLineString> = {
        type: "FeatureCollection",
        features: streets.map((s) => ({
          type: "Feature",
          id: s.id,
          properties: { street_id: s.id, display_name: s.displayName },
          geometry: s.geom,
        })),
      };
      map.addSource("streets", { type: "geojson", data: fc, promoteId: "street_id" });

      map.addLayer({
        id: "streets-visible",
        type: "line",
        source: "streets",
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": "#afafaf",
          "line-width": 4,
        },
      });

      // Invisible wider hit-box (DESIGN.md §9-bis).
      map.addLayer({
        id: "streets-hit",
        type: "line",
        source: "streets",
        paint: { "line-color": "#000000", "line-opacity": 0, "line-width": 22 },
      });

      map.on("click", "streets-hit", (e) => {
        const id = e.features?.[0]?.properties?.street_id as string | undefined;
        if (id && onSelectStreet) onSelectStreet(id);
      });
      map.on("mouseenter", "streets-hit", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "streets-hit", () => (map.getCanvas().style.cursor = ""));
      // Force a resize in case the container had zero dimensions at init
      // time (can happen during strict-mode double-mount before final layout).
      map.resize();
      setMapReady(true);
      console.info(
        "[CAMINA] map ready; layers:",
        map.getStyle().layers.map((l) => l.id),
        "canvas:",
        map.getCanvas().clientWidth + "×" + map.getCanvas().clientHeight
      );
    });
    map.on("error", (e) => {
      console.error("[CAMINA] map error:", e?.error?.message ?? e);
    });

    mapRef.current = map;
    const detach = attachTo(map);

    // Observe the container so the canvas always matches its real dimensions,
    // even if ancestor layout shifts (DevTools docking, window resize, etc.).
    const ro = new ResizeObserver(() => {
      map.resize();
      const c = map.getCanvas();
      console.info(
        "[CAMINA] container resize → canvas:",
        c.clientWidth + "×" + c.clientHeight
      );
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      setMapReady(false);
      detach();
      map.remove();
      mapRef.current = null;
    };
    // Map init is intentionally one-shot: city + street geometry are fixed
    // per page load. If streets change later, we'd call getSource().setData().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city]);

  // Keep the street source in sync if the parent re-renders with new data.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const src = map.getSource("streets") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: streets.map((s) => ({
        type: "Feature",
        id: s.id,
        properties: { street_id: s.id, display_name: s.displayName },
        geometry: s.geom,
      })),
    });
  }, [streets, mapReady]);

  // Apply the current metric ramp whenever the metrics change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    applyMetricPaint(map, metric, metrics);
  }, [metric, metrics, mapReady]);

  const { min, max } = useMemo(() => rampRangeFor(metrics), [metrics]);

  return (
    <div
      className="relative h-screen w-screen overflow-hidden bg-white"
      style={{ height: "100dvh", width: "100vw" }}
    >
      {/* Inline styles override MapLibre's own .maplibregl-map CSS, which
          would otherwise set position:relative and collapse the height. */}
      <div
        ref={containerRef}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          bottom: 0,
          left: 0,
          width: "100%",
          height: "100%",
        }}
      />

      {/* Top-right control stack (desktop) / single bottom bar collapses on mobile via CSS. */}
      <div className="pointer-events-none absolute inset-0">
        <div className="pointer-events-auto absolute right-3 top-16 hidden flex-col items-end gap-2 md:flex">
          <MetricToggle value={metric} onChange={setMetric} />
          <ClassFilter selected={classes} onChange={setClasses} />
          <TimeWindowPicker value={timeWindow} onChange={setTimeWindow} />
        </div>
        <div className="pointer-events-auto absolute bottom-4 left-1/2 -translate-x-1/2 md:hidden">
          <div className="flex items-center gap-2 rounded-pill bg-white px-2 py-2 shadow-medium">
            <MetricToggle value={metric} onChange={setMetric} />
            <ClassFilter selected={classes} onChange={setClasses} />
            <TimeWindowPicker value={timeWindow} onChange={setTimeWindow} />
          </div>
        </div>

        <div className="pointer-events-auto absolute bottom-4 left-4 hidden md:block">
          <ColourLegend ramp={RAMPS[metric]} min={min} max={max} unit={UNITS[metric]} />
        </div>
      </div>
    </div>
  );
}

function applyMetricPaint(map: MaplibreMap, metric: Metric, metrics: MetricValue[]) {
  for (const m of metrics) {
    map.setFeatureState(
      { source: "streets", id: m.streetId },
      { metric: m.value ?? 0 }
    );
  }
  const { min, max } = rampRangeFor(metrics);
  map.setPaintProperty(
    "streets-visible",
    "line-color",
    rampExpression(RAMPS[metric], min, max) as unknown as maplibregl.ExpressionSpecification
  );
  map.setPaintProperty("streets-visible", "line-width", [
    "interpolate",
    ["linear"],
    ["zoom"],
    10,
    2,
    14,
    4,
    18,
    6,
  ] as unknown as maplibregl.ExpressionSpecification);
}

function rampRangeFor(metrics: MetricValue[]) {
  const values = metrics
    .map((m) => m.value)
    .filter((v): v is number => typeof v === "number");
  if (values.length === 0) return { min: 0, max: 100 };
  return {
    min: Math.min(...values),
    max: Math.max(...values),
  };
}
