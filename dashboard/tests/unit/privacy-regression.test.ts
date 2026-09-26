// Privacy regression test — binding. The public API must never leak a
// sensor identifier, latitude, or longitude, regardless of data source.
// CI fails if any fixture-backed response body contains these keys.

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";
import { liveStreetsRepo } from "@/lib/repo/streets-live";
import postgres from "postgres";
import { ROAD_USER_CLASSES } from "@/lib/types";
import { metricLeaks, readingLeaks } from "./recoverability";

const FORBIDDEN_KEYS = [
  "sensor_id",
  "sensorId",
  "latitude",
  "longitude",
  "lat",
  "lng",
  "lon",
  "gps",
];

function assertClean(value: unknown, path = "$") {
  if (value === null || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((v, i) => assertClean(v, `${path}[${i}]`));
    return;
  }
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_KEYS.includes(k)) {
      throw new Error(`Privacy leak at ${path}.${k}: forbidden key`);
    }
    assertClean(v, `${path}.${k}`);
  }
}

// k-anonymity floor: no published COUNT may fall in 1..(K_MIN-1). Counts are
// integers; keys carrying non-count numerics (geometry coordinates, speeds,
// and — in the speed metric — the `value` field) are skipped so an honest
// -6.26 longitude or a 3 km/h speed is not mistaken for a suppressible count.
const K_MIN = 5;
const NON_COUNT_KEYS = new Set(["avgSpeedKmh", "speedBreakdown", "geom", "bbox"]);

function assertNoSmallCounts(
  value: unknown,
  path = "$",
  skipKeys: Set<string> = NON_COUNT_KEYS
): void {
  if (typeof value === "number") {
    if (Number.isInteger(value) && value >= 1 && value <= K_MIN - 1) {
      throw new Error(
        `k-anonymity leak at ${path}: count ${value} in 1..${K_MIN - 1}`
      );
    }
    return;
  }
  if (value === null || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((v, i) => assertNoSmallCounts(v, `${path}[${i}]`, skipKeys));
    return;
  }
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (skipKeys.has(k)) continue;
    assertNoSmallCounts(v, `${path}.${k}`, skipKeys);
  }
}

