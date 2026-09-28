import "server-only";
import { sql, type SQL } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  ROAD_USER_CLASSES,
  type MetricValue,
  type RoadUserClass,
  type StreetAdminInfo,
  type StreetReading,
  type StreetSummary,
  type TimeWindow,
} from "@/lib/types";
import { K_MIN, SPEED_BINS, emptyHistogram, publishedSum, publishedTotal, v85FromHistogram } from "@/lib/privacy";
import { isStaleFor, lastCompletedCellEnd } from "./streets-mock";
import { TYPICAL_WEEKS, typicalTotal, type WindowTotal } from "@/lib/typical";
import { speedResult, type SpeedFold } from "@/lib/speed";
import type { StreetsRepo } from "./types";

const WINDOW_MS: Record<TimeWindow, number> = {
  now: 15 * 60_000,
  "1h": 60 * 60_000,
  "24h": 24 * 60 * 60_000,
  "7d": 7 * 24 * 60 * 60_000,
  "30d": 30 * 24 * 60 * 60_000,
};

function rows<T>(result: unknown): T[] {
  return result as T[];
}

function number(value: string | number | null): number {
  return value === null ? 0 : Number(value);
}

function emptyCounts(value: number | null): Record<RoadUserClass, number | null> {
  return Object.fromEntries(ROAD_USER_CLASSES.map((cls) => [cls, value])) as Record<
    RoadUserClass,
    number | null
  >;
}

function classFilter(classes?: RoadUserClass[]): SQL {
  return classes ? sql`AND r.class_name IN (${sql.join(classes.map((cls) => sql`${cls}`), sql`, `)})` : sql``;
}

interface StreetRow {
  id: string;
  display_name: string;
  geom: GeoJSON.MultiLineString;
  bbox: GeoJSON.Polygon;
  city: string;
  speed_limit_kmh: number | null;
}

function summary(row: StreetRow): StreetSummary {
  return {
    id: row.id,
    displayName: row.display_name,
    geom: row.geom,
    bbox: row.bbox,
    city: row.city,
    speedLimitKmh: row.speed_limit_kmh,
  };
}

// Element-wise sum of speed histograms, one SUM per bin (SQL arrays are 1-based).
// The folded sum leaves the database as JSON: the driver returns a numeric[]
// as its text form.
function histogramSum(column: string, filter = ""): SQL {
  return sql.raw(`ARRAY[${Array.from({ length: SPEED_BINS }, (_, i) =>
    `COALESCE(SUM(${column}[${i + 1}])${filter}, 0)`).join(", ")}]`);
}

// Base cells (street, class, 15-min window) with the within-cell rules of
// src/lib/privacy.ts applied, then summed into the requested bucket or window
// from published cells only (rule 3). `foldCell` is the TypeScript twin.
// `filter` is the JOIN/WHERE tail over sensor_readings r and coverage c.
function publishedCells(filter: SQL): SQL {
  return sql`
    cells AS (
      SELECT c.street_id,
             date_bin(INTERVAL '15 min', r.window_start, TIMESTAMPTZ '1970-01-01') AS cell,
             r.class_name, SUM(r.count) AS n,
             COALESCE(SUM(r.avg_speed_kmh * r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL), 0) AS speed_sum,
             COALESCE(SUM(r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL), 0) AS speed_count,
             ${histogramSum("r.speed_hist_kmh")} AS speed_hist,
             COALESCE(SUM(r.direction_ab_count), 0) AS ab,
             COALESCE(SUM(r.direction_ba_count), 0) AS ba,
             COUNT(r.direction_ab_count) AS direction_rows,
             COUNT(*) AS class_rows
      FROM sensor_readings r
      JOIN sensor_street_coverage c ON c.sensor_id = r.sensor_id
      ${filter}
      GROUP BY 1, 2, 3
    ),
    published AS (
      SELECT *,
             n = 0 OR n >= ${K_MIN} AS count_shown,
             n >= ${K_MIN} AND speed_count >= ${K_MIN} AS speed_shown,
             direction_rows = class_rows
               AND (ab = 0 OR ab >= ${K_MIN}) AND (ba = 0 OR ba >= ${K_MIN}) AS pair_shown
      FROM cells
    )`;
}

// Sums over published cells; the outer query groups them.
const FOLD = sql`
  SUM(n) FILTER (WHERE count_shown) AS total_count,
  BOOL_OR(NOT count_shown) AS hidden,
  SUM(speed_sum) FILTER (WHERE speed_shown) AS speed_sum,
  SUM(speed_count) FILTER (WHERE speed_shown) AS speed_count,
  to_jsonb(${histogramSum("speed_hist", " FILTER (WHERE speed_shown)")}) AS speed_hist,
  SUM(ab) FILTER (WHERE pair_shown) AS ab_count,
  SUM(ba) FILTER (WHERE pair_shown) AS ba_count,
  BOOL_AND(pair_shown) AS pair_shown,
  BOOL_OR(direction_rows > 0) AS directional`;

