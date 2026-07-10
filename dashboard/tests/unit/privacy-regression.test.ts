// Privacy regression test — binding. The public API must never leak a
// sensor identifier, latitude, or longitude, regardless of data source.
// CI fails if any fixture-backed response body contains these keys.

import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";

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
});
