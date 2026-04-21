import {
  bigint,
  boolean,
  date,
  doublePrecision,
  integer,
  jsonb,
  pgTable,
  primaryKey,
  real,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

// Mirrors plan/02-dashboard-vercel.md §8 (without Timescale / PostGIS specific
// statements, which live in the raw SQL migration at drizzle/migrations/0000_init.sql).

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
  // geom and bbox are PostGIS geometry — declared as unknown here; the raw
  // migration adds the proper GEOMETRY columns.
  city: text("city").notNull(),
  active: boolean("active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
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
    avgSpeedKmh: real("avg_speed_kmh"),
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
    sensorId: text("sensor_id").notNull(),
    ts: timestamp("ts", { withTimezone: true }).notNull(),
    uptimeS: integer("uptime_s"),
    cpuTempC: real("cpu_temp_c"),
    lastWindowEnd: timestamp("last_window_end", { withTimezone: true }),
    configVersion: text("config_version"),
  },
  (t) => ({ pk: primaryKey({ columns: [t.sensorId, t.ts] }) })
);

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
