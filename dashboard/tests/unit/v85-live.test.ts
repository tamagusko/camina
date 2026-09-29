// The live adapter's v85: speed histograms summed in SQL over published base
// cells only, then read as the 85th percentile (src/lib/privacy.ts).
import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { SPEED_BIN_EDGES, emptyHistogram } from "@/lib/privacy";

const MIN = 60_000;

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("live v85", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const city = `v85-test-${randomUUID()}`;
  const id = `${city}-road`;
  const now = new Date("2026-03-10T10:07:00Z");
  const first = new Date("2026-03-10T09:15:00Z");

  // Keyed by a bin's lower edge in km/h.
  function hist(bins: Record<number, number>): number[] {
    const h = emptyHistogram();
    for (const [edge, n] of Object.entries(bins)) h[SPEED_BIN_EDGES.indexOf(Number(edge))] = n;
    return h;
  }

  async function reading(start: Date, cls: string, n: number, avg: number, h: number[]) {
    await client`INSERT INTO sensor_readings
      (sensor_id, window_start, window_end, class_name, count, avg_speed_kmh, speed_hist_kmh)
      VALUES (${id}, ${start}, ${new Date(start.getTime() + 15 * MIN)}, ${cls}, ${n}, ${avg}, ${h})`;
  }

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
      VALUES (${id}, 'v85 Test', ARRAY[42]::bigint[],
        ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
        ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
        ${city})`;
    await client`INSERT INTO sensors
      (id, display_name, latitude, longitude, install_date, config_json, config_version, api_token_hash)
      VALUES (${id}, 'v85 Sensor', 53.3, -6.3, '2026-01-01', '{}'::jsonb, 'v1', 'test-hash')`;
    await client`INSERT INTO sensor_street_coverage (sensor_id, street_id) VALUES (${id}, ${id})`;
    // Two published car cells: 10 in [20, 22), then 10 in [40, 42).
    await reading(first, "car", 10, 21, hist({ 20: 10 }));
    await reading(new Date(first.getTime() + 15 * MIN), "car", 10, 41, hist({ 40: 10 }));
    // A hidden cell (3 cars) at 100 km/h: must not reach any v85.
    await reading(new Date(first.getTime() + 30 * MIN), "car", 3, 100, hist({ 100: 3 }));
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id = ${id}`;
    await client`DELETE FROM streets WHERE city = ${city}`;
    await client.end();
  });

  it("reads v85 from the summed histograms of published cells", async () => {
    const { liveStreetsRepo } = await import("@/lib/repo/streets-live");
    const [row] = await liveStreetsRepo.latestMetrics({ city, metric: "counts", window: "1h", now });
    expect(row?.v85Breakdown.car).toBeCloseTo(41.4);
    expect(row?.v85Kmh).toBeCloseTo(41.4);
  });

  it("gives each bucket its own v85", async () => {
    const { liveStreetsRepo } = await import("@/lib/repo/streets-live");
    const rows = await liveStreetsRepo.readings({
      streetId: id, from: first, to: new Date(first.getTime() + 45 * MIN), bucketMinutes: 15,
    });
    expect(rows.map((r) => r.v85Kmh.car ?? null)).toEqual([
      expect.closeTo(21.7), expect.closeTo(41.7), null,
    ]);
  });

  it("refuses a histogram of the wrong length", async () => {
    await expect(reading(new Date(first.getTime() + 45 * MIN), "bus", 5, 20, [5])).rejects.toThrow();
  });
});