interface Fold {
  class_name: string;
  total_count: string | number | null;
  hidden: boolean;
  speed_sum: string | number | null;
  speed_count: string | number | null;
  speed_hist: (string | number)[] | null;
  ab_count: string | number | null;
  ba_count: string | number | null;
  pair_shown: boolean;
  directional: boolean;
}

const WEEK_MS = 7 * 24 * 60 * 60_000;

// Per street and week k (0 = the current window, k = the same window k weeks
// back): the published total and the number of 15-min cells with any reading,
// the inputs of src/lib/typical.ts. One query for all weeks.
async function windowTotals(
  city: string,
  classes: RoadUserClass[] | undefined,
  cutoff: Date,
  end: Date,
): Promise<Map<string, WindowTotal[]>> {
  const ranges = Array.from({ length: TYPICAL_WEEKS + 1 }, (_, k) => ({
    k,
    from: new Date(cutoff.getTime() - k * WEEK_MS).toISOString(),
    to: new Date(end.getTime() - k * WEEK_MS).toISOString(),
  }));
  const inRanges = sql.join(
    ranges.map((w) => sql`(r.window_start >= ${w.from} AND r.window_start < ${w.to})`),
    sql` OR `,
  );
  const week = sql`CASE ${sql.join(
    ranges.map((w) => sql`WHEN cell >= ${w.from}::timestamptz AND cell < ${w.to}::timestamptz THEN ${w.k}`),
    sql` `,
  )} END`;
  // Coverage counts cells of any class; the total only the requested classes.
  const requested = classes
    ? sql`AND class_name IN (${sql.join(classes.map((cls) => sql`${cls}`), sql`, `)})`
    : sql``;
  const result = rows<{ street_id: string; week: number; total: string | number | null; cells: string | number }>(
    await db().execute(sql`
      WITH ${publishedCells(sql`
        JOIN streets s ON s.id = c.street_id
        WHERE s.city = ${city} AND (${inRanges})`)}
      SELECT street_id, ${week} AS week,
             COALESCE(SUM(n) FILTER (WHERE count_shown ${requested}), 0) AS total,
             COUNT(DISTINCT cell) AS cells
      FROM published GROUP BY 1, 2
    `),
  );
  const out = new Map<string, WindowTotal[]>();
  for (const row of result) {
    const weeks = out.get(row.street_id) ?? [];
    weeks[Number(row.week)] = { total: number(row.total), cells: number(row.cells) };
    out.set(row.street_id, weeks);
  }
  return out;
}

function speedOf(fold: Fold): number | null {
  const den = number(fold.speed_count);
  return den >= K_MIN ? number(fold.speed_sum) / den : null;
}

function histOf(fold: Fold): number[] {
  return fold.speed_hist ? fold.speed_hist.map(Number) : emptyHistogram();
}

