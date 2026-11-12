-- Speed histogram per row: timed road users in 53 bins, 1 km/h wide to 20,
-- 2 km/h to 60, 5 km/h to 120, the last open (120 km/h and over). The
-- dashboard sums them into the v85 of any window (src/lib/privacy.ts); the
-- histogram itself is never published.
-- Null for rows without a speed and for sensors that predate it.
ALTER TABLE sensor_readings
  ADD COLUMN speed_hist_kmh INTEGER[],
  ADD CONSTRAINT sensor_readings_speed_hist_valid CHECK (
    speed_hist_kmh IS NULL
    OR (
      avg_speed_kmh IS NOT NULL
      AND cardinality(speed_hist_kmh) = 53
      AND 0 <= ALL (speed_hist_kmh)
      AND array_position(speed_hist_kmh, NULL) IS NULL
    )
  );
