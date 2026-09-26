-- Direction counts are present only for screenline sensors. Null means the
-- legacy/movement payload omitted direction; zero is a measured zero.
ALTER TABLE sensor_readings
  ADD COLUMN direction_ab_count INTEGER,
  ADD COLUMN direction_ba_count INTEGER,
  ADD CONSTRAINT sensor_readings_direction_counts_valid CHECK (
    (direction_ab_count IS NULL AND direction_ba_count IS NULL)
    OR (
      direction_ab_count IS NOT NULL AND direction_ba_count IS NOT NULL
      AND direction_ab_count >= 0 AND direction_ba_count >= 0
      AND direction_ab_count + direction_ba_count = count
    )
  );
