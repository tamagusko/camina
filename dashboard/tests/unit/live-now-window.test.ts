// "Now" on the live map is the last completed 15-min cell. A sensor publishes
// the cell [S, S+15) at S+15, so a cutoff of `now − 15 min` over window_start
// never reached it and window=now was always empty. Every window ends at that
// cell, and a street whose last completed cell has not arrived is stale, not 0.
// The clock is injected; nothing here depends on wall time.

import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { lastCompletedCellEnd } from "@/lib/repo/streets-mock";

const MIN = 60_000;

describe("lastCompletedCellEnd", () => {
  it("is the end of the latest 15-min cell whose window_end <= now", () => {
    expect(lastCompletedCellEnd(new Date("2026-03-10T10:07:00Z")).toISOString()).toBe("2026-03-10T10:00:00.000Z");
    expect(lastCompletedCellEnd(new Date("2026-03-10T10:00:00Z")).toISOString()).toBe("2026-03-10T10:00:00.000Z");
    expect(lastCompletedCellEnd(new Date("2026-03-10T09:59:59Z")).toISOString()).toBe("2026-03-10T09:45:00.000Z");
  });
});

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("live latestMetrics — window=now", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const city = `now-test-${randomUUID()}`;
  const onTime = `${city}-on-time`;
  const late = `${city}-late`;
  const now = new Date("2026-03-10T10:07:00Z");
  const at = (iso: string) => new Date(`2026-03-10T${iso}:00Z`);

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    for (const id of [onTime, late]) {
      await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
        VALUES (${id}, 'Now Test', ARRAY[42]::bigint[],
          ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
          ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
          ${city})`;
      await client`INSERT INTO sensors
        (id, display_name, latitude, longitude, install_date, config_json, config_version, api_token_hash)
        VALUES (${id}, 'Now Sensor', 53.3, -6.3, '2026-01-01', '{}'::jsonb, 'v1', 'test-hash')`;
      await client`INSERT INTO sensor_street_coverage (sensor_id, street_id) VALUES (${id}, ${id})`;
    }
    // On time: 09:00, 09:30 and the last completed cell 09:45–10:00.
    for (const [start, n] of [["09:00", 8], ["09:30", 12], ["09:45", 7]] as const) {
      await client`INSERT INTO sensor_readings (sensor_id, window_start, window_end, class_name, count)
        VALUES (${onTime}, ${at(start)}, ${new Date(at(start).getTime() + 15 * MIN)}, 'car', ${n})`;
    }
    // Late: 09:30 arrived, 09:45–10:00 has not.
    await client`INSERT INTO sensor_readings (sensor_id, window_start, window_end, class_name, count)
      VALUES (${late}, ${at("09:30")}, ${at("09:45")}, 'car', 9)`;
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id IN (${onTime}, ${late})`;
    await client`DELETE FROM streets WHERE city = ${city}`;
    await client.end();
  });

  async function metrics(window: "now" | "1h") {
    const { liveStreetsRepo } = await import("@/lib/repo/streets-live");
    const rows = await liveStreetsRepo.latestMetrics({ city, metric: "counts", window, now });
    return new Map(rows.map((row) => [row.streetId, row]));
  }

  it("shows the last completed cell", async () => {
    const row = (await metrics("now")).get(onTime);
    expect(row?.totalCount).toBe(7);
    expect(row?.stale).toBe(false);
    expect(row?.lastSeen).toBe("2026-03-10T10:00:00.000Z");
  });

  it("marks a street stale, not 0, when its last completed cell is late", async () => {
    const row = (await metrics("now")).get(late);
    expect(row?.stale).toBe(true);
  });

  it("ends every window at the last completed cell (1 h = four whole cells)", async () => {
    expect((await metrics("1h")).get(onTime)?.totalCount).toBe(8 + 12 + 7);
  });
});
