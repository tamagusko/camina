// Road analysis: one road against another, or against the city average.
// Built only from published numbers (src/lib/privacy.ts), like every page.
import { ROAD_USER_CLASSES, type MetricValue, type RoadUserClass, type StreetReading } from "./types";

export const ANALYSIS_WINDOWS = ["24h", "7d", "30d"] as const;
export type AnalysisWindow = (typeof ANALYSIS_WINDOWS)[number];
export const WINDOW_LABEL: Record<AnalysisWindow, string> = { "24h": "Last 24 hours", "7d": "Last 7 days", "30d": "Last 30 days" };
export const WINDOW_HOURS: Record<AnalysisWindow, number> = { "24h": 24, "7d": 7 * 24, "30d": 30 * 24 };

/** What one side of a comparison shows: a road, or the city average. */
export interface Side {
  label: string;
  total: number | null;
  perHour: number | null;
  byClass: Record<RoadUserClass, number | null>;
  meanSpeed: number | null; // the selected class only
  v85: number | null; // the selected class only
  v85ByClass: Partial<Record<RoadUserClass, number | null>>;
  profile: (number | null)[]; // road users per hour of the day, 0..23
}

const dublinHour = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Dublin", hour: "2-digit", hourCycle: "h23" });

/** Mean road users per hour of the day (Dublin time) over hourly readings;
 *  offline hours and hidden values are left out. */
export function hourlyProfile(readings: StreetReading[], cls: RoadUserClass | null): (number | null)[] {
  const sums = Array.from({ length: 24 }, () => ({ sum: 0, n: 0 }));
  for (const row of readings) {
    if (row.missing) continue;
    const value = cls ? row.counts[cls] : ROAD_USER_CLASSES.reduce((s, c) => s + (row.counts[c] ?? 0), 0);
    if (value === null) continue;
    const acc = sums[Number(dublinHour.format(new Date(row.bucket)))]!;
    acc.sum += value;
    acc.n += 1;
  }
  return sums.map(({ sum, n }) => (n ? sum / n : null));
}

/** Mean of the non-null values; null when there are none. */
export function mean(values: (number | null | undefined)[]): number | null {
  const shown = values.filter((v): v is number => v !== null && v !== undefined);
  return shown.length ? shown.reduce((s, v) => s + v, 0) / shown.length : null;
}

/** A road had data in the window: something published, or something hidden. */
export function hasData(metric: MetricValue): boolean {
  return metric.totalCount > 0 || metric.hasHidden;
}

export function roadSide(label: string, metric: MetricValue | undefined, cls: RoadUserClass | null, readings: StreetReading[], hours: number): Side {
  const data = metric && hasData(metric) ? metric : undefined;
  return {
    label,
    total: data ? data.totalCount : null,
    perHour: data ? data.totalCount / hours : null,
    byClass: Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, data ? data.classBreakdown[c] : null])) as Record<RoadUserClass, number | null>,
    meanSpeed: data && cls ? data.speedBreakdown[cls] ?? null : null,
    v85: data && cls ? data.v85Breakdown[cls] ?? null : null,
    v85ByClass: data?.v85Breakdown ?? {},
    profile: hourlyProfile(readings, cls),
  };
}

/** The city average: each figure is the mean over the roads with data. */
export function citySide(label: string, metrics: MetricValue[], cls: RoadUserClass | null, profiles: (number | null)[][], hours: number): Side {
  const roads = metrics.filter(hasData);
  const total = mean(roads.map((m) => m.totalCount));
  return {
    label,
    total,
    perHour: total === null ? null : total / hours,
    byClass: Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, mean(roads.map((m) => m.classBreakdown[c]))])) as Record<RoadUserClass, number | null>,
    meanSpeed: cls ? mean(roads.map((m) => m.speedBreakdown[cls])) : null,
    v85: cls ? mean(roads.map((m) => m.v85Breakdown[cls])) : null,
    v85ByClass: Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, mean(roads.map((m) => m.v85Breakdown[c]))])),
    profile: Array.from({ length: 24 }, (_, h) => mean(profiles.map((p) => p[h]))),
  };
}

/** The hour of the day with the most road users, or null. */
export function busiestHour(profile: (number | null)[]): number | null {
  let best: number | null = null;
  profile.forEach((v, h) => { if (v !== null && (best === null || v > profile[best]!)) best = h; });
  return best;
}

/** Relative difference of a against b, as a signed fraction; null when either
 *  is missing or b is 0. */
export function difference(a: number | null, b: number | null): number | null {
  return a === null || b === null || b === 0 ? null : (a - b) / b;
}
