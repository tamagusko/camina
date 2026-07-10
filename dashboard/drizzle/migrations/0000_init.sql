-- CAMINA dashboard schema — mirrors plan/02-dashboard-vercel.md §8.
-- Runs on Neon Postgres with the PostGIS extension enabled.
-- TimescaleDB is intentionally NOT required — materialized views refreshed
-- by Vercel Cron cover our workload at TRL 5-8 scale.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ── Admin-only ─────────────────────────────────────────────────────
CREATE TABLE sensors (
  id                TEXT PRIMARY KEY,
  display_name      TEXT NOT NULL,
  latitude          DOUBLE PRECISION NOT NULL,
  longitude         DOUBLE PRECISION NOT NULL,
  install_date      DATE NOT NULL,
  active            BOOLEAN NOT NULL DEFAULT TRUE,
  config_json       JSONB NOT NULL,
  config_version    TEXT NOT NULL,
  last_heartbeat    TIMESTAMPTZ,
  fw_version        TEXT,
  notes             TEXT,
  api_token_hash    TEXT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE streets (
  id                TEXT PRIMARY KEY,
  display_name      TEXT NOT NULL,
  osm_way_ids       BIGINT[] NOT NULL,
  geom              GEOMETRY(MultiLineString, 4326) NOT NULL,
  bbox              GEOMETRY(Polygon, 4326) NOT NULL,
  city              TEXT NOT NULL,
  active            BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_streets_geom ON streets USING GIST (geom);
CREATE INDEX idx_streets_bbox ON streets USING GIST (bbox);
CREATE INDEX idx_streets_city_active ON streets (city, active);

CREATE TABLE sensor_street_coverage (
  sensor_id   TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  street_id   TEXT NOT NULL REFERENCES streets(id) ON DELETE RESTRICT,
  weight      REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (sensor_id, street_id)
);
CREATE INDEX idx_coverage_street ON sensor_street_coverage (street_id);

-- ── Readings (partitioned) ─────────────────────────────────────────
CREATE TABLE sensor_readings (
  sensor_id         TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  window_start      TIMESTAMPTZ NOT NULL,
  window_end        TIMESTAMPTZ NOT NULL,
  class_name        TEXT NOT NULL,
  count             INTEGER NOT NULL,
  avg_speed_kmh     REAL,
  partial           BOOLEAN NOT NULL DEFAULT FALSE,
  received_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sensor_id, window_start, class_name)
);
CREATE INDEX idx_readings_window_start ON sensor_readings USING BRIN (window_start);

CREATE TABLE sensor_daily_totals (
  sensor_id     TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  day           DATE NOT NULL,
  totals_json   JSONB NOT NULL,
  window_count  INTEGER NOT NULL,
  late          BOOLEAN NOT NULL DEFAULT FALSE,
  reconciled    BOOLEAN NOT NULL DEFAULT FALSE,
  mismatch_json JSONB,
  received_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sensor_id, day)
);

CREATE TABLE sensor_heartbeats (
  sensor_id        TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  ts               TIMESTAMPTZ NOT NULL,
  uptime_s         INTEGER,
  cpu_temp_c       REAL,
  last_window_end  TIMESTAMPTZ,
  config_version   TEXT,
  PRIMARY KEY (sensor_id, ts)
);

-- ── Public aggregates ──────────────────────────────────────────────
CREATE MATERIALIZED VIEW street_readings_15m AS
SELECT
  c.street_id,
  r.class_name,
  date_trunc('minute',
             r.window_start - (EXTRACT(MINUTE FROM r.window_start)::int % 15) * INTERVAL '1 minute'
             ) AS bucket,
  SUM(r.count) AS total_count,
  CASE WHEN SUM(r.count) > 0
       THEN SUM(r.avg_speed_kmh * r.count) / NULLIF(SUM(r.count), 0)
       ELSE NULL END AS avg_speed_kmh
FROM sensor_readings r
JOIN sensor_street_coverage c ON c.sensor_id = r.sensor_id
GROUP BY c.street_id, r.class_name, bucket;
CREATE UNIQUE INDEX uidx_street_15m ON street_readings_15m (street_id, class_name, bucket);

CREATE MATERIALIZED VIEW street_readings_hourly AS
SELECT street_id, class_name,
       date_trunc('hour', bucket) AS hour,
       SUM(total_count) AS total_count,
       AVG(avg_speed_kmh) AS avg_speed_kmh
FROM street_readings_15m
GROUP BY street_id, class_name, date_trunc('hour', bucket);
CREATE UNIQUE INDEX uidx_street_hour ON street_readings_hourly (street_id, class_name, hour);

-- ── Auth + audit ───────────────────────────────────────────────────
CREATE TABLE allowed_members (
  email         TEXT PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('admin','viewer')),
  invited_by    TEXT,
  invited_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE allowed_domains (
  domain        TEXT PRIMARY KEY,
  default_role  TEXT NOT NULL CHECK (default_role IN ('admin','viewer'))
);

CREATE TABLE audit_log (
  id          BIGSERIAL PRIMARY KEY,
  actor_email TEXT NOT NULL,
  action      TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  payload     JSONB,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_actor_ts ON audit_log (actor_email, ts DESC);
