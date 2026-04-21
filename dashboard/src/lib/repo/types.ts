import type {
  Metric,
  RoadUserClass,
  StreetAdminInfo,
  StreetReading,
  StreetSummary,
  TimeWindow,
  MetricValue,
} from "@/lib/types";

// Repositories abstract "mock" and "live" data sources.
// Both implementations MUST produce identical, privacy-safe shapes.

export interface StreetsRepo {
  list(city: string): Promise<StreetSummary[]>;
  get(streetId: string): Promise<StreetSummary | null>;
  readings(opts: {
    streetId: string;
    classes?: RoadUserClass[];
    from: Date;
    to: Date;
    bucketMinutes: number;
  }): Promise<StreetReading[]>;
  latestMetrics(opts: {
    city: string;
    metric: Metric;
    classes?: RoadUserClass[];
    window: TimeWindow;
  }): Promise<MetricValue[]>;
  /** Admin-only: reveals sensor identifiers and GPS for a given street.
   *  Callers must gate this on an admin session. */
  adminInfo(streetId: string): Promise<StreetAdminInfo | null>;
}
