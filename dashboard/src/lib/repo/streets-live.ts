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
import { isStale } from "./streets-mock";
import type { StreetsRepo } from "./types";

const K_MIN = 5;
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

function suppress(value: number): number | null {
  return value > 0 && value < K_MIN ? null : value;
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

interface ReadingAggregate {
  bucket: Date;
  class_name: string;
  total_count: string | number;
  speed_sum: string | number | null;
  speed_count: string | number | null;
  ab_count: string | number | null;
  ba_count: string | number | null;
  direction_rows: string | number;
}

interface MetricAggregate {
  street_id: string;
  class_name: string;
  total_count: string | number;
  speed_sum: string | number | null;
  speed_count: string | number | null;
}

export const liveStreetsRepo: StreetsRepo = {
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
      SELECT date_bin(make_interval(mins => ${bucketMinutes}), r.window_start,
                      TIMESTAMPTZ '1970-01-01') AS bucket,
             r.class_name, SUM(r.count) AS total_count,
             SUM(r.avg_speed_kmh * r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL) AS speed_sum,
             SUM(r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL) AS speed_count,
             SUM(r.direction_ab_count) AS ab_count,
             SUM(r.direction_ba_count) AS ba_count,
             COUNT(r.direction_ab_count) AS direction_rows
      FROM sensor_readings r
      JOIN sensor_street_coverage c ON c.sensor_id = r.sensor_id
      WHERE c.street_id = ${streetId}
        AND r.window_start >= ${from.toISOString()} AND r.window_start < ${to.toISOString()}
        ${classFilter(classes)}
      GROUP BY bucket, r.class_name ORDER BY bucket
    `);
    const present = new Map<number, StreetReading>();
    for (const aggregate of rows<ReadingAggregate>(result)) {
      const t = new Date(aggregate.bucket).getTime();
      let row = present.get(t);
      if (!row) {
        row = {
          bucket: new Date(t).toISOString(),
          missing: false,
          counts: emptyCounts(0),
          avgSpeedKmh: {},
        };
        present.set(t, row);
      }
      if (!ROAD_USER_CLASSES.includes(aggregate.class_name as RoadUserClass)) continue;
      const cls = aggregate.class_name as RoadUserClass;
      const count = number(aggregate.total_count);
      const speedCount = number(aggregate.speed_count);
      row.counts[cls] = suppress(count);
      row.avgSpeedKmh[cls] = count >= K_MIN && speedCount >= K_MIN
        ? number(aggregate.speed_sum) / speedCount : null;
      if (number(aggregate.direction_rows) > 0) {
        row.countsByDirection ??= { AB: emptyCounts(null), BA: emptyCounts(null) };
        row.countsByDirection.AB[cls] = suppress(number(aggregate.ab_count));
        row.countsByDirection.BA[cls] = suppress(number(aggregate.ba_count));
      }
    }
    const out: StreetReading[] = [];
    for (let t = Math.floor(from.getTime() / bucketMs) * bucketMs; t < to.getTime(); t += bucketMs) {
      out.push(present.get(t) ?? {
        bucket: new Date(t).toISOString(), missing: true,
        counts: emptyCounts(null), avgSpeedKmh: {},
      });
    }
    return out;
  },

  async latestMetrics({ city, metric, classes, window }) {
    const now = new Date();
    const cutoff = new Date(now.getTime() - WINDOW_MS[window]);
    const streetRows = rows<{ id: string }>(await db().execute(sql`
      SELECT id FROM streets WHERE city = ${city} ORDER BY id
    `));
    const metricRows = classes?.length === 0 ? [] : rows<MetricAggregate>(await db().execute(sql`
      SELECT c.street_id, r.class_name, SUM(r.count) AS total_count,
             SUM(r.avg_speed_kmh * r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL) AS speed_sum,
             SUM(r.count) FILTER (WHERE r.avg_speed_kmh IS NOT NULL) AS speed_count
      FROM sensor_readings r
      JOIN sensor_street_coverage c ON c.sensor_id = r.sensor_id
      JOIN streets s ON s.id = c.street_id
      WHERE s.city = ${city} AND r.window_start >= ${cutoff.toISOString()}
        ${classFilter(classes)}
      GROUP BY c.street_id, r.class_name
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
    const byStreet = new Map<string, MetricAggregate[]>();
    for (const row of metricRows) {
      const group = byStreet.get(row.street_id) ?? [];
      group.push(row);
      byStreet.set(row.street_id, group);
    }
    const lastSeenByStreet = new Map(lastRows.map((row) => [row.street_id, row.last_seen]));
    return streetRows.map(({ id }): MetricValue => {
      const counts = emptyCounts(0);
      const speeds: Partial<Record<RoadUserClass, number | null>> = {};
      let totalCount = 0;
      let speedSum = 0;
      let speedCount = 0;
      for (const aggregate of byStreet.get(id) ?? []) {
        if (!ROAD_USER_CLASSES.includes(aggregate.class_name as RoadUserClass)) continue;
        const cls = aggregate.class_name as RoadUserClass;
        const count = number(aggregate.total_count);
        const speedDen = number(aggregate.speed_count);
        counts[cls] = suppress(count);
        totalCount += count;
        if (count >= K_MIN && speedDen >= K_MIN) {
          speeds[cls] = number(aggregate.speed_sum) / speedDen;
          speedSum += number(aggregate.speed_sum);
          speedCount += speedDen;
        } else {
          speeds[cls] = null;
        }
      }
      const avgSpeedKmh = speedCount >= K_MIN ? speedSum / speedCount : null;
      const seen = lastSeenByStreet.get(id);
      const lastSeen = seen ? new Date(seen).toISOString() : null;
      return {
        streetId: id,
        value: metric === "counts" ? suppress(totalCount) : avgSpeedKmh,
        totalCount: suppress(totalCount),
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
