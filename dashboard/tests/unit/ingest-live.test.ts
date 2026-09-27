import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { randomUUID } from "node:crypto";
import { and, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { sensorReadings, sensors } from "../../drizzle/schema";
import { persistCounts, readSensorConfigVersion } from "@/lib/ingest-store";
import { countsPayloadSchema } from "@/lib/schemas";

const databaseUrl = process.env.DATABASE_URL_TEST;
const describeWithDatabase = databaseUrl ? describe : describe.skip;

describeWithDatabase("ingest live persistence", () => {
  const sensorId = `test-ingest-direction-${randomUUID()}`;
  const client = postgres(databaseUrl ?? "postgres://unused", {
    max: 1,
    prepare: false,
  });
  const database = drizzle(client);

  beforeAll(async () => {
    await database.insert(sensors).values({
      id: sensorId,
      displayName: "Direction ingest test",
      latitude: 53.34,
      longitude: -6.26,
      installDate: "2026-09-26",
      configJson: {},
      configVersion: "test-v1",
      apiTokenHash: "test-only",
    });
  });

  afterAll(async () => {
    await database.delete(sensors).where(eq(sensors.id, sensorId));
    await client.end();
  });

  it("idempotently updates counts and both direction cells", async () => {
    const windowStart = new Date(Date.now() - 901_000).toISOString();
    const base = {
      schema_version: "1.1",
      sensor_id: sensorId,
      window_start: windowStart,
      window_end: new Date(Date.now() - 1_000).toISOString(),
      partial: false,
      counts: { car: 8 },
      counts_by_direction: { AB: { car: 5 }, BA: { car: 3 } },
      avg_speed_kmh: { car: 24 },
      config_version: "test-v1",
      fw_version: "test",
      produced_at: new Date().toISOString(),
    };
    await persistCounts(countsPayloadSchema.parse(base), sensorId, database);
    await persistCounts(
      countsPayloadSchema.parse({
        ...base,
        counts: { car: 9 },
        counts_by_direction: { AB: { car: 4 }, BA: { car: 5 } },
      }),
      sensorId,
      database
    );

    const rows = await database
      .select()
      .from(sensorReadings)
      .where(
        and(
          eq(sensorReadings.sensorId, sensorId),
          eq(sensorReadings.windowStart, new Date(windowStart))
        )
      );
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      count: 9,
      directionAbCount: 4,
      directionBaCount: 5,
    });
  });

  it("rejects a direction pair with one missing cell at the database boundary", async () => {
    await expect(client`
      INSERT INTO sensor_readings
        (sensor_id, window_start, window_end, class_name, count,
         direction_ab_count, direction_ba_count)
      VALUES (${sensorId}, '2026-09-26T00:00:00Z', '2026-09-26T00:15:00Z',
              'car', 5, 5, NULL)
    `).rejects.toThrow();
  });

  it("reads a changed config version from the sensor row", async () => {
    expect(await readSensorConfigVersion(sensorId, database)).toBe("test-v1+hb15"); // tagged with CAMINA_HEARTBEAT_MINUTES (default 15)
    await database.update(sensors).set({ configVersion: "test-v2" }).where(eq(sensors.id, sensorId));
    expect(await readSensorConfigVersion(sensorId, database)).toBe("test-v2+hb15");
  });
});
