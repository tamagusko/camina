// The live adapter's usual total: the same window in past weeks, from
// published cells only, scaled by the 15-min cells that had data.
import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const MIN = 60_000;
const WEEK = 7 * 24 * 60 * MIN;

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("live latestMetrics — usual total", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const city = `usual-test-${randomUUID()}`;
  const steady = `${city}-steady`;
  const young = `${city}-young`;
  const now = new Date("2026-03-10T10:07:00Z");
  const cell = new Date("2026-03-10T09:45:00Z"); // the "now" cell

  async function reading(sensor: string, weeksBack: number, cls: string, n: number) {
    const start = new Date(cell.getTime() - weeksBack * WEEK);
    await client`INSERT INTO sensor_readings (sensor_id, window_start, window_end, class_name, count)
      VALUES (${sensor}, ${start}, ${new Date(start.getTime() + 15 * MIN)}, ${cls}, ${n})`;
  }

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    for (const id of [steady, young]) {
      await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
        VALUES (${id}, 'Usual Test', ARRAY[42]::bigint[],
          ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
          ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
          ${city})`;
      await client`INSERT INTO sensors
        (id, display_name, latitude, longitude, install_date, config_json, config_version, api_token_hash)
        VALUES (${id}, 'Usual Sensor', 53.3, -6.3, '2026-01-01', '{}'::jsonb, 'v1', 'test-hash')`;
      await client`INSERT INTO sensor_street_coverage (sensor_id, street_id) VALUES (${id}, ${id})`;
    }
    // Steady: cars 30 now; 20 and 40 one and two weeks back; buses 10 every week.
    for (const [k, cars] of [[0, 30], [1, 20], [2, 40]] as const) {
      await reading(steady, k, "car", cars);
      await reading(steady, k, "bus", 10);
    }
    // Young: only one past week.
    await reading(young, 0, "car", 30);
    await reading(young, 1, "car", 30);
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id IN (${steady}, ${young})`;
    await client`DELETE FROM streets WHERE city = ${city}`;
    await client.end();
  });

  async function metrics(classes?: ["car"]) {
    const { liveStreetsRepo } = await import("@/lib/repo/streets-live");
    const rows = await liveStreetsRepo.latestMetrics({ city, metric: "counts", window: "now", classes, now });
    return new Map(rows.map((row) => [row.streetId, row]));
  }

  it("averages the same cell in past weeks", async () => {
    expect((await metrics()).get(steady)?.typical).toBe(40);
    expect((await metrics(["car"])).get(steady)?.typical).toBe(30);
  });

  it("needs two past weeks with data", async () => {
    expect((await metrics()).get(young)?.typical).toBeNull();
  });
});
