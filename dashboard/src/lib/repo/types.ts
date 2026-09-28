import type { SpeedFocus, SpeedResult } from "@/lib/speed";
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
  /** The instant the public views treat as "now": the end of the last
   *  completed 15-min cell in live, the end of the latest window in the
   *  historical mock data. */
  now(): Promise<Date>;
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
    /** Clock override (tests); defaults to now(). */
    now?: Date;
  }): Promise<MetricValue[]>;
  /** Speeds on one road over a window, against a limit: per class, for the
   *  focus (one class or all motor vehicles) and by hour of the day. */
  speeds(opts: {
    streetId: string;
    window: TimeWindow;
    focus: SpeedFocus;
    limitKmh: number | null;
    /** Clock override (tests); defaults to now(). */
    now?: Date;
  }): Promise<SpeedResult>;
  /** Admin-only: reveals sensor identifiers and GPS for a given street.
   *  Callers must gate this on an admin session. */
  adminInfo(streetId: string): Promise<StreetAdminInfo | null>;
}
