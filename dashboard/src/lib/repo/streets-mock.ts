import "server-only";
import {
  loadCoverage,
  loadReadings,
  loadSensors,
  loadStreets,
  type MockReading,
  type MockStreet,
} from "@/lib/mock-loader";
import {
  ROAD_USER_CLASSES,
  type Metric,
  type MetricValue,
  type RoadUserClass,
  type StreetAdminInfo,
  type StreetReading,
  type StreetSummary,
  type TimeWindow,
} from "@/lib/types";
import type { StreetsRepo } from "./types";

function toSummary(s: MockStreet): StreetSummary {
  return {
    id: s.id,
    displayName: s.display_name,
    geom: s.geom,
    bbox: s.bbox,
    city: s.city,
  };
}

function emptyBreakdown(): Record<RoadUserClass, number> {
  return Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<
    RoadUserClass,
    number
  >;
}

function nullBreakdown(): Record<RoadUserClass, number | null> {
  return Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, null])) as Record<
    RoadUserClass,
    number | null
  >;
}

// k-anonymity floor: a published count identifies K_MIN or more individuals.
// Counts of 1..(K_MIN-1) are re-identifiable, so they are suppressed to null.
// 0 is safe to publish — there is no counted individual to re-identify.
export const K_MIN = 5;

export function suppressCount(n: number | null): number | null {
  if (n === null) return null;
  return n > 0 && n < K_MIN ? null : n;
}

function suppressBreakdown(
  b: Record<RoadUserClass, number>
): Record<RoadUserClass, number | null> {
  return Object.fromEntries(
    ROAD_USER_CLASSES.map((c) => [c, suppressCount(b[c])])
  ) as Record<RoadUserClass, number | null>;
}

// Staleness: a silent sensor (no reading for more than two 15-min windows,
// i.e. > 30 min) must not paint as a quiet street. Exported so the rule is
// unit-testable independently of the fixtures.
export const STALE_AFTER_MS = 2 * 15 * 60_000;

export function isStale(lastSeen: string | null, now: Date): boolean {
  if (lastSeen === null) return true;
  return now.getTime() - new Date(lastSeen).getTime() > STALE_AFTER_MS;
}

// Internal accumulator for windows that have data; counts are non-null while
// aggregating and only widened to `number | null` on the emitted StreetReading.
interface PresentBucket {
  counts: Record<RoadUserClass, number>;
  avgSpeedKmh: Partial<Record<RoadUserClass, number | null>>;
}

function windowCutoff(window: TimeWindow, now: Date): Date {
  const map: Record<TimeWindow, number> = {
    now: 15 * 60_000,
    "1h": 60 * 60_000,
    "24h": 24 * 60 * 60_000,
    "7d": 7 * 24 * 60 * 60_000,
    "30d": 30 * 24 * 60 * 60_000,
  };
  return new Date(now.getTime() - map[window]);
}