export const liveStreetsRepo: StreetsRepo = {
  async now() {
    // Whole cells only: a wall-clock edge would cut the first bucket short and
    // leave the last one in progress, both painting as offline.
    return lastCompletedCellEnd(new Date());
  },

  async list(city) {
    const result = await db().execute(sql`
      SELECT id, display_name, ST_AsGeoJSON(geom)::jsonb AS geom,
             ST_AsGeoJSON(bbox)::jsonb AS bbox, city, speed_limit_kmh
      FROM streets WHERE city = ${city} AND active = true ORDER BY id
    `);
    return rows<StreetRow>(result).map(summary);
  },

  async get(streetId) {
    const result = await db().execute(sql`
      SELECT id, display_name, ST_AsGeoJSON(geom)::jsonb AS geom,
             ST_AsGeoJSON(bbox)::jsonb AS bbox, city, speed_limit_kmh
      FROM streets WHERE id = ${streetId} LIMIT 1
    `);
    const row = rows<StreetRow>(result)[0];
    return row ? summary(row) : null;
  },

  async readings({ streetId, classes, from, to, bucketMinutes }) {
    if (classes?.length === 0) return [];
    const bucketMs = bucketMinutes * 60_000;
    const result = await db().execute(sql`
      WITH ${publishedCells(sql`
        WHERE c.street_id = ${streetId}
          AND r.window_start >= ${from.toISOString()} AND r.window_start < ${to.toISOString()}
          ${classFilter(classes)}`)}
      SELECT date_bin(make_interval(mins => ${bucketMinutes}), cell,
                      TIMESTAMPTZ '1970-01-01') AS bucket, class_name, ${FOLD}
      FROM published GROUP BY bucket, class_name ORDER BY bucket
    `);
    const folds = rows<Fold & { bucket: Date }>(result);
    if (folds.length === 0) {
      const coverage = rows<{ covered: boolean }>(await db().execute(sql`
        SELECT EXISTS (
          SELECT 1 FROM sensor_street_coverage WHERE street_id = ${streetId}
        ) AS covered
      `));
      if (!coverage[0]?.covered) return [];
    }
    const present = new Map<number, StreetReading>();
    for (const fold of folds) {
      const t = new Date(fold.bucket).getTime();
      const row = present.get(t) ?? {
        bucket: new Date(t).toISOString(),
        missing: false,
        hasHidden: false,
        counts: emptyCounts(0),
        avgSpeedKmh: {},
        v85Kmh: {},
      };
      present.set(t, row);
      if (!ROAD_USER_CLASSES.includes(fold.class_name as RoadUserClass)) continue;
      const cls = fold.class_name as RoadUserClass;
      row.counts[cls] = publishedSum(number(fold.total_count), fold.hidden);
      row.hasHidden ||= fold.hidden;
      row.avgSpeedKmh[cls] = speedOf(fold);
      row.v85Kmh[cls] = v85FromHistogram(histOf(fold));
      if (fold.directional) {
        row.countsByDirection ??= { AB: emptyCounts(0), BA: emptyCounts(0) };
      }
    }
    // Direction cells, once each bucket knows whether it has any.
    for (const fold of folds) {
      const row = present.get(new Date(fold.bucket).getTime());
      if (!row?.countsByDirection) continue;
      if (!ROAD_USER_CLASSES.includes(fold.class_name as RoadUserClass)) continue;
      const cls = fold.class_name as RoadUserClass;
      row.countsByDirection.AB[cls] = fold.pair_shown ? number(fold.ab_count) : null;
      row.countsByDirection.BA[cls] = fold.pair_shown ? number(fold.ba_count) : null;
    }
    const out: StreetReading[] = [];
    for (let t = Math.floor(from.getTime() / bucketMs) * bucketMs; t < to.getTime(); t += bucketMs) {
      out.push(present.get(t) ?? {
        bucket: new Date(t).toISOString(), missing: true, hasHidden: false,
        counts: emptyCounts(null), avgSpeedKmh: {}, v85Kmh: {},
      });
    }
    return out;
  },

  async latestMetrics({ city, metric, classes, window, now = new Date() }) {
    // Whole cells ending at the last completed one (window=now is that cell).
    const end = lastCompletedCellEnd(now);
    const cutoff = new Date(end.getTime() - WINDOW_MS[window]);
    const streetRows = rows<{ id: string }>(await db().execute(sql`
      SELECT id FROM streets WHERE city = ${city} AND active = true ORDER BY id
    `));
    const metricRows = classes?.length === 0 ? [] : rows<Fold & { street_id: string }>(await db().execute(sql`
      WITH ${publishedCells(sql`
        JOIN streets s ON s.id = c.street_id
        WHERE s.city = ${city} AND r.window_start >= ${cutoff.toISOString()}
          AND r.window_start < ${end.toISOString()}
          ${classFilter(classes)}`)}
      SELECT street_id, class_name, ${FOLD}
      FROM published GROUP BY street_id, class_name
    `));
    const lastRows = rows<{ street_id: string; last_seen: Date | null }>(await db().execute(sql`
      SELECT c.street_id, MAX(latest.window_end) AS last_seen
      FROM sensor_street_coverage c
      JOIN streets s ON s.id = c.street_id
      LEFT JOIN LATERAL (
        SELECT window_end FROM sensor_readings r
        WHERE r.sensor_id = c.sensor_id ORDER BY window_start DESC LIMIT 1
      ) latest ON true
      WHERE s.city = ${city}
      GROUP BY c.street_id
    `));
    const weeks = metric === "counts" && WINDOW_MS[window] <= WEEK_MS
      ? await windowTotals(city, classes, cutoff, end)
      : null;
    const byStreet = new Map<string, Fold[]>();
    for (const row of metricRows) {
      const group = byStreet.get(row.street_id) ?? [];
      group.push(row);
      byStreet.set(row.street_id, group);
    }
    const lastSeenByStreet = new Map(lastRows.map((row) => [row.street_id, row.last_seen]));
    return streetRows.map(({ id }): MetricValue => {
      const counts = emptyCounts(0);
      const speeds: Partial<Record<RoadUserClass, number | null>> = {};
      const v85s: Partial<Record<RoadUserClass, number | null>> = {};
      const pooledHist = emptyHistogram();
      let speedSum = 0;
      let speedCount = 0;
      let hasHidden = false;
      for (const fold of byStreet.get(id) ?? []) {
        if (!ROAD_USER_CLASSES.includes(fold.class_name as RoadUserClass)) continue;
        const cls = fold.class_name as RoadUserClass;
        counts[cls] = publishedSum(number(fold.total_count), fold.hidden);
        hasHidden ||= fold.hidden;
        speeds[cls] = speedOf(fold);
        const hist = histOf(fold);
        v85s[cls] = v85FromHistogram(hist);
        if (speeds[cls] !== null) {
          speedSum += number(fold.speed_sum);
          speedCount += number(fold.speed_count);
          hist.forEach((n, bin) => { pooledHist[bin] = (pooledHist[bin] ?? 0) + n; });
        }
      }
      const avgSpeedKmh = speedCount >= K_MIN ? speedSum / speedCount : null;
      const published = publishedTotal(Object.values(counts));
      const seen = lastSeenByStreet.get(id);
      const lastSeen = seen ? new Date(seen).toISOString() : null;
      return {
        streetId: id,
        value: metric === "counts" ? published.total : avgSpeedKmh,
        totalCount: published.total,
        hasHidden: hasHidden || published.hasHidden,
        classBreakdown: counts,
        speedBreakdown: speeds,
        avgSpeedKmh,
        v85Breakdown: v85s,
        v85Kmh: v85FromHistogram(pooledHist),
        stale: isStaleFor(window, lastSeen, now),
        lastSeen,
        typical: weeks
          ? typicalTotal(
              { total: published.total, cells: weeks.get(id)?.[0]?.cells ?? 0 },
              Array.from({ length: TYPICAL_WEEKS }, (_, k) => weeks.get(id)?.[k + 1] ?? { total: 0, cells: 0 }),
            )
          : null,
      };
    });
  },

  async speeds({ streetId, window, focus, limitKmh, now = new Date() }) {
    const end = lastCompletedCellEnd(now);
    const cutoff = new Date(end.getTime() - WINDOW_MS[window]);
    // Published folds per class over the window, and per class and Dublin
    // hour of the day, in one pass (GROUPING SETS).
    const result = rows<Fold & { hour: number | null; whole: number }>(await db().execute(sql`
      WITH ${publishedCells(sql`
        WHERE c.street_id = ${streetId}
          AND r.window_start >= ${cutoff.toISOString()} AND r.window_start < ${end.toISOString()}`)},
      timed AS (
        SELECT *, EXTRACT(HOUR FROM cell AT TIME ZONE 'Europe/Dublin')::int AS hour FROM published
      )
      SELECT class_name, hour, GROUPING(hour) AS whole, ${FOLD}
      FROM timed GROUP BY GROUPING SETS ((class_name), (class_name, hour))
    `));
    const folds: SpeedFold[] = result
      .filter((f) => ROAD_USER_CLASSES.includes(f.class_name as RoadUserClass))
      .map((f) => ({
        cls: f.class_name as RoadUserClass,
        hour: Number(f.whole) === 1 ? null : Number(f.hour),
        hist: histOf(f),
        speedSum: number(f.speed_sum),
        speedCount: number(f.speed_count),
      }));
    return speedResult(folds, focus, limitKmh);
  },

  async adminInfo(streetId) {
    const exists = rows<{ id: string }>(await db().execute(sql`
      SELECT id FROM streets WHERE id = ${streetId} LIMIT 1
    `));
    if (exists.length === 0) return null;
    const result = await db().execute(sql`
      SELECT s.id, s.display_name, s.latitude, s.longitude, s.install_date,
             s.active, s.last_heartbeat, s.fw_version, s.config_version
      FROM sensors s
      JOIN sensor_street_coverage c ON c.sensor_id = s.id
      WHERE c.street_id = ${streetId} ORDER BY s.id
    `);
    const sensorRows = rows<{
      id: string; display_name: string; latitude: number; longitude: number;
      install_date: string | Date; active: boolean; last_heartbeat: Date | null;
      fw_version: string | null; config_version: string;
    }>(result);
    return {
      streetId,
      sensors: sensorRows.map((row) => ({
        id: row.id,
        displayName: row.display_name,
        latitude: row.latitude,
        longitude: row.longitude,
        installDate: row.install_date instanceof Date
          ? row.install_date.toISOString().slice(0, 10) : row.install_date,
        active: row.active,
        lastHeartbeat: row.last_heartbeat?.toISOString() ?? null,
        fwVersion: row.fw_version ?? "",
        configVersion: row.config_version,
      })),
    } satisfies StreetAdminInfo;
  },
};
