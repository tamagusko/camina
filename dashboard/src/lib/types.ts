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
  counts: Record<RoadUserClass, number | null>;  // null per class when missing
  avgSpeedKmh: Partial<Record<RoadUserClass, number | null>>;
}

export interface MetricValue {
  streetId: string;
  // null when the aggregate count falls below the k-anonymity floor (1..4).
  value: number | null;
  // True all-class total for the street window, independent of the selected
  // metric. k-floored like `value`: null when the total falls in 1..4.
  totalCount: number | null;
  // Per-class counts; null marks a value suppressed below the k-floor (1..4).
  // 0 is retained (no counted individual to re-identify).
  classBreakdown: Record<RoadUserClass, number | null>;
  speedBreakdown: Partial<Record<RoadUserClass, number | null>>;
  avgSpeedKmh: number | null;
  // true when the covering sensor has gone silent (no reading for > 2 windows).
  stale: boolean;
  // ISO timestamp of the most recent reading, or null if never seen.
  lastSeen: string | null;
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
