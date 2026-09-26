import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { reconcileDay } from "@/lib/reconcile-daily";
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
        (${sensorId}, '2026-09-25T00:15:00Z', '2026-09-25T00:30:00Z', 'car', 4, false)
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
});
