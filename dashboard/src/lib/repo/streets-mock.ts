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

    const buckets = new Map<number, StreetReading>();
    for (const r of readings) {
      if (!sensorIds.includes(r.sensor_id)) continue;
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      const t = new Date(r.window_start).getTime();
      if (t < fromMs || t >= toMs) continue;
      const bucketStart = Math.floor(t / bucketMs) * bucketMs;
      let row = buckets.get(bucketStart);
      if (!row) {
        row = {
          bucket: new Date(bucketStart).toISOString(),
          counts: emptyBreakdown(),
          avgSpeedKmh: {},
        };
        buckets.set(bucketStart, row);
      }
      row.counts[r.class_name as RoadUserClass] += r.count;
      if (r.avg_speed_kmh !== null) {
        // Count-weighted running mean.
        const prev = row.avgSpeedKmh[r.class_name as RoadUserClass] ?? null;
        const prevCount = prev === null ? 0 : row.counts[r.class_name as RoadUserClass] - r.count;
        const total = prevCount + r.count;
        row.avgSpeedKmh[r.class_name as RoadUserClass] =
          total > 0
            ? ((prev ?? 0) * prevCount + r.avg_speed_kmh * r.count) / total
            : r.avg_speed_kmh;
      }
    }

    return [...buckets.values()].sort((a, b) => a.bucket.localeCompare(b.bucket));
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

    const byStreet = new Map<string, MetricValue>();
    for (const id of citySet) {
      byStreet.set(id, {
        streetId: id,
        value: 0,
        classBreakdown: emptyBreakdown(),
        speedBreakdown: {},
        avgSpeedKmh: null,
      });
    }

    // sensor_id → street_id (multi-coverage supported: one sensor can cover many streets).
    const sensorToStreets = new Map<string, string[]>();
    for (const c of coverage) {
      const list = sensorToStreets.get(c.sensor_id) ?? [];
      list.push(c.street_id);
      sensorToStreets.set(c.sensor_id, list);
    }

    // Count-weighted running aggregates: street-level and per-class speeds.
    const speedNumTotal = new Map<string, number>();
    const speedDenTotal = new Map<string, number>();
    const speedNumCls = new Map<string, Record<string, number>>();
    const speedDenCls = new Map<string, Record<string, number>>();

    for (const r of readings) {
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      if (new Date(r.window_start).getTime() < cutoff) continue;
      for (const streetId of sensorToStreets.get(r.sensor_id) ?? []) {
        const row = byStreet.get(streetId);
        if (!row) continue;
        row.classBreakdown[r.class_name as RoadUserClass] += r.count;
        if (metric === "counts") {
          row.value = (row.value ?? 0) + r.count;
        }
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

    for (const row of byStreet.values()) {
      const denT = speedDenTotal.get(row.streetId) ?? 0;
      row.avgSpeedKmh = denT > 0 ? (speedNumTotal.get(row.streetId) ?? 0) / denT : null;
      if (metric === "speed") row.value = row.avgSpeedKmh;
      const nc = speedNumCls.get(row.streetId) ?? {};
      const dc = speedDenCls.get(row.streetId) ?? {};
      for (const cls of ROAD_USER_CLASSES) {
        const d = dc[cls] ?? 0;
        row.speedBreakdown[cls] = d > 0 ? (nc[cls] ?? 0) / d : null;
      }
    }

    return [...byStreet.values()];
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
