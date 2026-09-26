import type { MetricValue, StreetSummary } from "./types";

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

export function rampExpression(ramp: readonly string[], metric: "counts" | "speed") {
  const thresholds = metric === "counts" ? [25, 75, 200, 500] : [10, 20, 30, 50];
  return ["step", ["coalesce", ["to-number", ["feature-state", "metric"]], 0], ramp[0],
    ...thresholds.flatMap((threshold, index) => [threshold, ramp[index + 1]])];
}
