// Shared TypeScript types for the dashboard.
// Public surface: no sensor identifiers or GPS coordinates escape these types.

export type Metric = "counts" | "speed";

export const ROAD_USER_CLASSES = [
  "person",
  "cyclist",
  "car",
  "e-scooter",
  "SUV",
  "motorcyclist",
  "bus",
  "delivery_van",
  "truck",
] as const;

export type RoadUserClass = (typeof ROAD_USER_CLASSES)[number];

/** How a class is spelled on every page: "Delivery van", "E-scooter", "SUV". */
export function classLabel(cls: RoadUserClass): string {
  return cls === "SUV" ? cls : cls.replaceAll("_", " ").replace(/^./, (m) => m.toUpperCase());
}

export type TimeWindow = "now" | "1h" | "24h" | "7d" | "30d";

export interface StreetSummary {
  id: string;
  displayName: string;
  geom: GeoJSON.MultiLineString;
  bbox: GeoJSON.Polygon;
  city: string;
}

export interface StreetReading {
  bucket: string;             // ISO timestamp of window start
  missing: boolean;           // true when no data covered this window (sensor down)
  // true when a 15-min cell under this bucket was hidden, so a count here is
  // the sum of the published cells only (src/lib/privacy.ts rule 3).
  hasHidden: boolean;
  counts: Record<RoadUserClass, number | null>;  // null per class when missing
  avgSpeedKmh: Partial<Record<RoadUserClass, number | null>>;
  countsByDirection?: Record<"AB" | "BA", Record<RoadUserClass, number | null>>;
}

export interface MetricValue {
  streetId: string;
  // counts: sum of published class counts;
  // speed: count-weighted mean over classes whose speed is published.
  value: number | null;
  // Sum of the published per-class counts (src/lib/privacy.ts): a lower bound
  // when `hasHidden`, never the true total. For metric "counts", `value`
  // equals this.
  totalCount: number;
  // true when any 15-min cell under the window was hidden below the k-floor.
  hasHidden: boolean;
  // Per-class counts; null marks a value suppressed below the k-floor (1..4).
  // 0 is retained (no counted individual to re-identify).
  classBreakdown: Record<RoadUserClass, number | null>;
  speedBreakdown: Partial<Record<RoadUserClass, number | null>>;
  avgSpeedKmh: number | null;
  // true when the covering sensor has gone silent (no reading for > 2 windows).
  stale: boolean;
  // ISO timestamp of the most recent reading, or null if never seen.
  lastSeen: string | null;
  // Metric "counts" only: the usual published total for this window, from the
  // same window in past weeks (src/lib/typical.ts); null without enough history.
  typical: number | null;
}

/** Admin-only view of a street (includes sensor identifiers and GPS).
 *  Must never be returned from a public API route. */
export interface StreetAdminInfo {
  streetId: string;
  sensors: {
    id: string;
    displayName: string;
    latitude: number;
    longitude: number;
    installDate: string;
    active: boolean;
    lastHeartbeat: string | null;
    fwVersion: string;
    configVersion: string;
  }[];
}
