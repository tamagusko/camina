import { afterAll, beforeAll, describe, expect, it } from "vitest";
import postgres from "postgres";
import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { provisionSensor } from "../../scripts/provision-sensor";

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("sensor provisioning", () => {
  const client = postgres(process.env.DATABASE_URL_TEST ?? "", { max: 1 });
  const streetId = `provision-street-${randomUUID()}`;
  const sensorId = `provision-sensor-${randomUUID()}`;
  const cliSensorId = `provision-cli-${randomUUID()}`;
  const opts = {
    id: sensorId,
    displayName: "Provision Sensor",
    streetId,
    latitude: 53.3,
    longitude: -6.3,
    installDate: "2026-09-26",
    configVersion: "1",
    config: {
      publish_interval_minutes: 15,
      heartbeat_interval_minutes: 5,
      frame_skip: 5,
      min_track_hits: 3,
    },
  };

  beforeAll(async () => {
    await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
      VALUES (${streetId}, 'Provision Street', ARRAY[42]::bigint[],
        ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
        ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
        'provision-test')`;
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id = ${sensorId}`;
    await client`DELETE FROM sensors WHERE id = ${cliSensorId}`;
    await client`DELETE FROM streets WHERE id = ${streetId}`;
    await client.end();
  });

  it("stores only a hash, refuses overwrite, and rotates explicitly", async () => {
    const token = await provisionSensor(client, opts);
    const created = await client`SELECT api_token_hash FROM sensors WHERE id = ${sensorId}`;
    const coverage = await client`SELECT street_id FROM sensor_street_coverage WHERE sensor_id = ${sensorId}`;
    expect(created[0]?.api_token_hash).toBe(createHash("sha256").update(token).digest("hex"));
    expect(created[0]?.api_token_hash).not.toBe(token);
    expect(coverage[0]?.street_id).toBe(streetId);

    await expect(provisionSensor(client, opts)).rejects.toThrow(/already exists/);
    const replacement = await provisionSensor(client, { id: sensorId, rotate: true });
    const rotated = await client`SELECT api_token_hash FROM sensors WHERE id = ${sensorId}`;
    expect(replacement).not.toBe(token);
    expect(rotated[0]?.api_token_hash).toBe(createHash("sha256").update(replacement).digest("hex"));
  });

  it("prints exactly one token from the CLI", async () => {
    const output = execFileSync(path.resolve("node_modules/.bin/tsx"), [
      "scripts/provision-sensor.ts", "--id", cliSensorId,
      "--display-name", "CLI Sensor", "--street-id", streetId,
      "--latitude", "53.3", "--longitude", "-6.3",
    ], {
      cwd: process.cwd(),
      env: { ...process.env, DATABASE_URL: process.env.DATABASE_URL_TEST },
      encoding: "utf8",
    });
    expect(output.trim().split("\n")).toHaveLength(1);
    const stored = await client`SELECT api_token_hash FROM sensors WHERE id = ${cliSensorId}`;
    expect(stored[0]?.api_token_hash).toBe(createHash("sha256").update(output.trim()).digest("hex"));
  });
});
