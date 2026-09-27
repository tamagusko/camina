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
import { K_MIN, publishedSum, publishedTotal } from "@/lib/privacy";
import { isStale } from "./streets-mock";
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
}

function summary(row: StreetRow): StreetSummary {
  return {
    id: row.id,
    displayName: row.display_name,
    geom: row.geom,
    bbox: row.bbox,
    city: row.city,
  };
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
  ab_count: string | number | null;
  ba_count: string | number | null;
  pair_shown: boolean;
  directional: boolean;
}

function speedOf(fold: Fold): number | null {
  const den = number(fold.speed_count);
  return den >= K_MIN ? number(fold.speed_sum) / den : null;
}

export const liveStreetsRepo: StreetsRepo = {
  async now() {
    return new Date();
  },

  async list(city) {
    const result = await db().execute(sql`
      SELECT id, display_name, ST_AsGeoJSON(geom)::jsonb AS geom,
             ST_AsGeoJSON(bbox)::jsonb AS bbox, city
      FROM streets WHERE city = ${city} AND active = true ORDER BY id
    `);
    return rows<StreetRow>(result).map(summary);
  },

  async get(streetId) {
    const result = await db().execute(sql`
      SELECT id, display_name, ST_AsGeoJSON(geom)::jsonb AS geom,
             ST_AsGeoJSON(bbox)::jsonb AS bbox, city
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
      };
      present.set(t, row);
      if (!ROAD_USER_CLASSES.includes(fold.class_name as RoadUserClass)) continue;
      const cls = fold.class_name as RoadUserClass;
      row.counts[cls] = publishedSum(number(fold.total_count), fold.hidden);
      row.hasHidden ||= fold.hidden;
      row.avgSpeedKmh[cls] = speedOf(fold);
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
        counts: emptyCounts(null), avgSpeedKmh: {},
      });
    }
    return out;
  },

  async latestMetrics({ city, metric, classes, window }) {
    const now = new Date();
    const cutoff = new Date(now.getTime() - WINDOW_MS[window]);
    const streetRows = rows<{ id: string }>(await db().execute(sql`
      SELECT id FROM streets WHERE city = ${city} AND active = true ORDER BY id
    `));
    const metricRows = classes?.length === 0 ? [] : rows<Fold & { street_id: string }>(await db().execute(sql`
      WITH ${publishedCells(sql`
        JOIN streets s ON s.id = c.street_id
        WHERE s.city = ${city} AND r.window_start >= ${cutoff.toISOString()}
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
      let speedSum = 0;
      let speedCount = 0;
      let hasHidden = false;
      for (const fold of byStreet.get(id) ?? []) {
        if (!ROAD_USER_CLASSES.includes(fold.class_name as RoadUserClass)) continue;
        const cls = fold.class_name as RoadUserClass;
        counts[cls] = publishedSum(number(fold.total_count), fold.hidden);
        hasHidden ||= fold.hidden;
        speeds[cls] = speedOf(fold);
        if (speeds[cls] !== null) {
          speedSum += number(fold.speed_sum);
          speedCount += number(fold.speed_count);
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
        stale: isStale(lastSeen, now),
        lastSeen,
      };
    });
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
