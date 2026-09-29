import {
  bigint,
  boolean,
  customType,
  date,
  doublePrecision,
  integer,
  jsonb,
  pgMaterializedView,
  pgTable,
  primaryKey,
  real,
  smallint,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

// Mirrors the SQL migrations in drizzle/migrations/. Indexes (GIST, BRIN),
// CHECK constraints, GENERATED columns and the materialized views' queries
// live only in those SQL files. Every column is declared here, including the
// PostGIS ones, so `drizzle-kit generate` (which diffs this file against the
// latest meta snapshot) never proposes adding or dropping one. After a schema
// change, update this file, run `drizzle-kit generate`, and review or rewrite
// the generated SQL (0003_snapshot_postgis.sql replaced it with a no-op);
// tests/unit/drizzle-snapshot.test.ts checks nothing is left to generate.

// PostGIS geometry, read with ST_AsGeoJSON in raw SQL; the ORM never selects it.
const geometry = (kind: "MultiLineString" | "Polygon") =>
  customType<{ data: string; driverData: string }>({
    dataType: () => `geometry(${kind},4326)`,
  });
const multiLineString = geometry("MultiLineString");
const polygon = geometry("Polygon");

export const sensors = pgTable("sensors", {
  id: text("id").primaryKey(),
  displayName: text("display_name").notNull(),
  latitude: doublePrecision("latitude").notNull(),
  longitude: doublePrecision("longitude").notNull(),
  installDate: date("install_date").notNull(),
  active: boolean("active").notNull().default(true),
  configJson: jsonb("config_json").notNull(),
  configVersion: text("config_version").notNull(),
  lastHeartbeat: timestamp("last_heartbeat", { withTimezone: true }),
  fwVersion: text("fw_version"),
  notes: text("notes"),
  apiTokenHash: text("api_token_hash").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const streets = pgTable("streets", {
  id: text("id").primaryKey(),
  displayName: text("display_name").notNull(),
  osmWayIds: bigint("osm_way_ids", { mode: "bigint" }).array().notNull(),
  geom: multiLineString("geom").notNull(),
  bbox: polygon("bbox").notNull(),
  city: text("city").notNull(),
  active: boolean("active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  // OpenStreetMap maxspeed by default; null when unknown (0005_speed_limit.sql).
  speedLimitKmh: smallint("speed_limit_kmh"),
});

export const sensorStreetCoverage = pgTable(
  "sensor_street_coverage",
  {
    sensorId: text("sensor_id")
      .notNull()
      .references(() => sensors.id, { onDelete: "cascade" }),
    streetId: text("street_id")
      .notNull()
      .references(() => streets.id, { onDelete: "restrict" }),
    weight: real("weight").notNull().default(1.0),
  },
  (t) => ({ pk: primaryKey({ columns: [t.sensorId, t.streetId] }) })
);

export const sensorReadings = pgTable(
  "sensor_readings",
  {
    sensorId: text("sensor_id")
      .notNull()
      .references(() => sensors.id, { onDelete: "cascade" }),
    windowStart: timestamp("window_start", { withTimezone: true }).notNull(),
    windowEnd: timestamp("window_end", { withTimezone: true }).notNull(),
    className: text("class_name").notNull(),
    count: integer("count").notNull(),
    directionAbCount: integer("direction_ab_count"),
    directionBaCount: integer("direction_ba_count"),
    avgSpeedKmh: real("avg_speed_kmh"),
    // Timed road users per speed bin (src/lib/privacy.ts), for v85; never public.
    speedHistKmh: integer("speed_hist_kmh").array(),
    partial: boolean("partial").notNull().default(false),
    receivedAt: timestamp("received_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.sensorId, t.windowStart, t.className] }),
  })
);

export const sensorDailyTotals = pgTable(
  "sensor_daily_totals",
  {
    sensorId: text("sensor_id")
      .notNull()
      .references(() => sensors.id, { onDelete: "cascade" }),
    day: date("day").notNull(),
    totalsJson: jsonb("totals_json").notNull(),
    windowCount: integer("window_count").notNull(),
    late: boolean("late").notNull().default(false),
    reconciled: boolean("reconciled").notNull().default(false),
    mismatchJson: jsonb("mismatch_json"),
    receivedAt: timestamp("received_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({ pk: primaryKey({ columns: [t.sensorId, t.day] }) })
);

export const sensorHeartbeats = pgTable(
  "sensor_heartbeats",
  {
    sensorId: text("sensor_id")
      .notNull()
      .references(() => sensors.id, { onDelete: "cascade" }),
    ts: timestamp("ts", { withTimezone: true }).notNull(),
    uptimeS: integer("uptime_s"),
    cpuTempC: real("cpu_temp_c"),
    lastWindowEnd: timestamp("last_window_end", { withTimezone: true }),
    configVersion: text("config_version"),
  },
  (t) => ({ pk: primaryKey({ columns: [t.sensorId, t.ts] }) })
);

// ── Durable rollup tables (retention history store, migration 0001) ──
// Averages are stored as weighted-sum components; avg_speed_kmh is a DB
// GENERATED column (read-only from the ORM's perspective, so it is omitted
// here — the retention job writes total_count / speed_weighted_sum / speed_count).
export const streetHourly = pgTable(
  "street_hourly",
  {
    streetId: text("street_id")
      .notNull()
      .references(() => streets.id, { onDelete: "cascade" }),
    className: text("class_name").notNull(),
    hour: timestamp("hour", { withTimezone: true }).notNull(),
    totalCount: bigint("total_count", { mode: "number" }).notNull().default(0),
    speedWeightedSum: doublePrecision("speed_weighted_sum").notNull().default(0),
    speedCount: bigint("speed_count", { mode: "number" }).notNull().default(0),
    avgSpeedKmh: doublePrecision("avg_speed_kmh"),
  },
  (t) => ({ pk: primaryKey({ columns: [t.streetId, t.className, t.hour] }) })
);

export const streetDaily = pgTable(
  "street_daily",
  {
    streetId: text("street_id")
      .notNull()
      .references(() => streets.id, { onDelete: "cascade" }),
    className: text("class_name").notNull(),
    day: date("day").notNull(),
    totalCount: bigint("total_count", { mode: "number" }).notNull().default(0),
    speedWeightedSum: doublePrecision("speed_weighted_sum").notNull().default(0),
    speedCount: bigint("speed_count", { mode: "number" }).notNull().default(0),
    avgSpeedKmh: doublePrecision("avg_speed_kmh"),
  },
  (t) => ({ pk: primaryKey({ columns: [t.streetId, t.className, t.day] }) })
);

// Cron coordination metadata — gates the piggyback MV refresh (migration 0001).
export const cronMeta = pgTable("cron_meta", {
  job: text("job").primaryKey(),
  lastRunAt: timestamp("last_run_at", { withTimezone: true }).notNull().defaultNow(),
  stats: jsonb("stats"),
});

export const allowedMembers = pgTable("allowed_members", {
  email: text("email").primaryKey(),
  role: text("role").notNull(),
  invitedBy: text("invited_by"),
  invitedAt: timestamp("invited_at", { withTimezone: true }).notNull().defaultNow(),
});

export const allowedDomains = pgTable("allowed_domains", {
  domain: text("domain").primaryKey(),
  defaultRole: text("default_role").notNull(),
});

export const auditLog = pgTable("audit_log", {
  id: bigint("id", { mode: "bigint" }).primaryKey().notNull(),
  actorEmail: text("actor_email").notNull(),
  action: text("action").notNull(),
  targetType: text("target_type").notNull(),
  targetId: text("target_id").notNull(),
  payload: jsonb("payload"),
  ts: timestamp("ts", { withTimezone: true }).notNull().defaultNow(),
});

// Materialized views created by 0001_retention_and_bounded_mv.sql. Declared as
// existing so drizzle-kit leaves them to the SQL migrations.
export const streetReadings15m = pgMaterializedView("street_readings_15m", {
  streetId: text("street_id").notNull(),
  className: text("class_name").notNull(),
  bucket: timestamp("bucket", { withTimezone: true }).notNull(),
  totalCount: bigint("total_count", { mode: "number" }),
  avgSpeedKmh: doublePrecision("avg_speed_kmh"),
}).existing();

export const streetReadingsHourly = pgMaterializedView("street_readings_hourly", {
  streetId: text("street_id").notNull(),
  className: text("class_name").notNull(),
  hour: timestamp("hour", { withTimezone: true }).notNull(),
  totalCount: bigint("total_count", { mode: "number" }),
  avgSpeedKmh: doublePrecision("avg_speed_kmh"),
}).existing();
