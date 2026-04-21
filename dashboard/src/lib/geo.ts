import type { StreetSummary } from "./types";

// Cividis (speed) and viridis (counts) colour ramps — both colour-blind safe.
// DESIGN.md §9-ter pinned these values until explicitly overridden.
export const VIRIDIS_5 = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"];
export const CIVIDIS_5 = ["#00224e", "#3c456b", "#7c7b78", "#c0ac5d", "#fee838"];

// Default city centres — extend with DESIGN.md-specified locations.
export const CITY_VIEWS: Record<
  string,
  { center: [number, number]; zoom: number }
> = {
  dublin: { center: [-6.2603, 53.3498], zoom: 14 },
};

// Compute bbox union of an array of streets. Useful for `fitBounds`.
export function unionBbox(streets: StreetSummary[]):
  | [[number, number], [number, number]]
  | null {
  if (streets.length === 0) return null;
  let minLon = Infinity,
    minLat = Infinity,
    maxLon = -Infinity,
    maxLat = -Infinity;
  for (const s of streets) {
    for (const ring of s.bbox.coordinates) {
      for (const [lon, lat] of ring) {
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

/** MapLibre paint expression that interpolates a 5-stop ramp by metric value.
 *
 * The feature-state lookup is wrapped in `coalesce` so features that haven't
 * had a numeric state set yet fall back to `min` rather than throwing
 * `Expected value to be of type number, but found null instead.`
 *
 * If `min === max`, the interpolate is degenerate (division by zero in
 * MapLibre's internals). We return a constant colour instead — the middle of
 * the ramp feels right for a uniform dataset.
 */
export function rampExpression(ramp: readonly string[], min: number, max: number) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return ramp[Math.floor(ramp.length / 2)];
  }
  const step = (max - min) / (ramp.length - 1);
  const stops: (number | string)[] = [];
  ramp.forEach((colour, i) => {
    stops.push(min + step * i, colour);
  });
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["to-number", ["feature-state", "metric"]], min],
    ...stops,
  ];
}
