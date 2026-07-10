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
  value: number | null;
  classBreakdown: Record<RoadUserClass, number>;
  speedBreakdown: Partial<Record<RoadUserClass, number | null>>;
  avgSpeedKmh: number | null;
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