describe("privacy regression — public repo outputs", () => {
  // Derive a real street from the fixtures so these tests can never pass
  // vacuously against a renamed/removed slug.
  async function firstStreetId(): Promise<string> {
    const rows = await mockStreetsRepo.list("dublin");
    expect(rows.length).toBeGreaterThan(0);
    const id = rows[0]?.id;
    if (!id) throw new Error("fixture has no streets — privacy test cannot run");
    return id;
  }

  it("list(city) hides sensor fields", async () => {
    const rows = await mockStreetsRepo.list("dublin");
    assertClean(rows);
    expect(rows.length).toBeGreaterThan(0);
  });

  it("get(streetId) hides sensor fields", async () => {
    const row = await mockStreetsRepo.get(await firstStreetId());
    expect(row).not.toBeNull();
    assertClean(row);
  });

  it("readings() hides sensor fields", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: await firstStreetId(),
      from: new Date("2026-04-07T00:00:00Z"),
      to: new Date("2026-04-21T00:00:00Z"),
      bucketMinutes: 15,
    });
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.some((r) => !r.missing)).toBe(true);
    assertClean(rows);
  });

  it("latestMetrics() hides sensor fields", async () => {
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "1h",
    });
    assertClean(rows);
  });
});

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("privacy regression — live repo", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const suffix = crypto.randomUUID();
  const streetId = `privacy-street-${suffix}`;
  const sensorId = `privacy-sensor-${suffix}`;
  const bucket = new Date(Math.floor(Date.now() / 900_000) * 900_000 - 900_000);
  const end = new Date(bucket.getTime() + 900_000);

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
      VALUES (${streetId}, 'Privacy Street', ARRAY[42]::bigint[],
        ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
        ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
        'privacy-test')`;
    await client`INSERT INTO sensors
      (id, display_name, latitude, longitude, install_date, config_json, config_version, api_token_hash)
      VALUES (${sensorId}, 'Private Sensor', 53.3, -6.3, '2026-01-01', '{}'::jsonb, 'v1', 'test-hash')`;
    await client`INSERT INTO sensor_street_coverage (sensor_id, street_id) VALUES (${sensorId}, ${streetId})`;
    await client`INSERT INTO sensor_readings
      (sensor_id, window_start, window_end, class_name, count, avg_speed_kmh,
       direction_ab_count, direction_ba_count)
      VALUES
      (${sensorId}, ${bucket}, ${end}, 'cyclist', 6, 20, 5, 1),
      (${sensorId}, ${bucket}, ${end}, 'car', 2, 45, 1, 1)`;
  });

  afterAll(async () => {
    await client`DELETE FROM sensors WHERE id = ${sensorId}`;
    await client`DELETE FROM streets WHERE id = ${streetId}`;
    await client.end();
  });

  it("keeps all public methods free of sensor and GPS fields", async () => {
    const listed = await liveStreetsRepo.list("privacy-test");
    const detail = await liveStreetsRepo.get(streetId);
    const readings = await liveStreetsRepo.readings({
      streetId, from: bucket, to: end, bucketMinutes: 15,
    });
    const metrics = await liveStreetsRepo.latestMetrics({
      city: "privacy-test", metric: "counts", window: "1h",
    });
    expect(listed).toHaveLength(1);
    expect(detail?.id).toBe(streetId);
    expect(readings[0]?.missing).toBe(false);
    expect(metrics).toHaveLength(1);
    for (const value of [listed, detail, readings, metrics]) assertClean(value);
  });

  it("suppresses low counts, speeds, and direction cells", async () => {
    const rows = await liveStreetsRepo.readings({
      streetId, from: bucket, to: end, bucketMinutes: 15,
    });
    const row = rows[0];
    expect(row?.counts.car).toBeNull();
    expect(row?.avgSpeedKmh.car).toBeNull();
    expect(row?.counts.cyclist).toBe(6);
    expect(row?.avgSpeedKmh.cyclist).toBe(20);
    // BA = 1 is below the floor, so AB = 5 is hidden too: 6 - 5 would give it away.
    expect(row?.countsByDirection?.AB.cyclist).toBeNull();
    expect(row?.countsByDirection?.BA.cyclist).toBeNull();
    assertNoSmallCounts(rows);
    expect(readingLeaks(rows)).toEqual([]);

    const speed = await liveStreetsRepo.latestMetrics({
      city: "privacy-test", metric: "speed", classes: ["car"], window: "1h",
    });
    expect(speed[0]?.value).toBeNull();
    expect(speed[0]?.speedBreakdown.car).toBeNull();
  });

  it("random week: no suppressed value is recoverable by subtraction", async () => {
    // Two sensors on one street: A sends direction cells (schema 1.1), B does
    // not (1.0) in some windows, so buckets mix complete and partial classes.
    const randomStreet = `${streetId}-random`;
    const a = `${sensorId}-a`;
    const b = `${sensorId}-b`;
    await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city)
      VALUES (${randomStreet}, 'Random Street', ARRAY[43]::bigint[],
        ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
        ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
        'privacy-random')`;
    for (const id of [a, b]) {
      await client`INSERT INTO sensors
        (id, display_name, latitude, longitude, install_date, config_json, config_version, api_token_hash)
        VALUES (${id}, 'Random Sensor', 53.3, -6.3, '2026-01-01', '{}'::jsonb, 'v1', ${`hash-${id}`})`;
      await client`INSERT INTO sensor_street_coverage (sensor_id, street_id) VALUES (${id}, ${randomStreet})`;
    }
    let seed = 7;
    const rand = (n: number) => {
      seed = (seed * 1_103_515_245 + 12_345) % 2 ** 31;
      return seed % n;
    };
    const start = Math.floor(Date.now() / 900_000) * 900_000 - 96 * 900_000;
    const values: (string | number | Date | null)[][] = [];
    for (let w = 0; w < 96; w++) {
      const ws = new Date(start + w * 900_000);
      const we = new Date(ws.getTime() + 900_000);
      for (const cls of ROAD_USER_CLASSES) {
        const ab = rand(4) === 0 ? rand(30) : rand(6);
        const ba = rand(6);
        if (ab + ba > 0) values.push([a, ws, we, cls, ab + ba, 30, ab, ba]);
        if (rand(5) === 0) values.push([b, ws, we, cls, 1 + rand(4), null, null, null]);
      }
    }
    try {
      for (const v of values) {
        await client`INSERT INTO sensor_readings
          (sensor_id, window_start, window_end, class_name, count, avg_speed_kmh,
           direction_ab_count, direction_ba_count)
          VALUES (${v[0] as string}, ${v[1] as Date}, ${v[2] as Date}, ${v[3] as string},
            ${v[4] as number}, ${v[5] as number | null}, ${v[6] as number | null}, ${v[7] as number | null})`;
      }
      let directional = 0;
      for (const bucketMinutes of [15, 60, 1440]) {
        const rows = await liveStreetsRepo.readings({
          streetId: randomStreet, from: new Date(start),
          to: new Date(start + 96 * 900_000), bucketMinutes,
        });
        directional += rows.filter((r) => r.countsByDirection).length;
        assertNoSmallCounts(rows);
        expect(readingLeaks(rows)).toEqual([]);
      }
      expect(directional).toBeGreaterThan(0);
      for (const window of ["now", "1h", "24h", "7d"] as const) {
        for (const metric of ["counts", "speed"] as const) {
          const rows = await liveStreetsRepo.latestMetrics({ city: "privacy-random", metric, window });
          expect(metricLeaks(rows, metric)).toEqual([]);
        }
      }
    } finally {
      await client`DELETE FROM sensors WHERE id IN (${a}, ${b})`;
      await client`DELETE FROM streets WHERE id = ${randomStreet}`;
    }
  });

  it("keeps sensor coordinates in the admin method only and gap-fills readings", async () => {
    const admin = await liveStreetsRepo.adminInfo(streetId);
    expect(admin?.sensors[0]).toMatchObject({
      id: sensorId, latitude: 53.3, longitude: -6.3,
    });
    const rows = await liveStreetsRepo.readings({
      streetId, from: bucket,
      to: new Date(end.getTime() + 900_000), bucketMinutes: 15,
    });
    expect(rows).toHaveLength(2);
    expect(rows[0]?.missing).toBe(false);
    expect(rows[1]?.missing).toBe(true);
    expect(rows[1]?.counts.car).toBeNull();
    const uncovered = await liveStreetsRepo.readings({
      streetId: `uncovered-${suffix}`, from: bucket, to: end, bucketMinutes: 15,
    });
    expect(uncovered).toEqual([]);
  });
});

