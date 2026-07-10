-- CAMINA retention + bounded materialized views (audit C1, H12, H14).
--
-- WHY: Neon free tier caps at 0.5 GB. At 100 sensors raw `sensor_readings`
-- grows ~3-6 GB/yr (audit C1), so raw rows must be pruned. This migration:
--   1. Adds durable, plain aggregate rollup tables (street_hourly / street_daily)
--      that survive raw pruning and back the dashboard history charts.
--   2. Adds a `cron_meta` table used to gate the piggyback MV refresh (H14).
--   3. Re-creates the public materialized views bounded to the ~48 h painted
--      window (H12) so a REFRESH scans only recent raw rows, not the whole table.
--
-- The retention cron (/api/cron/retention) rolls raw rows older than 90 days
-- INTO these aggregates and DELETEs them, in bounded single-transaction batches
-- guarded by a transaction-scoped advisory lock.

-- ── Durable rollup tables (history store) ──────────────────────────
-- Averages are stored as weighted-sum components (speed_weighted_sum /
-- speed_count) rather than a pre-divided mean, so additive ON CONFLICT merges
-- across retention batches stay exact. avg_speed_kmh is a derived read column.

CREATE TABLE street_hourly (
  street_id          TEXT NOT NULL REFERENCES streets(id) ON DELETE CASCADE,
  class_name         TEXT NOT NULL,
  hour               TIMESTAMPTZ NOT NULL,          -- date_trunc('hour', window_start)
  total_count        BIGINT NOT NULL DEFAULT 0,
  speed_weighted_sum DOUBLE PRECISION NOT NULL DEFAULT 0,  -- Σ(avg_speed_kmh * count) over speed-bearing rows
  speed_count        BIGINT NOT NULL DEFAULT 0,            -- Σ(count) over speed-bearing rows
  avg_speed_kmh      DOUBLE PRECISION
                       GENERATED ALWAYS AS (speed_weighted_sum / NULLIF(speed_count, 0)) STORED,
  PRIMARY KEY (street_id, class_name, hour)
);
CREATE INDEX idx_street_hourly_hour ON street_hourly (hour);

CREATE TABLE street_daily (
  street_id          TEXT NOT NULL REFERENCES streets(id) ON DELETE CASCADE,
  class_name         TEXT NOT NULL,
  day                DATE NOT NULL,                 -- date_trunc('day', window_start)::date
  total_count        BIGINT NOT NULL DEFAULT 0,
  speed_weighted_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
  speed_count        BIGINT NOT NULL DEFAULT 0,
  avg_speed_kmh      DOUBLE PRECISION
                       GENERATED ALWAYS AS (speed_weighted_sum / NULLIF(speed_count, 0)) STORED,
  PRIMARY KEY (street_id, class_name, day)
);
CREATE INDEX idx_street_daily_day ON street_daily (day);

-- ── Cron coordination metadata ─────────────────────────────────────
-- Single-row-per-job table. Backs the min-interval gate for the piggyback MV
-- refresh so an ingest burst triggers at most ~1 refresh per window.
CREATE TABLE cron_meta (
  job         TEXT PRIMARY KEY,
  last_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  stats       JSONB
);

-- ── Bound the public materialized views to the painted window (H12) ─
-- 0000_init.sql created these views over the ENTIRE sensor_readings table,
-- so every refresh scanned all history. Re-create them bounded to 48 h. The
-- now() filter is re-evaluated on each REFRESH.
DROP MATERIALIZED VIEW IF EXISTS street_readings_hourly;
DROP MATERIALIZED VIEW IF EXISTS street_readings_15m;

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
WHERE r.window_start > now() - INTERVAL '48 hours'
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
