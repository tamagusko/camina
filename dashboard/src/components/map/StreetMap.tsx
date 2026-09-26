"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MaplibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CITY_VIEWS, VIRIDIS_5, initialViewBounds, mapColourValue, rampExpression, streetPaintStatus } from "@/lib/geo";
import { formatDublinUpdated } from "@/lib/format-time";
import type { Metric, MetricValue, RoadUserClass, StreetSummary, TimeWindow } from "@/lib/types";
import { ClassFilter } from "./ClassFilter";
import { ColourLegend } from "./ColourLegend";
import { MetricToggle } from "./MetricToggle";
import { TimeWindowPicker } from "./TimeWindowPicker";
import { useMapQuery, type Viewport } from "./useMapQuery";

const MAPLIBRE_WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";
const BASEMAP = { light: "https://tiles.openfreemap.org/styles/positron", dark: "https://tiles.openfreemap.org/styles/dark" };
interface Shown { rows: MetricValue[]; metric: Metric; timeWindow: TimeWindow; }
interface Props { city: string; streets: StreetSummary[]; initialMetrics: MetricValue[]; onSelectStreet?: (streetId: string) => void; }

export function StreetMap({ city, streets, initialMetrics, onSelectStreet }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const mapViewRef = useRef<Viewport | null>(null);
  const [metric, setMetric] = useState<Metric>("counts");
  const [selectedClass, setSelectedClass] = useState<RoadUserClass | null>(null);
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("now");
  // Rows are kept with the metric and window they were fetched for, so the map
  // never colours old rows by a newly selected window's scale.
  const [shown, setShown] = useState<Shown>({ rows: initialMetrics, metric: "counts", timeWindow: "now" });
  const [mapReady, setMapReady] = useState(false);
  const [streetsOpen, setStreetsOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const fallback = useMemo<Viewport>(() => CITY_VIEWS[city] ?? { center: [-6.26, 53.35], zoom: 13 }, [city]);
  const { viewport, attachTo, pinned } = useMapQuery(fallback);
  const lastSeen = shown.rows.map((m) => m.lastSeen).filter((v): v is string => !!v).sort().at(-1);

  useEffect(() => { if (streetsOpen) listRef.current?.querySelector("button")?.focus(); }, [streetsOpen]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setTheme(media.matches ? "dark" : "light");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const url = new URL("/api/metrics", window.location.origin);
    url.searchParams.set("city", city);
    url.searchParams.set("metric", metric);
    url.searchParams.set("window", timeWindow);
    if (selectedClass) url.searchParams.set("class", selectedClass);
    let cancelled = false;
    const run = () => fetch(url.toString(), { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error("Metrics unavailable"); return r.json() as Promise<MetricValue[]>; }).then((rows) => { if (!cancelled) setShown({ rows, metric, timeWindow }); }).catch(() => {});
    run();
    const refresh = setInterval(run, 5 * 60_000);
    return () => { cancelled = true; clearInterval(refresh); };
  }, [city, metric, selectedClass, timeWindow]);

  useEffect(() => {
    if (!containerRef.current) return;
    maplibregl.setWorkerUrl(MAPLIBRE_WORKER_URL);
    const savedView = mapViewRef.current;
    const map = new maplibregl.Map({ container: containerRef.current, style: BASEMAP[theme], center: savedView?.center ?? viewport.center, zoom: savedView?.zoom ?? viewport.zoom,
      minZoom: 12, maxZoom: 18, pitch: 0, bearing: 0, dragRotate: false, pitchWithRotate: false, attributionControl: false });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: window.innerWidth < 768 }), "bottom-right");
    map.on("load", () => {
      map.addSource("streets", { type: "geojson", data: featureCollection(streets, shown) });
      map.addLayer({ id: "streets-casing", type: "line", source: "streets", filter: ["==", ["get", "status"], "live"], layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": getComputedStyle(document.documentElement).getPropertyValue("--ink-1").trim(), "line-opacity": .85, "line-width": 7 } });
      map.addLayer({ id: "streets-visible", type: "line", source: "streets", filter: ["!=", ["get", "status"], "stale"], layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ["case", ["==", ["get", "status"], "suppressed"], getComputedStyle(document.documentElement).getPropertyValue("--ink-3").trim(), rampExpression(VIRIDIS_5, shown.metric)] as unknown as maplibregl.ExpressionSpecification, "line-width": ["case", ["==", ["get", "status"], "suppressed"], 3, 4] as maplibregl.ExpressionSpecification } });
      map.addLayer({ id: "streets-stale", type: "line", source: "streets", filter: ["==", ["get", "status"], "stale"], layout: { "line-cap": "butt" }, paint: { "line-color": getComputedStyle(document.documentElement).getPropertyValue("--ink-3").trim(), "line-width": 3, "line-dasharray": [2, 2] } });
      map.addLayer({ id: "streets-hit", type: "line", source: "streets", paint: { "line-color": "#000", "line-opacity": 0, "line-width": 22 } });
      map.on("click", "streets-hit", (event) => { const id = event.features?.[0]?.properties?.street_id as string | undefined; if (id) onSelectStreet?.(id); });
      map.on("mouseenter", "streets-hit", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "streets-hit", () => { map.getCanvas().style.cursor = ""; });
      if (!pinned && !mapViewRef.current) { const bounds = initialViewBounds(streets, false); if (bounds) map.fitBounds(bounds, { padding: 64, animate: false, maxZoom: 15 }); }
      map.resize(); setMapReady(true);
    });
    map.on("error", (event) => console.error("Map error:", event.error));
    mapRef.current = map;
    const detach = attachTo(map);
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    return () => { const center = map.getCenter(); mapViewRef.current = { center: [center.lng, center.lat], zoom: map.getZoom() }; observer.disconnect(); detach(); setMapReady(false); map.remove(); mapRef.current = null; };
    // Map reinitializes when the system colour scheme changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, theme]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    (map.getSource("streets") as maplibregl.GeoJSONSource).setData(featureCollection(streets, shown));
    map.setPaintProperty("streets-visible", "line-color", ["case", ["==", ["get", "status"], "suppressed"], getComputedStyle(document.documentElement).getPropertyValue("--ink-3").trim(), rampExpression(VIRIDIS_5, shown.metric)] as unknown as maplibregl.ExpressionSpecification);
  }, [streets, shown, mapReady]);

  return <div className="relative h-[100dvh] w-full overflow-hidden bg-bg">
    <div ref={containerRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
    <div className="pointer-events-none absolute inset-0 z-10">
      <div className="pointer-events-auto absolute left-4 top-4 w-[calc(100%-32px)] rounded-md border border-line bg-surface p-3 shadow-[var(--card-shadow)] md:w-auto md:p-4">
        <div className="flex items-center gap-3"><strong className="text-sm tracking-wide">CAMINA</strong><span className="hidden text-sm text-ink-2 md:inline">Street counts, Dublin</span><span className="text-xs text-ink-2">Updated {lastSeen ? formatDublinUpdated(lastSeen) : "—"}</span><button onClick={() => setStreetsOpen((open) => !open)} aria-expanded={streetsOpen} aria-controls="streets-list" className="ml-auto min-h-11 rounded-sm border border-line px-3 text-sm text-ink-1 md:hidden">Streets</button></div>
        <div className="mt-2 hidden text-sm text-ink-2 md:block">Street counts across Dublin</div>
        <button onClick={() => setStreetsOpen((open) => !open)} aria-expanded={streetsOpen} aria-controls="streets-list" className="mt-2 hidden min-h-11 rounded-sm border border-line px-3 text-sm text-ink-1 hover:opacity-70 md:block">Streets</button>
      </div>
      {streetsOpen && <div ref={listRef} id="streets-list" className="pointer-events-auto absolute left-4 top-32 max-h-[min(52dvh,450px)] w-[min(320px,calc(100%-32px))] overflow-y-auto rounded-md border border-line bg-surface p-2 shadow-[var(--card-shadow)]" role="group" aria-label="Streets">
        {[...streets].sort((a, b) => a.displayName.localeCompare(b.displayName)).map((street) => <button key={street.id} className="block min-h-11 w-full rounded-sm px-3 py-2 text-left text-sm text-ink-1 hover:bg-line" onKeyDown={(event) => { if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); const buttons = [...(listRef.current?.querySelectorAll("button") ?? [])]; const index = buttons.indexOf(event.currentTarget); buttons[(index + (event.key === "ArrowDown" ? 1 : buttons.length - 1)) % buttons.length]?.focus(); } }} onClick={() => { onSelectStreet?.(street.id); setStreetsOpen(false); }}>{street.displayName}</button>)}
      </div>}
      <div className="pointer-events-auto absolute right-4 top-4 hidden w-[250px] rounded-md border border-line bg-surface p-3 shadow-[var(--card-shadow)] md:flex md:flex-col md:gap-2">
        <MetricToggle value={metric} onChange={setMetric} /><ClassFilter selected={selectedClass} onChange={setSelectedClass} /><TimeWindowPicker value={timeWindow} onChange={setTimeWindow} />
      </div>
      <div className="pointer-events-auto absolute bottom-4 left-4 hidden w-[300px] md:block"><ColourLegend metric={metric} timeWindow={timeWindow} /></div>
      <div className="pointer-events-auto absolute bottom-4 left-4 right-4 rounded-md border border-line bg-surface p-2 shadow-[var(--card-shadow)] md:hidden">
        <ColourLegend metric={metric} timeWindow={timeWindow} compact />
        <div className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-2"><MetricToggle value={metric} onChange={setMetric} /><ClassFilter selected={selectedClass} onChange={setSelectedClass} /></div>
        <div className="mt-2 flex justify-center"><TimeWindowPicker value={timeWindow} onChange={setTimeWindow} /></div>
      </div>
    </div>
  </div>;
}

function featureCollection(streets: StreetSummary[], { rows, metric, timeWindow }: Shown): GeoJSON.FeatureCollection<GeoJSON.MultiLineString> {
  const byId = new Map(rows.map((row) => [row.streetId, row]));
  return { type: "FeatureCollection", features: streets.map((street) => {
    const row = byId.get(street.id);
    const status = streetPaintStatus(row);
    return { type: "Feature", id: street.id, geometry: street.geom, properties: { street_id: street.id, status, metric: mapColourValue(row?.value ?? 0, metric, timeWindow) } };
  }) };
}
