-- The road's speed limit, km/h: OpenStreetMap maxspeed by default, set by hand
-- where OSM is wrong or silent. Null when unknown. The speed page counts the
-- road users above it from the stored speed histograms (src/lib/privacy.ts).
ALTER TABLE streets
  ADD COLUMN speed_limit_kmh SMALLINT,
  ADD CONSTRAINT streets_speed_limit_valid CHECK (
    speed_limit_kmh IS NULL OR speed_limit_kmh BETWEEN 5 AND 130
  );
