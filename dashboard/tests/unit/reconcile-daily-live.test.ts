import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { RECONCILE_LOOKBACK_DAYS, reconcileDay, reconcileRecent } from "@/lib/reconcile-daily";
import * as schema from "../../drizzle/schema";

const databaseUrl = process.env.DATABASE_URL_TEST;
const describeLive = databaseUrl ? describe : describe.skip;

describeLive("daily reconciliation against Postgres", () => {
  const client = postgres(databaseUrl ?? "postgres://unused", { max: 1, prepare: false });
  const database = drizzle(client, { schema });
  const sensorId = `reconcile-${randomUUID()}`;
  const day = "2026-09-25";

  beforeAll(async () => {
    await client`
      INSERT INTO sensors (
        id, display_name, latitude, longitude, install_date, config_json,
        config_version, api_token_hash
      ) VALUES (
        ${sensorId}, 'Reconcile test', 53.3, -6.2, ${day}, '{}'::jsonb, '1', 'test-hash'
      )
    `;
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id = ${sensorId}`;
    await client.end();
  });

  it("persists a mismatch and clears it after the totals agree", async () => {
    await client`
      INSERT INTO sensor_readings (
        sensor_id, window_start, window_end, class_name, count, partial
      ) VALUES
        (${sensorId}, '2026-09-25T00:00:00Z', '2026-09-25T00:15:00Z', 'car', 3, false),
        (${sensorId}, '2026-09-25T00:15:00Z', '2026-09-25T00:30:00Z', 'car', 4, true)
    `;
    await client`
      INSERT INTO sensor_daily_totals (
        sensor_id, day, totals_json, window_count
      ) VALUES (${sensorId}, ${day}, '{"car": 8}'::jsonb, 2)
    `;

    const mismatchRun = await reconcileDay(day, database);
    expect(mismatchRun.day).toBe(day);
    expect(mismatchRun.checked).toBeGreaterThanOrEqual(1);
    expect(mismatchRun.mismatched).toBeGreaterThanOrEqual(1);
    let [stored] = await client`
      SELECT reconciled, mismatch_json FROM sensor_daily_totals
      WHERE sensor_id = ${sensorId} AND day = ${day}
    `;
    expect(stored?.reconciled).toBe(false);
    expect(stored?.mismatch_json).toMatchObject({
      classes: { car: { daily: 8, windows: 7, difference: -1 } },
    });

    await client`
      UPDATE sensor_daily_totals SET totals_json = '{"car": 7}'::jsonb
      WHERE sensor_id = ${sensorId} AND day = ${day}
    `;
    const resolvedRun = await reconcileDay(day, database);
    expect(resolvedRun.day).toBe(day);
    expect(resolvedRun.checked).toBeGreaterThanOrEqual(1);
    [stored] = await client`
      SELECT reconciled, mismatch_json FROM sensor_daily_totals
      WHERE sensor_id = ${sensorId} AND day = ${day}
    `;
    expect(stored).toMatchObject({ reconciled: true, mismatch_json: null });
  });

  it("sweeps unreconciled and late days in the lookback window, idempotently", async () => {
    // Far from other fixtures: "now" is 2020-01-15, so the window is 01-05..01-14.
    const now = new Date("2020-01-15T02:00:00Z");
    expect(RECONCILE_LOOKBACK_DAYS).toBe(10);
    const days = ["2020-01-14", "2020-01-10", "2020-01-05", "2020-01-04"];
    for (const d of days) {
      await client`
        INSERT INTO sensor_readings (sensor_id, window_start, window_end, class_name, count)
        VALUES (${sensorId}, ${`${d}T08:00:00Z`}, ${`${d}T08:15:00Z`}, 'car', 9)
      `;
      await client`
        INSERT INTO sensor_daily_totals (sensor_id, day, totals_json, window_count)
        VALUES (${sensorId}, ${d}, '{"car": 9}'::jsonb, 1)
      `;
    }
    // A late window on an already reconciled day must be re-checked.
    await client`UPDATE sensor_daily_totals SET reconciled = true
      WHERE sensor_id = ${sensorId} AND day = '2020-01-10'`;
    await client`
      INSERT INTO sensor_readings (sensor_id, window_start, window_end, class_name, count)
      VALUES (${sensorId}, '2020-01-10T09:00:00Z', '2020-01-10T09:15:00Z', 'car', 2)
    `;

    const read = async () => Object.fromEntries((await client`
      SELECT day::text AS day, reconciled, mismatch_json FROM sensor_daily_totals
      WHERE sensor_id = ${sensorId} AND day < '2020-02-01'
    `).map((row) => [row.day, [row.reconciled, row.mismatch_json === null]]));

    const first = await reconcileRecent(now, database);
    expect(first.days).toHaveLength(10);
    expect(first.days[0]).toBe("2020-01-14");
    expect(first.days.at(-1)).toBe("2020-01-05");
    const expected = {
      "2020-01-14": [true, true],
      "2020-01-10": [false, false],
      "2020-01-05": [true, true],
      "2020-01-04": [false, true], // outside the window: untouched
    };
    expect(await read()).toEqual(expected);
    await reconcileRecent(now, database);
    expect(await read()).toEqual(expected);
  });
});
