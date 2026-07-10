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
