import { sql } from "drizzle-orm";
import { db } from "@/lib/db";

// Retention rollup for raw sensor_readings (audit C1).
//
// Raw rows older than `retentionDays` are rolled up into the durable
// street_hourly / street_daily aggregates and then DELETEd — in bounded,
// single-transaction batches guarded by a transaction-scoped advisory lock so
// overlapping cron invocations never double-process a row.

type Db = ReturnType<typeof db>;

// Arbitrary but fixed 64-bit key for pg_try_advisory_xact_lock. Distinct from
// the MV-refresh lock key in ingest-store.ts.
export const RETENTION_LOCK_KEY = 4_270_010_001n;

export interface RetentionOptions {
  retentionDays?: number;
  batchSize?: number;
  maxBatches?: number;
}

export interface RetentionResult {
  batches: number;
  rowsDeleted: number;
  hourlyUpserts: number;
  dailyUpserts: number;
  /** True if another retention run held the advisory lock and this run yielded. */
  skippedLocked: boolean;
}

interface BatchRow {
  deleted: number;
  hourly_upserts: number;
  daily_upserts: number;
}

/**
 * One retention batch as a single data-modifying CTE statement:
 *   DELETE the oldest `batchSize` expired raw rows (RETURNING them), then
 *   additively upsert their contributions into street_hourly and street_daily.
 * Averages merge exactly because we accumulate weighted-sum components, never a
 * pre-divided mean. The whole statement runs under one snapshot, so each raw
 * row is counted and deleted exactly once.
 */
export function buildRetentionBatchSql(retentionDays: number, batchSize: number) {
  return sql`
    WITH batch AS (
      DELETE FROM sensor_readings
      WHERE ctid IN (
        SELECT ctid FROM sensor_readings
        WHERE window_start < now() - make_interval(days => ${retentionDays})
        ORDER BY window_start
        LIMIT ${batchSize}
      )
      RETURNING sensor_id, window_start, class_name, count, avg_speed_kmh
    ),
    rolled_hourly AS (
      INSERT INTO street_hourly
        (street_id, class_name, hour, total_count, speed_weighted_sum, speed_count)
      SELECT
        c.street_id,
        b.class_name,
        date_trunc('hour', b.window_start),
        SUM(b.count),
        COALESCE(SUM(b.avg_speed_kmh * b.count) FILTER (WHERE b.avg_speed_kmh IS NOT NULL), 0),
        COALESCE(SUM(b.count) FILTER (WHERE b.avg_speed_kmh IS NOT NULL), 0)
      FROM batch b
      JOIN sensor_street_coverage c ON c.sensor_id = b.sensor_id
      GROUP BY c.street_id, b.class_name, date_trunc('hour', b.window_start)
      ON CONFLICT (street_id, class_name, hour) DO UPDATE SET
        total_count        = street_hourly.total_count + EXCLUDED.total_count,
        speed_weighted_sum = street_hourly.speed_weighted_sum + EXCLUDED.speed_weighted_sum,
        speed_count        = street_hourly.speed_count + EXCLUDED.speed_count
      RETURNING 1
    ),
    rolled_daily AS (
      INSERT INTO street_daily
        (street_id, class_name, day, total_count, speed_weighted_sum, speed_count)
      SELECT
        c.street_id,
        b.class_name,
        date_trunc('day', b.window_start)::date,
        SUM(b.count),
        COALESCE(SUM(b.avg_speed_kmh * b.count) FILTER (WHERE b.avg_speed_kmh IS NOT NULL), 0),
        COALESCE(SUM(b.count) FILTER (WHERE b.avg_speed_kmh IS NOT NULL), 0)
      FROM batch b
      JOIN sensor_street_coverage c ON c.sensor_id = b.sensor_id
      GROUP BY c.street_id, b.class_name, date_trunc('day', b.window_start)::date
      ON CONFLICT (street_id, class_name, day) DO UPDATE SET
        total_count        = street_daily.total_count + EXCLUDED.total_count,
        speed_weighted_sum = street_daily.speed_weighted_sum + EXCLUDED.speed_weighted_sum,
        speed_count        = street_daily.speed_count + EXCLUDED.speed_count
      RETURNING 1
    )
    SELECT
      (SELECT count(*) FROM batch)::int         AS deleted,
      (SELECT count(*) FROM rolled_hourly)::int AS hourly_upserts,
      (SELECT count(*) FROM rolled_daily)::int  AS daily_upserts
  `;
}

function firstRow<T>(result: unknown): T | undefined {
  // postgres-js `execute` resolves to an array-like of row objects.
  if (Array.isArray(result)) return result[0] as T | undefined;
  const rows = (result as { rows?: unknown[] })?.rows;
  return Array.isArray(rows) ? (rows[0] as T | undefined) : undefined;
}

/**
 * Run retention as a sequence of bounded batches. Each batch is its own
 * transaction: it takes a transaction-scoped try-lock, and if another run holds
 * it the batch yields (skippedLocked) rather than blocking. The loop stops when
 * a batch drains fewer rows than the batch size (backlog cleared) or when
 * `maxBatches` is reached (bounds work per invocation to avoid function timeouts).
 */
export async function runRetention(
  database: Db = db(),
  opts: RetentionOptions = {}
): Promise<RetentionResult> {
  const retentionDays = opts.retentionDays ?? 90;
  const batchSize = opts.batchSize ?? 5000;
  const maxBatches = opts.maxBatches ?? 50;

  const result: RetentionResult = {
    batches: 0,
    rowsDeleted: 0,
    hourlyUpserts: 0,
    dailyUpserts: 0,
    skippedLocked: false,
  };

  for (let i = 0; i < maxBatches; i++) {
    const batch = await database.transaction(async (tx) => {
      const lockRes = await tx.execute(
        sql`SELECT pg_try_advisory_xact_lock(${RETENTION_LOCK_KEY}) AS locked`
      );
      const locked = firstRow<{ locked: boolean }>(lockRes)?.locked ?? false;
      if (!locked) return null; // another run active — yield this batch

      const rowsRes = await tx.execute(buildRetentionBatchSql(retentionDays, batchSize));
      return (
        firstRow<BatchRow>(rowsRes) ?? {
          deleted: 0,
          hourly_upserts: 0,
          daily_upserts: 0,
        }
      );
    });

    if (batch === null) {
      result.skippedLocked = true;
      break;
    }

    result.batches += 1;
    result.rowsDeleted += batch.deleted;
    result.hourlyUpserts += batch.hourly_upserts;
    result.dailyUpserts += batch.daily_upserts;

    if (batch.deleted < batchSize) break; // backlog drained
  }

  return result;
}
