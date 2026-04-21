import { z } from "zod";
import { ROAD_USER_CLASSES } from "./types";

export const metricSchema = z.enum(["counts", "speed"]);
export const timeWindowSchema = z.enum(["now", "1h", "24h", "7d", "30d"]);
export const classSchema = z.enum(ROAD_USER_CLASSES);

// Query params for /api/streets/[id]/readings.
export const readingsQuerySchema = z.object({
  metric: metricSchema.default("counts"),
  class: z.array(classSchema).optional(),
  from: z.string().datetime().optional(),
  to: z.string().datetime().optional(),
  bucket: z.coerce.number().int().positive().default(15),
});

// Ingest POST bodies — mirror src/camina/io/schemas.py on the device side.
export const countsPayloadSchema = z.object({
  schema_version: z.string(),
  sensor_id: z.string(),
  window_start: z.string().datetime(),
  window_end: z.string().datetime(),
  partial: z.boolean(),
  counts: z.record(z.string(), z.number().int().nonnegative()),
  avg_speed_kmh: z.record(z.string(), z.number().nonnegative()).default({}),
  config_version: z.string(),
  fw_version: z.string(),
  produced_at: z.string().datetime(),
});

export const dailyPayloadSchema = z.object({
  schema_version: z.string(),
  sensor_id: z.string(),
  day: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  totals: z.record(z.string(), z.number().int().nonnegative()),
  window_count: z.number().int().nonnegative(),
  late: z.boolean().default(false),
  config_version: z.string(),
  fw_version: z.string(),
  produced_at: z.string().datetime(),
});

export const heartbeatPayloadSchema = z.object({
  sensor_id: z.string(),
  ts: z.string().datetime(),
  uptime_s: z.number().int().nonnegative(),
  cpu_temp_c: z.number().nullable().optional(),
  last_window_end: z.string().datetime().nullable().optional(),
  config_version: z.string(),
  fw_version: z.string(),
  auth_error: z.boolean().default(false),
  config_error: z.boolean().default(false),
});

export type ReadingsQuery = z.infer<typeof readingsQuerySchema>;
export type CountsPayload = z.infer<typeof countsPayloadSchema>;
export type DailyPayload = z.infer<typeof dailyPayloadSchema>;
export type HeartbeatPayload = z.infer<typeof heartbeatPayloadSchema>;
