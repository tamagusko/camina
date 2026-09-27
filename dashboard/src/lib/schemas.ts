import { z } from "zod";
import { ROAD_USER_CLASSES } from "./types";

export const metricSchema = z.enum(["counts", "speed"]);
export const timeWindowSchema = z.enum(["now", "1h", "24h", "7d", "30d"]);
export const classSchema = z.enum(ROAD_USER_CLASSES);

// Query params for /api/streets/[id]/readings. The response has one row per
// bucket, so the range is bounded by a row cap: 30 days at 15 min, 120 days
// hourly, ~7.9 years daily. Defaults: the hour before `to`, `to` = now.
export const READING_BUCKETS = [15, 60, 1440] as const;
export const MAX_READING_ROWS = 2880;
const DEFAULT_RANGE_MS = 60 * 60_000;

export const readingsQuerySchema = z
  .object({
    metric: metricSchema.default("counts"),
    class: z.array(classSchema).optional(),
    from: z.string().datetime().optional(),
    to: z.string().datetime().optional(),
    bucket: z.coerce
      .number()
      .int()
      .refine((b) => (READING_BUCKETS as readonly number[]).includes(b), {
        message: `bucket must be one of ${READING_BUCKETS.join(", ")}`,
      })
      .default(15),
  })
  .transform((q, ctx) => {
    const to = q.to ? new Date(q.to) : new Date();
    const from = q.from ? new Date(q.from) : new Date(to.getTime() - DEFAULT_RANGE_MS);
    const bucketMs = q.bucket * 60_000;
    if (from.getTime() >= to.getTime()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["from"], message: "from must be before to" });
      return z.NEVER;
    }
    const rows = Math.ceil((to.getTime() - Math.floor(from.getTime() / bucketMs) * bucketMs) / bucketMs);
    if (rows > MAX_READING_ROWS) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["from"],
        message: `range must be at most ${MAX_READING_ROWS} buckets`,
      });
      return z.NEVER;
    }
    return { metric: q.metric, class: q.class, from, to, bucket: q.bucket };
  });

// Query params for /api/metrics.
export const metricsQuerySchema = z.object({
  city: z.string().min(1).max(64).default("dublin"),
  metric: metricSchema.default("counts"),
  window: timeWindowSchema.default("1h"),
  class: z.array(classSchema).optional(),
});

// Ingest POST bodies — mirror camina/io/schemas.py on the device side.
// Wire-format bounds.
const MAX_COUNT = 65535; // uint16 ceiling per class per window/day
const MAX_WINDOW_S = 3600; // windows are 900 s; partials may be shorter, never longer
const MAX_FUTURE_MS = 24 * 60 * 60 * 1000; // clock sanity: reject far-future windows

// Class-keyed records: unknown class keys are rejected; a subset of the nine
// classes is allowed (edge and fixtures omit zero-count classes).
const classCountsSchema = z.record(
  classSchema,
  z.number().int().min(0).max(MAX_COUNT)
);
const classSpeedsSchema = z.record(classSchema, z.number().nonnegative());
const directionCountsSchema = z
  .object({
    AB: classCountsSchema.optional(),
    BA: classCountsSchema.optional(),
  })
  .strict()
  .refine((value) => value.AB !== undefined || value.BA !== undefined, {
    message: "counts_by_direction must contain AB and/or BA",
  });

