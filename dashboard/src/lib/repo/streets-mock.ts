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
  type MetricValue,
  type RoadUserClass,
  type StreetAdminInfo,
  type StreetReading,
  type StreetSummary,
  type TimeWindow,
} from "@/lib/types";
import {
  K_MIN,
  emptyFold,
  emptyRawCell,
  foldCell,
  publishFold,
  publishedTotal,
  type CellFold,
  type RawCell,
} from "@/lib/privacy";
import { TYPICAL_WEEKS, typicalTotal, type WindowTotal } from "@/lib/typical";
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

// Staleness: a silent sensor (no reading for more than two 15-min windows,
// i.e. > 30 min) must not paint as a quiet street. Exported so the rule is
// unit-testable independently of the fixtures.
export const STALE_AFTER_MS = 2 * 15 * 60_000;

export function isStale(lastSeen: string | null, now: Date): boolean {
  if (lastSeen === null) return true;
  return now.getTime() - new Date(lastSeen).getTime() > STALE_AFTER_MS;
}

const CELL_MS = 15 * 60_000;

/** End of the last completed 15-min cell: the latest window_end <= now. A
 *  sensor publishes the cell [S, S+15) at S+15, so this is the newest cell a
 *  street can have; every window ends here. */
export function lastCompletedCellEnd(now: Date): Date {
  return new Date(Math.floor(now.getTime() / CELL_MS) * CELL_MS);
}

/** Stale for this window: silent for > 2 cells, or — for "now", which is that
 *  one cell — the last completed cell has not arrived (late, not 0). */
export function isStaleFor(window: TimeWindow, lastSeen: string | null, now: Date): boolean {
  if (isStale(lastSeen, now)) return true;
  return window === "now" && new Date(lastSeen!).getTime() < lastCompletedCellEnd(now).getTime();
}

type DirectionalMockReading = MockReading & {
  direction_ab_count?: number | null;
  direction_ba_count?: number | null;
};

// Adds one sensor row to its base cell (street, class, 15-min window); the
// privacy rules run on base cells only (src/lib/privacy.ts).
function addReading(cell: RawCell, r: DirectionalMockReading): void {
  cell.count += r.count;
  cell.rows += 1;
  const ab = r.direction_ab_count;
  const ba = r.direction_ba_count;
  if (ab !== undefined && ab !== null && ba !== undefined && ba !== null) {
    cell.ab += ab;
    cell.ba += ba;
    cell.directionalRows += 1;
  }
  if (r.avg_speed_kmh !== null) {
    cell.speedSum += r.avg_speed_kmh * r.count;
    cell.speedCount += r.count;
  }
}

function cellKey(r: MockReading): string {
  const t = Math.floor(new Date(r.window_start).getTime() / CELL_MS) * CELL_MS;
  return `${t}|${r.class_name}`;
}

function windowCutoff(window: TimeWindow, end: Date): Date {
  const map: Record<TimeWindow, number> = {
    now: 15 * 60_000,
    "1h": 60 * 60_000,
    "24h": 24 * 60 * 60_000,
    "7d": 7 * 24 * 60 * 60_000,
    "30d": 30 * 24 * 60 * 60_000,
  };
  return new Date(end.getTime() - map[window]);
}

const WEEK_MS = 7 * 24 * 60 * 60_000;

// Published total and the number of 15-min cells with any reading, per street,
// over [from, to): the inputs of src/lib/typical.ts. Same rules as the counts.
function windowTotals(
  readings: MockReading[],
  sensorToStreets: Map<string, string[]>,
  streetIds: Set<string>,
  requested: RoadUserClass[],
  from: number,
  to: number,
): Map<string, WindowTotal> {
  const cells = new Map<string, Map<string, RawCell>>();
  const present = new Map<string, Set<number>>();
  for (const r of readings) {
    const start = new Date(r.window_start).getTime();
    if (start < from || start >= to) continue;
    for (const streetId of sensorToStreets.get(r.sensor_id) ?? []) {
      if (!streetIds.has(streetId)) continue;
      const seen = present.get(streetId) ?? new Set<number>();
      present.set(streetId, seen.add(Math.floor(start / CELL_MS) * CELL_MS));
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      const byKey = cells.get(streetId) ?? new Map<string, RawCell>();
      cells.set(streetId, byKey);
      const key = cellKey(r);
      const cell = byKey.get(key) ?? emptyRawCell();
      byKey.set(key, cell);
      addReading(cell, r as DirectionalMockReading);
    }
  }
  const out = new Map<string, WindowTotal>();
  for (const streetId of streetIds) {
    const folds = new Map<string, CellFold>();
    for (const [key, cell] of cells.get(streetId) ?? []) {
      const cls = key.split("|")[1]!;
      const fold = folds.get(cls) ?? emptyFold();
      folds.set(cls, fold);
      foldCell(fold, cell);
    }
    const counts = [...folds.values()].map((fold) => publishFold(fold).count);
    out.set(streetId, { total: publishedTotal(counts).total, cells: present.get(streetId)?.size ?? 0 });
  }
  return out;
}