export const mockStreetsRepo: StreetsRepo = {
  async list(city: string): Promise<StreetSummary[]> {
    const streets = await loadStreets();
    return streets.filter((s) => s.city === city && s.active).map(toSummary);
  },

  async get(streetId: string): Promise<StreetSummary | null> {
    const streets = await loadStreets();
    const found = streets.find((s) => s.id === streetId);
    return found ? toSummary(found) : null;
  },

  async readings({ streetId, classes, from, to, bucketMinutes }): Promise<StreetReading[]> {
    const [coverage, readings] = await Promise.all([
      loadCoverage(),
      loadReadings(),
    ]);
    const sensorIds = coverage.filter((c) => c.street_id === streetId).map((c) => c.sensor_id);
    if (sensorIds.length === 0) return [];

    const requested = classes ?? [...ROAD_USER_CLASSES];
    const fromMs = from.getTime();
    const toMs = to.getTime();
    const bucketMs = bucketMinutes * 60_000;

    // Accumulate only the windows that actually have data. Counts stay
    // non-null here so the running aggregation type-checks; nullability is
    // applied when the gap-filled grid is emitted below.
    const present = new Map<number, PresentBucket>();
    for (const r of readings) {
      if (!sensorIds.includes(r.sensor_id)) continue;
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      const t = new Date(r.window_start).getTime();
      if (t < fromMs || t >= toMs) continue;
      const bucketStart = Math.floor(t / bucketMs) * bucketMs;
      let row = present.get(bucketStart);
      if (!row) {
        row = { counts: emptyBreakdown(), avgSpeedKmh: {} };
        present.set(bucketStart, row);
      }
      const cls = r.class_name as RoadUserClass;
      row.counts[cls] += r.count;
      if (r.avg_speed_kmh !== null) {
        // Count-weighted running mean.
        const prev = row.avgSpeedKmh[cls] ?? null;
        const prevCount = prev === null ? 0 : row.counts[cls] - r.count;
        const total = prevCount + r.count;
        row.avgSpeedKmh[cls] =
          total > 0
            ? ((prev ?? 0) * prevCount + r.avg_speed_kmh * r.count) / total
            : r.avg_speed_kmh;
      }
    }

    // Gap-fill the full [from, to) grid at the bucket interval. Absent windows
    // are emitted with missing:true and null counts so a downed sensor renders
    // as a visible gap instead of interpolated (fake) traffic.
    const gridStart = Math.floor(fromMs / bucketMs) * bucketMs;
    const out: StreetReading[] = [];
    for (let t = gridStart; t < toMs; t += bucketMs) {
      const row = present.get(t);
      out.push(
        row
          ? {
              bucket: new Date(t).toISOString(),
              missing: false,
              // k-anonymity: null-out per-class counts below the k-floor.
              counts: suppressBreakdown(row.counts),
              avgSpeedKmh: row.avgSpeedKmh,
            }
          : {
              bucket: new Date(t).toISOString(),
              missing: true,
              counts: nullBreakdown(),
              avgSpeedKmh: {},
            }
      );
    }
    return out;
  },

  async latestMetrics({ city, metric, classes, window }): Promise<MetricValue[]> {
    const [streets, coverage, readings] = await Promise.all([
      loadStreets(),
      loadCoverage(),
      loadReadings(),
    ]);

    const citySet = new Set(streets.filter((s) => s.city === city).map((s) => s.id));
    const requested = classes ?? [...ROAD_USER_CLASSES];
    const now = deriveNow(readings);
    const cutoff = windowCutoff(window, now).getTime();

    // sensor_id → street_id (multi-coverage supported: one sensor can cover many streets).
    const sensorToStreets = new Map<string, string[]>();
    for (const c of coverage) {
      const list = sensorToStreets.get(c.sensor_id) ?? [];
      list.push(c.street_id);
      sensorToStreets.set(c.sensor_id, list);
    }

    // Numeric accumulators kept non-null while aggregating; k-anonymity
    // suppression is applied only on emit so partial sums stay correct.
    const rawBreakdown = new Map<string, Record<RoadUserClass, number>>();
    const rawTotal = new Map<string, number>();
    const speedNumTotal = new Map<string, number>();
    const speedDenTotal = new Map<string, number>();
    const speedNumCls = new Map<string, Record<string, number>>();
    const speedDenCls = new Map<string, Record<string, number>>();
    for (const id of citySet) rawBreakdown.set(id, emptyBreakdown());

    // Most recent window_end per street across ALL readings (not just the
    // selected window): a silent sensor must be detectable even when a short
    // window contains no data at all.
    const lastSeenMs = new Map<string, number>();

    for (const r of readings) {
      const streetsForSensor = sensorToStreets.get(r.sensor_id) ?? [];
      const end = new Date(r.window_end).getTime();
      for (const streetId of streetsForSensor) {
        if (!citySet.has(streetId)) continue;
        if (end > (lastSeenMs.get(streetId) ?? 0)) lastSeenMs.set(streetId, end);
      }
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      if (new Date(r.window_start).getTime() < cutoff) continue;
      for (const streetId of streetsForSensor) {
        const rb = rawBreakdown.get(streetId);
        if (!rb) continue;
        rb[r.class_name as RoadUserClass] += r.count;
        rawTotal.set(streetId, (rawTotal.get(streetId) ?? 0) + r.count);
        if (r.avg_speed_kmh !== null) {
          speedNumTotal.set(streetId, (speedNumTotal.get(streetId) ?? 0) + r.avg_speed_kmh * r.count);
          speedDenTotal.set(streetId, (speedDenTotal.get(streetId) ?? 0) + r.count);
          const nc = speedNumCls.get(streetId) ?? {};
          const dc = speedDenCls.get(streetId) ?? {};
          nc[r.class_name] = (nc[r.class_name] ?? 0) + r.avg_speed_kmh * r.count;
          dc[r.class_name] = (dc[r.class_name] ?? 0) + r.count;
          speedNumCls.set(streetId, nc);
          speedDenCls.set(streetId, dc);
        }
      }
    }

    const out: MetricValue[] = [];
    for (const streetId of citySet) {
      const denT = speedDenTotal.get(streetId) ?? 0;
      const avgSpeedKmh = denT > 0 ? (speedNumTotal.get(streetId) ?? 0) / denT : null;
      const nc = speedNumCls.get(streetId) ?? {};
      const dc = speedDenCls.get(streetId) ?? {};
      const speedBreakdown: Partial<Record<RoadUserClass, number | null>> = {};
      for (const cls of ROAD_USER_CLASSES) {
        const d = dc[cls] ?? 0;
        speedBreakdown[cls] = d > 0 ? (nc[cls] ?? 0) / d : null;
      }
      const seen = lastSeenMs.get(streetId);
      const lastSeen = seen !== undefined ? new Date(seen).toISOString() : null;
      out.push({
        streetId,
        // k-anonymity: suppress the street total only when metric === counts.
        value:
          metric === "counts"
            ? suppressCount(rawTotal.get(streetId) ?? 0)
            : avgSpeedKmh,
        classBreakdown: suppressBreakdown(rawBreakdown.get(streetId) ?? emptyBreakdown()),
        speedBreakdown,
        avgSpeedKmh,
        stale: isStale(lastSeen, now),
        lastSeen,
      });
    }

    return out;
  },

  async adminInfo(streetId: string): Promise<StreetAdminInfo | null> {
    const [streets, sensors, coverage] = await Promise.all([
      loadStreets(),
      loadSensors(),
      loadCoverage(),
    ]);
    const street = streets.find((s) => s.id === streetId);
    if (!street) return null;
    const sensorIds = coverage
      .filter((c) => c.street_id === streetId)
      .map((c) => c.sensor_id);
    const matched = sensors.filter((s) => sensorIds.includes(s.id));
    return {
      streetId,
      sensors: matched.map((s) => ({
        id: s.id,
        displayName: s.display_name,
        latitude: s.latitude,
        longitude: s.longitude,
        installDate: s.install_date,
        active: s.active,
        lastHeartbeat: s.last_heartbeat,
        fwVersion: s.fw_version,
        configVersion: s.config_version,
      })),
    };
  },
};

function deriveNow(readings: MockReading[]): Date {
  // Mock dataset is historical; "now" = most recent window in data so the
  // dashboard has something to show in dev mode.
  let maxTs = 0;
  for (const r of readings) {
    const t = new Date(r.window_end).getTime();
    if (t > maxTs) maxTs = t;
  }
  return new Date(maxTs);
}
