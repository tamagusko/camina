-- No schema change. 0000_init.sql created streets.geom and streets.bbox in raw
-- SQL, but no drizzle snapshot recorded them, so drizzle-kit would propose
-- adding (or, against a live database, dropping) them. This migration exists
-- only to record the snapshot with the PostGIS columns (meta/0003_snapshot.json).
SELECT 1;