export const mockStreetsRepo: StreetsRepo = {
  async now(): Promise<Date> {
    return deriveNow(await loadReadings());
  },

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

    const hasDirectionalData = readings.some((reading) => {
      const directional = reading as DirectionalMockReading;
      return sensorIds.includes(reading.sensor_id) &&
        directional.direction_ab_count !== undefined &&
        directional.direction_ba_count !== undefined;
    });

    const requested = classes ?? [...ROAD_USER_CLASSES];
    const fromMs = from.getTime();
    const toMs = to.getTime();
    const bucketMs = bucketMinutes * 60_000;

    // Base cells, summed across the street's sensors.
    const cells = new Map<string, RawCell>();
    for (const r of readings) {
      if (!sensorIds.includes(r.sensor_id)) continue;
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      const t = new Date(r.window_start).getTime();
      if (t < fromMs || t >= toMs) continue;
      const key = cellKey(r);
      const cell = cells.get(key) ?? emptyRawCell();
      cells.set(key, cell);
      addReading(cell, r as DirectionalMockReading);
    }
    // Published base cells, summed into the requested buckets (rule 3).
    const present = new Map<number, Map<RoadUserClass, CellFold>>();
    for (const [key, cell] of cells) {
      const [t, cls] = key.split("|") as [string, RoadUserClass];
      const bucketStart = Math.floor(Number(t) / bucketMs) * bucketMs;
      const folds = present.get(bucketStart) ?? new Map<RoadUserClass, CellFold>();
      present.set(bucketStart, folds);
      const fold = folds.get(cls) ?? emptyFold();
      folds.set(cls, fold);
      foldCell(fold, cell);
    }

    // Gap-fill the full [from, to) grid at the bucket interval. Absent windows
    // are emitted with missing:true and null counts so a downed sensor renders
    // as a visible gap instead of interpolated (fake) traffic.
    const gridStart = Math.floor(fromMs / bucketMs) * bucketMs;
    const out: StreetReading[] = [];
    for (let t = gridStart; t < toMs; t += bucketMs) {
      const folds = present.get(t);
      const bucket = new Date(t).toISOString();
      if (!folds) {
        out.push({
          bucket,
          missing: true,
          hasHidden: false,
          counts: nullBreakdown(),
          countsByDirection: hasDirectionalData
            ? { AB: nullBreakdown(), BA: nullBreakdown() }
            : undefined,
          avgSpeedKmh: {},
        });
        continue;
      }
      const counts = emptyBreakdown() as Record<RoadUserClass, number | null>;
      const AB = emptyBreakdown() as Record<RoadUserClass, number | null>;
      const BA = emptyBreakdown() as Record<RoadUserClass, number | null>;
      let directional = false;
      let hasHidden = false;
      for (const [cls, fold] of folds) {
        const shown = publishFold(fold);
        counts[cls] = shown.count;
        AB[cls] = shown.AB;
        BA[cls] = shown.BA;
        directional ||= fold.directional;
        hasHidden ||= fold.hidden;
      }
      out.push({
        bucket,
        missing: false,
        hasHidden,
        counts,
        countsByDirection: directional ? { AB, BA } : undefined,
        avgSpeedKmh: Object.fromEntries(
          requested.map((cls) => [cls, folds.get(cls) ? publishFold(folds.get(cls)!).speed : null])
        ),
      });
    }
    return out;
  },

  async latestMetrics({ city, metric, classes, window, now: clock }): Promise<MetricValue[]> {
    const [streets, coverage, readings] = await Promise.all([
      loadStreets(),
      loadCoverage(),
      loadReadings(),
    ]);

    // Active streets only, matching list().
    const citySet = new Set(
      streets.filter((s) => s.city === city && s.active).map((s) => s.id)
    );
    const requested = classes ?? [...ROAD_USER_CLASSES];
    const now = clock ?? deriveNow(readings);
    const end = lastCompletedCellEnd(now).getTime();
    const cutoff = windowCutoff(window, new Date(end)).getTime();

    // sensor_id → street_id (multi-coverage supported: one sensor can cover many streets).
    const sensorToStreets = new Map<string, string[]>();
    for (const c of coverage) {
      const list = sensorToStreets.get(c.sensor_id) ?? [];
      list.push(c.street_id);
      sensorToStreets.set(c.sensor_id, list);
    }

    // Base cells per street, summed across the street's sensors.
    const cells = new Map<string, Map<string, RawCell>>();
    for (const id of citySet) cells.set(id, new Map());

    // Most recent window_end per street across ALL readings (not just the
    // selected window): a silent sensor must be detectable even when a short
    // window contains no data at all.
    const lastSeenMs = new Map<string, number>();

    for (const r of readings) {
      const streetsForSensor = sensorToStreets.get(r.sensor_id) ?? [];
      const windowEnd = new Date(r.window_end).getTime();
      for (const streetId of streetsForSensor) {
        if (!citySet.has(streetId)) continue;
        if (windowEnd > (lastSeenMs.get(streetId) ?? 0)) lastSeenMs.set(streetId, windowEnd);
      }
      if (!requested.includes(r.class_name as RoadUserClass)) continue;
      const start = new Date(r.window_start).getTime();
      if (start < cutoff || start >= end) continue;
      for (const streetId of streetsForSensor) {
        const byKey = cells.get(streetId);
        if (!byKey) continue;
        const key = cellKey(r);
        const cell = byKey.get(key) ?? emptyRawCell();
        byKey.set(key, cell);
        addReading(cell, r as DirectionalMockReading);
      }
    }

    // Usual total (counts only): the same window in each of the past weeks.
    const weeks = metric === "counts" && end - cutoff <= WEEK_MS
      ? Array.from({ length: TYPICAL_WEEKS + 1 }, (_, k) =>
          windowTotals(readings, sensorToStreets, citySet, requested, cutoff - k * WEEK_MS, end - k * WEEK_MS))
      : [];

    const out: MetricValue[] = [];
    for (const streetId of citySet) {
      // Published base cells, summed over the window (src/lib/privacy.ts rule 3).
      const folds = new Map<RoadUserClass, CellFold>();
      for (const [key, cell] of cells.get(streetId) ?? []) {
        const cls = key.split("|")[1] as RoadUserClass;
        const fold = folds.get(cls) ?? emptyFold();
        folds.set(cls, fold);
        foldCell(fold, cell);
      }
      const classBreakdown = emptyBreakdown() as Record<RoadUserClass, number | null>;
      const speedBreakdown: Partial<Record<RoadUserClass, number | null>> = {};
      let speedSum = 0;
      let speedCount = 0;
      let hasHidden = false;
      for (const cls of ROAD_USER_CLASSES) {
        const fold = folds.get(cls);
        const shown = fold ? publishFold(fold) : null;
        classBreakdown[cls] = shown ? shown.count : 0;
        speedBreakdown[cls] = shown ? shown.speed : null;
        if (fold && shown?.speed !== null) {
          speedSum += fold.speedSum;
          speedCount += fold.speedCount;
        }
        hasHidden ||= fold?.hidden ?? false;
      }
      const avgSpeedKmh = speedCount >= K_MIN ? speedSum / speedCount : null;
      const published = publishedTotal(Object.values(classBreakdown));
      const seen = lastSeenMs.get(streetId);
      const lastSeen = seen !== undefined ? new Date(seen).toISOString() : null;
      out.push({
        streetId,
        value: metric === "counts" ? published.total : avgSpeedKmh,
        totalCount: published.total,
        hasHidden: hasHidden || published.hasHidden,
        classBreakdown,
        speedBreakdown,
        avgSpeedKmh,
        stale: isStaleFor(window, lastSeen, now),
        lastSeen,
        typical: weeks.length
          ? typicalTotal(
              { total: published.total, cells: weeks[0]!.get(streetId)?.cells ?? 0 },
              weeks.slice(1).map((week) => week.get(streetId) ?? { total: 0, cells: 0 }),
            )
          : null,
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
