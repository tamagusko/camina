import "server-only";
import { and, eq, isNull, lt, or, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import type {
  CountsPayload,
  DailyPayload,
  HeartbeatPayload,
} from "@/lib/schemas";
import {
  sensorDailyTotals,
  sensorHeartbeats,
  sensorReadings,
  sensors,
} from "../../drizzle/schema";

// Live-mode persistence for the ingest routes (H2/H5). The edge publishes
// at-least-once (offline buffer replays), so every write is an idempotent
// upsert on the table's composite primary key.

type Db = ReturnType<typeof db>;

// ── Timestamp skew (H5-adjacent) ───────────────────────────────────
// zod already caps window_end at 24 h in the future; this is the tighter
// server policy. Past bound is generous to accept buffered replays.
const MAX_FUTURE_SKEW_MS = 60 * 1000; // 60 s
const MAX_PAST_SKEW_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export interface SkewRejection {
  status: 422;
  error: string;
}

export function checkTimestampSkew(
  iso: string,
  now: number = Date.now()
): SkewRejection | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return { status: 422, error: "invalid_timestamp" };
  if (t - now > MAX_FUTURE_SKEW_MS) {
    return { status: 422, error: "timestamp_in_future" };
  }
  if (now - t > MAX_PAST_SKEW_MS) {
    return { status: 422, error: "timestamp_too_old" };
  }
  return null;
}

// ── Bounded MV refresh (H14 — piggybacked on ingest) ───────────────
// Vercel Hobby cron is daily-only, so the ~48 h materialized views cannot be
// refreshed sub-daily by Vercel Cron. Instead a successful live upsert
// opportunistically refreshes them, rate-gated so an ingest burst triggers at
// most ~1 refresh per window. A GitHub Actions cron (every 15 min) hits
// /api/cron/refresh-aggregates as a fallback for quiet periods.

// Fixed 64-bit key for pg_try_advisory_xact_lock — distinct from RETENTION_LOCK_KEY.
const MV_REFRESH_LOCK_KEY = 4_270_010_002n;
const MV_REFRESH_JOB = "mv_refresh";
const MV_REFRESH_MIN_INTERVAL_MS = 4 * 60 * 1000; // ≤ ~1 refresh / 4 min

export type MvRefreshOutcome = "refreshed" | "skipped_locked" | "skipped_recent";

/**
 * Pure min-interval gate: refresh only if enough time has elapsed since the
 * last recorded refresh. `null` (never refreshed) always passes.
 */
export function shouldRefreshNow(
  lastRunAt: Date | null,
  now: number = Date.now(),
  minIntervalMs: number = MV_REFRESH_MIN_INTERVAL_MS
): boolean {
  if (lastRunAt === null) return true;
  return now - lastRunAt.getTime() >= minIntervalMs;
}

function firstRow<T>(result: unknown): T | undefined {
  if (Array.isArray(result)) return result[0] as T | undefined;
  const rows = (result as { rows?: unknown[] })?.rows;
  return Array.isArray(rows) ? (rows[0] as T | undefined) : undefined;
}

/**
 * Refresh the bounded public materialized views. Guarded by a transaction-scoped
 * try-lock (never blocks; yields if another refresh is mid-flight) and a
 * min-interval gate tracked in `cron_meta`. Non-concurrent REFRESH is used so it
 * can run inside the lock-holding transaction; the 48 h-bounded views are small
 * enough that the brief read lock is acceptable at TRL-6.
 */
export async function refreshBoundedAggregates(
  database: Db = db(),
  opts: { minIntervalMs?: number; now?: number } = {}
): Promise<MvRefreshOutcome> {
  const minIntervalMs = opts.minIntervalMs ?? MV_REFRESH_MIN_INTERVAL_MS;
  const now = opts.now ?? Date.now();
  return database.transaction(async (tx) => {
    const lockRes = await tx.execute(
      sql`SELECT pg_try_advisory_xact_lock(${MV_REFRESH_LOCK_KEY}) AS locked`
    );
    if (!(firstRow<{ locked: boolean }>(lockRes)?.locked ?? false)) {
      return "skipped_locked";
    }
    const metaRes = await tx.execute(
      sql`SELECT last_run_at FROM cron_meta WHERE job = ${MV_REFRESH_JOB}`
    );
    const lastRunAt = firstRow<{ last_run_at: string | Date }>(metaRes)?.last_run_at;
    const last = lastRunAt ? new Date(lastRunAt) : null;
    if (!shouldRefreshNow(last, now, minIntervalMs)) return "skipped_recent";

    await tx.execute(sql`REFRESH MATERIALIZED VIEW street_readings_15m`);
    await tx.execute(sql`REFRESH MATERIALIZED VIEW street_readings_hourly`);
    await tx.execute(sql`
      INSERT INTO cron_meta (job, last_run_at)
      VALUES (${MV_REFRESH_JOB}, now())
      ON CONFLICT (job) DO UPDATE SET last_run_at = now()
    `);
    return "refreshed";
  });
}

/**
 * Fire-and-forget-safe wrapper for the ingest piggyback. Never throws, so it
 * can never fail the ingest response. Intended to be handed to `waitUntil`.
 */
export async function refreshBoundedAggregatesSafe(): Promise<void> {
  try {
    await refreshBoundedAggregates();
  } catch (err) {
    console.warn(`[ingest] piggyback MV refresh failed (ignored): ${String(err)}`);
  }
}