export const countsPayloadSchema = z
  .object({
    schema_version: z.string(),
    sensor_id: z.string(),
    window_start: z.string().datetime(),
    window_end: z.string().datetime(),
    partial: z.boolean(),
    counts: classCountsSchema,
    counts_by_direction: directionCountsSchema.optional(),
    avg_speed_kmh: classSpeedsSchema.default({}),
    config_version: z.string(),
    fw_version: z.string(),
    produced_at: z.string().datetime(),
  })
  .superRefine((p, ctx) => {
    const start = Date.parse(p.window_start);
    const end = Date.parse(p.window_end);
    if (end <= start) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["window_end"],
        message: "window_end must be after window_start",
      });
    } else if (end - start > MAX_WINDOW_S * 1000) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["window_end"],
        message: `window duration must be <= ${MAX_WINDOW_S} s`,
      });
    }
    if (end - Date.now() > MAX_FUTURE_MS) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["window_end"],
        message: "window must not lie more than 24 h in the future",
      });
    }
    const expectedVersion = p.counts_by_direction ? "1.1" : "1.0";
    if (p.schema_version !== expectedVersion) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["schema_version"],
        message: `schema_version must be ${expectedVersion}`,
      });
    }
    if (p.counts_by_direction) {
      const ab = p.counts_by_direction.AB ?? {};
      const ba = p.counts_by_direction.BA ?? {};
      const classes = new Set([
        ...Object.keys(p.counts),
        ...Object.keys(ab),
        ...Object.keys(ba),
      ]);
      for (const className of classes) {
        const total = p.counts[className as keyof typeof p.counts] ?? 0;
        const directionTotal =
          (ab[className as keyof typeof ab] ?? 0) +
          (ba[className as keyof typeof ba] ?? 0);
        if (directionTotal !== total) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["counts_by_direction", className],
            message: "AB + BA must equal counts for every class",
          });
        }
      }
    }
  });

const utcTimeSchema = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/);

export const sensorConfigResponseSchema = z
  .object({
    config_version: z.string(),
    publish_interval_minutes: z.number().int().min(1).max(1440),
    heartbeat_interval_minutes: z.number().int().min(1).max(60),
    daily_publish_time_utc: utcTimeSchema.default("00:00"),
    detection_zone: z.record(z.string(), z.unknown()).nullable().default(null),
    frame_skip: z.number().int().min(1).max(120),
    min_track_hits: z.number().int().min(1).max(20),
  })
  .strict();

export const dailyPayloadSchema = z.object({
  schema_version: z.string(),
  sensor_id: z.string(),
  // A real calendar date: 2026-02-30 would fail the Postgres date insert (500).
  day: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .refine((day) => {
      const t = Date.parse(`${day}T00:00:00Z`);
      return !Number.isNaN(t) && new Date(t).toISOString().startsWith(day);
    }, {
      message: "day must be a calendar date",
    }),
  totals: classCountsSchema,
  window_count: z.number().int().nonnegative(),
  late: z.boolean().default(false),
  config_version: z.string(),
  fw_version: z.string(),
  produced_at: z.string().datetime(),
});

// Strict: unknown keys are rejected (mirrors extra="forbid" on the edge).
// Phase-3 simulator must not ride this schema for debug fields.
export const heartbeatPayloadSchema = z
  .object({
    sensor_id: z.string(),
    ts: z.string().datetime(),
    uptime_s: z.number().int().nonnegative(),
    cpu_temp_c: z.number().nullable().optional(),
    // Integer bitmask from vcgencmd get_throttled; 0 means healthy, null unavailable.
    throttled: z.number().int().min(0).max(4_294_967_295).nullable().optional(),
    rss_mb: z.number().nonnegative().nullable().optional(),
    last_window_end: z.string().datetime().nullable().optional(),
    config_version: z.string(),
    fw_version: z.string(),
    auth_error: z.boolean().default(false),
    config_error: z.boolean().default(false),
    outbox_depth: z.number().int().nonnegative().optional(),
    outbox_dropped_total: z.number().int().nonnegative().optional(),
  })
  .strict();

export type CountsPayload = z.infer<typeof countsPayloadSchema>;
export type DailyPayload = z.infer<typeof dailyPayloadSchema>;
export type HeartbeatPayload = z.infer<typeof heartbeatPayloadSchema>;
export type SensorConfigResponse = z.infer<typeof sensorConfigResponseSchema>;