describe("k-anonymity floor — no published count in 1..4", () => {
  const from = new Date("2026-04-20T00:00:00Z");
  const to = new Date("2026-04-21T00:00:00Z");

  async function firstStreetId(): Promise<string> {
    const rows = await mockStreetsRepo.list("dublin");
    const id = rows[0]?.id;
    if (!id) throw new Error("fixture has no streets — k-anon test cannot run");
    return id;
  }

  it("list(city) carries no suppressible count", async () => {
    const rows = await mockStreetsRepo.list("dublin");
    assertNoSmallCounts(rows);
  });

  it("get(streetId) [detail] carries no suppressible count", async () => {
    const row = await mockStreetsRepo.get(await firstStreetId());
    assertNoSmallCounts(row);
  });

  it("readings() [windowed, 15-min] suppresses every count in 1..4", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: await firstStreetId(),
      from,
      to,
      bucketMinutes: 15,
    });
    expect(rows.length).toBeGreaterThan(0);
    assertNoSmallCounts(rows);
  });

  it("readings() [daily, 1440-min] suppresses every count in 1..4", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: await firstStreetId(),
      from,
      to,
      bucketMinutes: 1440,
    });
    expect(rows.length).toBeGreaterThan(0);
    assertNoSmallCounts(rows);
  });

  it("publishes optional direction counts with per-cell suppression", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: "ucd-stillorgan-rd-entrance",
      from,
      to,
      bucketMinutes: 15,
    });
    const directional = rows.filter((row) => row.countsByDirection !== undefined);
    expect(directional.length).toBeGreaterThan(0);
    expect(
      directional.some((row) =>
        [...Object.values(row.countsByDirection!.AB), ...Object.values(row.countsByDirection!.BA)]
          .some((count) => count === null)
      )
    ).toBe(true);
    assertNoSmallCounts(directional);
  });

  it("omits direction counts for streets without direction data", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: "ranelagh-rd",
      from,
      to,
      bucketMinutes: 15,
    });
    expect(rows.some((row) => !row.missing)).toBe(true);
    expect(rows.every((row) => row.countsByDirection === undefined)).toBe(true);
  });

  it("latestMetrics(counts) suppresses value + classBreakdown below the floor", async () => {
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "24h",
    });
    // `value` here is a count → scanned; speed fields skipped by key.
    assertNoSmallCounts(rows);
  });

  it("latestMetrics(speed) still suppresses classBreakdown counts", async () => {
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "speed",
      window: "24h",
    });
    // In speed mode `value` is a speed (float), so skip it alongside the other
    // non-count numerics; classBreakdown remains a count and must be clean.
    assertNoSmallCounts(rows, "$", new Set([...NON_COUNT_KEYS, "value"]));
  });

  it("suppression is real, not vacuous — some class is actually nulled", async () => {
    // Across a full day the fixtures contain many 1..4 counts, so at least one
    // per-class value must come back suppressed. Guards against the test
    // passing simply because no small counts existed.
    const rows = await mockStreetsRepo.readings({
      streetId: await firstStreetId(),
      from,
      to,
      bucketMinutes: 15,
    });
    const anySuppressed = rows.some(
      (r) => !r.missing && Object.values(r.counts).some((n) => n === null)
    );
    expect(anySuppressed).toBe(true);
  });

  it("zero counts are retained (0 is not re-identifiable)", async () => {
    // A present bucket keeps 0 for classes with genuinely no traffic; only
    // 1..4 is nulled. Prove 0 survives somewhere in a present window.
    const rows = await mockStreetsRepo.readings({
      streetId: await firstStreetId(),
      from,
      to,
      bucketMinutes: 15,
    });
    const anyZero = rows.some(
      (r) => !r.missing && Object.values(r.counts).some((n) => n === 0)
    );
    expect(anyZero).toBe(true);
  });

  it("suppresses speeds when their class count is below five", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: "ucd-stillorgan-rd-entrance",
      classes: ["cyclist"],
      from: new Date("2026-04-07T00:00:00Z"),
      to: new Date("2026-04-07T00:15:00Z"),
      bucketMinutes: 15,
    });
    expect(rows[0]?.counts.cyclist).toBeNull();
    expect(rows[0]?.avgSpeedKmh.cyclist).toBeNull();

    const metrics = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "speed",
      classes: ["car"],
      window: "now",
    });
    const street = metrics.find((row) => row.streetId === "ucd-stillorgan-rd-entrance");
    expect(street?.classBreakdown.car).toBeNull();
    expect(street?.speedBreakdown.car).toBeNull();
    expect(street?.avgSpeedKmh).toBeNull();
    expect(street?.value).toBeNull();
  });
});