// ── Counts fan-out + promotion rule (H2) ───────────────────────────
export interface ReadingRow {
  sensorId: string;
  windowStart: Date;
  windowEnd: Date;
  className: string;
  count: number;
  avgSpeedKmh: number | null;
  partial: boolean;
}

/** Fan one counts payload out to one row per reported class. */
export function buildCountsRows(
  payload: CountsPayload,
  sensorId: string
): ReadingRow[] {
  const windowStart = new Date(payload.window_start);
  const windowEnd = new Date(payload.window_end);
  const speeds = payload.avg_speed_kmh as Record<string, number | undefined>;
  const counts = payload.counts as Record<string, number | undefined>;
  return Object.entries(counts).map(([className, count]) => ({
    sensorId,
    windowStart,
    windowEnd,
    className,
    count: count ?? 0,
    avgSpeedKmh: speeds[className] ?? null,
    partial: payload.partial,
  }));
}

/**
 * Partial-promotion rule: a finalized (partial=false) row must never be
 * overwritten by partial=true data. Any other combination overwrites
 * (latest-wins), keeping replays idempotent. Mirrors the SQL `setWhere`.
 */
export function shouldOverwrite(
  existingPartial: boolean,
  incomingPartial: boolean
): boolean {
  return !(existingPartial === false && incomingPartial === true);
}

export async function persistCounts(
  payload: CountsPayload,
  sensorId: string,
  database: Db = db()
): Promise<void> {
  const rows = buildCountsRows(payload, sensorId);
  if (rows.length === 0) return;
  await database
    .insert(sensorReadings)
    .values(rows)
    .onConflictDoUpdate({
      target: [
        sensorReadings.sensorId,
        sensorReadings.windowStart,
        sensorReadings.className,
      ],
      set: {
        windowEnd: sql`excluded.window_end`,
        count: sql`excluded.count`,
        avgSpeedKmh: sql`excluded.avg_speed_kmh`,
        partial: sql`excluded.partial`,
        receivedAt: sql`now()`,
      },
      // Promotion rule: skip the update when the stored row is final and the
      // incoming row is partial. Any other case overwrites (latest-wins).
      setWhere: sql`${sensorReadings.partial} = true OR excluded.partial = false`,
    });
}

// ── Daily totals (idempotent upsert) ───────────────────────────────
export async function persistDaily(
  payload: DailyPayload,
  sensorId: string,
  database: Db = db()
): Promise<void> {
  await database
    .insert(sensorDailyTotals)
    .values({
      sensorId,
      day: payload.day,
      totalsJson: payload.totals,
      windowCount: payload.window_count,
      late: payload.late,
    })
    .onConflictDoUpdate({
      target: [sensorDailyTotals.sensorId, sensorDailyTotals.day],
      // Only refresh the reported fields; reconciled/mismatch_json are owned
      // by the reconciliation cron and must survive a replay.
      set: {
        totalsJson: sql`excluded.totals_json`,
        windowCount: sql`excluded.window_count`,
        late: sql`excluded.late`,
        receivedAt: sql`now()`,
      },
    });
}

// ── Heartbeats (idempotent row + latest-wins sensor pointer) ───────
export async function persistHeartbeat(
  payload: HeartbeatPayload,
  sensorId: string,
  database: Db = db()
): Promise<void> {
  const ts = new Date(payload.ts);
  await database
    .insert(sensorHeartbeats)
    .values({
      sensorId,
      ts,
      uptimeS: payload.uptime_s,
      cpuTempC: payload.cpu_temp_c ?? null,
      lastWindowEnd: payload.last_window_end
        ? new Date(payload.last_window_end)
        : null,
      configVersion: payload.config_version,
    })
    .onConflictDoUpdate({
      target: [sensorHeartbeats.sensorId, sensorHeartbeats.ts],
      set: {
        uptimeS: sql`excluded.uptime_s`,
        cpuTempC: sql`excluded.cpu_temp_c`,
        lastWindowEnd: sql`excluded.last_window_end`,
        configVersion: sql`excluded.config_version`,
      },
    });
  // Latest-wins pointer on the sensor row (keyed by sensor, not by ts).
  await database
    .update(sensors)
    .set({ lastHeartbeat: ts })
    .where(
      and(
        eq(sensors.id, sensorId),
        or(isNull(sensors.lastHeartbeat), lt(sensors.lastHeartbeat, ts))
      )
    );
}

// ── Config read (removes the config-route 501 stub) ────────────────
export async function readSensorConfig(
  sensorId: string,
  database: Db = db()
): Promise<{ config: Record<string, unknown>; config_version: string } | null> {
  const rows = await database
    .select({
      configJson: sensors.configJson,
      configVersion: sensors.configVersion,
    })
    .from(sensors)
    .where(eq(sensors.id, sensorId))
    .limit(1);
  const row = rows[0];
  if (!row) return null;
  return {
    config: row.configJson as Record<string, unknown>,
    config_version: row.configVersion,
  };
}

// ── Per-sensor token lookups (H6) ──────────────────────────────────
export async function getSensorTokenHash(
  sensorId: string,
  database: Db = db()
): Promise<string | null> {
  const rows = await database
    .select({ hash: sensors.apiTokenHash })
    .from(sensors)
    .where(eq(sensors.id, sensorId))
    .limit(1);
  return rows[0]?.hash ?? null;
}

export async function findSensorIdByTokenHash(
  tokenHash: string,
  database: Db = db()
): Promise<string | null> {
  const rows = await database
    .select({ id: sensors.id })
    .from(sensors)
    .where(eq(sensors.apiTokenHash, tokenHash))
    .limit(1);
  return rows[0]?.id ?? null;
}
