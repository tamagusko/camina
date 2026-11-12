// Per-class figures for the street page's class view. Built only from published
// values: a hidden cell (null) is left out, as everywhere else (src/lib/privacy.ts).
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "./types";

export interface ClassSummary {
  total: number;
  peak: { count: number; bucket: string } | null;
  byDirection: { AB: number; BA: number } | null;
  avgSpeedKmh: number | null;
}

export function classSummary(readings: StreetReading[], cls: RoadUserClass): ClassSummary {
  let total = 0;
  let peak: ClassSummary["peak"] = null;
  let byDirection: ClassSummary["byDirection"] = null;
  let speedSum = 0;
  let speedCount = 0;
  for (const r of readings) {
    if (r.missing) continue;
    const count = r.counts[cls];
    if (count !== null) {
      total += count;
      if (!peak || count > peak.count) peak = { count, bucket: r.bucket };
      const speed = r.avgSpeedKmh[cls];
      if (speed != null) {
        speedSum += speed * count;
        speedCount += count;
      }
    }
    if (r.countsByDirection) {
      byDirection ??= { AB: 0, BA: 0 };
      for (const dir of ["AB", "BA"] as const) {
        const cell = r.countsByDirection[dir][cls];
        byDirection[dir] += cell ?? 0;
      }
    }
  }
  return { total, peak, byDirection, avgSpeedKmh: speedCount ? speedSum / speedCount : null };
}

/** Classes with at least one published count above zero, in wire order. */
export function classesWithData(readings: StreetReading[]): RoadUserClass[] {
  return ROAD_USER_CLASSES.filter((cls) => readings.some((r) => !r.missing && (r.counts[cls] ?? 0) > 0));
}
