import type { Metric, MetricValue, StreetSummary, TimeWindow } from "./types";
import { USUAL_LEVELS } from "./typical";

export const VIRIDIS_5 = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"];

export function streetPaintStatus(row: MetricValue | undefined): "live" | "suppressed" | "stale" {
  if (!row || row.stale || !row.lastSeen) return "stale";
  // Nothing publishable: every non-zero class is hidden below the k-floor.
  if (row.value === null || (row.hasHidden && row.value === 0)) return "suppressed";
  return "live";
}

// Default city centres — extend with DESIGN.md-specified locations.
export const CITY_VIEWS: Record<
  string,
  { center: [number, number]; zoom: number }
> = {
  dublin: { center: [-6.2603, 53.3498], zoom: 14 },
};

// Compute bbox union of an array of streets. Useful for `fitBounds`.
function unionBbox(streets: StreetSummary[]):
  | [[number, number], [number, number]]
  | null {
  if (streets.length === 0) return null;
  let minLon = Infinity,
    minLat = Infinity,
    maxLon = -Infinity,
    maxLat = -Infinity;
  for (const s of streets) {
    for (const ring of s.bbox.coordinates) {
      for (const position of ring) {
        const [lon, lat] = position;
        if (lon === undefined || lat === undefined) continue;
        if (lon < minLon) minLon = lon;
        if (lat < minLat) minLat = lat;
        if (lon > maxLon) maxLon = lon;
        if (lat > maxLat) maxLat = lat;
      }
    }
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

/** Bounds the map should open at, or null to use the city's default view.
 *
 * The street data is what the page is about, so the first view frames it —
 * `CITY_VIEWS` is only a fallback for when there is nothing to frame. A
 * viewport pinned in the URL always wins: that is someone following a shared
 * link to a specific place.
 */
export function initialViewBounds(
  streets: StreetSummary[],
  hasPinnedViewport: boolean
): [[number, number], [number, number]] | null {
  if (hasPinnedViewport) return null;
  return unionBbox(streets);
}

/** Counts under 5 per 15 min — a published 0, or a mean below the first
 *  step — paint `quiet` (the legend's "<5" key), never the 5–24 colour. */
export function rampExpression(ramp: readonly string[], metric: "counts" | "speed", quiet = "#a8a8a8") {
  const thresholds = metric === "counts" ? [25, 75, 200, 500] : [10, 20, 30, 50];
  const input = ["coalesce", ["to-number", ["get", "metric"]], 0];
  const steps = thresholds.flatMap((threshold, index) => [threshold, ramp[index + 1]]);
  return metric === "counts"
    ? ["step", input, quiet, 5, ramp[0], ...steps]
    : ["step", input, ramp[0], ...steps];
}

const BUCKETS_PER_WINDOW: Record<TimeWindow, number> = { now: 1, "1h": 4, "24h": 96, "7d": 672, "30d": 2880 };

/** The value a street is coloured by: counts as the mean per 15 min, so one
 *  legend holds in every window; speed is already an average. */
export function mapColourValue(value: number, metric: Metric, window: TimeWindow): number {
  return metric === "counts" ? value / BUCKETS_PER_WINDOW[window] : value;
}

/** Compass names of the two travel directions (A→B, B→A) along a street's first line. */
export function streetDirections(street: StreetSummary): [string, string] {
  const line = street.geom.coordinates[0];
  const first = line?.[0], last = line?.at(-1);
  if (!first || !last || first[0] === undefined || first[1] === undefined || last[0] === undefined || last[1] === undefined) return ["A", "B"];
  const lat1 = first[1] * Math.PI / 180, lat2 = last[1] * Math.PI / 180;
  const lon = (last[0] - first[0]) * Math.PI / 180;
  const angle = (Math.atan2(Math.sin(lon) * Math.cos(lat2), Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon)) * 180 / Math.PI + 360) % 360;
  if (!Number.isFinite(angle)) return ["A", "B"];
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const index = Math.round(angle / 45) % 8;
  return [names[index]!, names[(index + 4) % 8]!];
}

/** What the map colours streets by: a metric, or the count against its usual. */
export type MapMode = Metric | "usual";

/** Much quieter → much busier (src/lib/typical.ts USUAL_LEVELS): blue for
 *  quieter, the neutral ink for usual, red for busier; no judgement implied. */
export const USUAL_RAMP = ["#2166ac", "#67a9cf", "var(--ink-2)", "#ef8a62", "#b2182b"] as const;

/** Colour by the feature's `level`; a street without one paints `quiet`. */
export function usualExpression(quiet: string, ramp: readonly string[] = USUAL_RAMP) {
  return ["match", ["get", "level"], ...USUAL_LEVELS.flatMap((level, i) => [level, ramp[i]]), quiet];
}

/** How much the other streets fade while one is selected. */
const FADED = 0.25;

/** Line opacity: the selected street keeps `full`, the others fade. */
export function selectionOpacity(selectedId: string | null, full: number) {
  return selectedId ? ["case", ["==", ["get", "street_id"], selectedId], full, full * FADED] : full;
}

/** The middle of a street's extent, [lon, lat], to centre the map on it. */
export function streetCentre(street: StreetSummary): [number, number] {
  const ring = street.bbox.coordinates[0] ?? [];
  const lons = ring.map((p) => p[0]!);
  const lats = ring.map((p) => p[1]!);
  return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}
