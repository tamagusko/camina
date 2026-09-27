// config_json is real jsonb: provisioning stores an object, and GET /config
// reads configs written by plain SQL as well as legacy double-encoded ones.

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import postgres from "postgres";
import { randomUUID } from "node:crypto";
import { provisionSensor } from "../../scripts/provision-sensor";

const CONFIG = {
  publish_interval_minutes: 15,
  heartbeat_interval_minutes: 5,
  daily_publish_time_utc: "00:00",
  detection_zone: null,
  frame_skip: 5,
  min_track_hits: 3,
};

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("sensor config_json", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const suffix = randomUUID();
  const streetId = `cfg-street-${suffix}`;
  const provisioned = `cfg-prov-${suffix}`;
  const plain = `cfg-sql-${suffix}`;
  const legacy = `cfg-legacy-${suffix}`;

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
      VALUES (${streetId}, 'Config Street', ARRAY[42]::bigint[],
        ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
        ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
        'config-test')`;
    // A constant JSON literal in the SQL text, as an operator would type it.
    const literal = JSON.stringify(CONFIG).replaceAll("'", "''");
    await client.unsafe(
      `INSERT INTO sensors (id, display_name, latitude, longitude, install_date,
         config_json, config_version, api_token_hash)
       VALUES ($1, 'SQL', 53.3, -6.3, '2026-01-01', '${literal}'::jsonb, 'sql-v1', $2),
              ($3, 'Legacy', 53.3, -6.3, '2026-01-01', to_jsonb('${literal}'::text), 'legacy-v1', $4)`,
      [plain, `h-${plain}`, legacy, `h-${legacy}`]
    );
    const types = await client`SELECT id, jsonb_typeof(config_json) AS t FROM sensors
      WHERE id IN (${plain}, ${legacy}) ORDER BY id`;
    expect(types.map((r) => r.t).sort()).toEqual(["object", "string"]);
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id IN (${provisioned}, ${plain}, ${legacy})`;
    await client`DELETE FROM streets WHERE id = ${streetId}`;
    await client.end();
  });

  it("provisioning stores a jsonb object, not a string", async () => {
    await provisionSensor(client, {
      id: provisioned, displayName: "Prov", streetId, latitude: 53.3, longitude: -6.3,
      installDate: "2026-09-26", configVersion: "1", config: CONFIG,
    });
    const rows = await client`
      SELECT jsonb_typeof(config_json) AS t, config_json->>'frame_skip' AS fs
      FROM sensors WHERE id = ${provisioned}`;
    expect(rows[0]).toEqual({ t: "object", fs: "5" });
  });

  it("reads a config inserted with plain SQL and a legacy double-encoded one", async () => {
    const { readSensorConfig } = await import("@/lib/ingest-store");
    for (const [id, version] of [[plain, "sql-v1"], [legacy, "legacy-v1"]] as const) {
      const cfg = await readSensorConfig(id);
      // The deployment heartbeat (CAMINA_HEARTBEAT_MINUTES, default 15) wins over the stored value.
      expect(cfg).toEqual({
        config: { ...CONFIG, heartbeat_interval_minutes: 15 },
        config_version: `${version}+hb15`,
      });
    }
  });

  it("an object edited in SQL keeps working", async () => {
    await client`UPDATE sensors SET config_json = config_json || '{"frame_skip": 7}'::jsonb
      WHERE id = ${plain}`;
    const { readSensorConfig } = await import("@/lib/ingest-store");
    expect((await readSensorConfig(plain))?.config.frame_skip).toBe(7);
  });
});
