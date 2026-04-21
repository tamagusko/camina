// Privacy regression test — binding. The public API must never leak a
// sensor identifier, latitude, or longitude, regardless of data source.
// CI fails if any fixture-backed response body contains these keys.

import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";

const FORBIDDEN_KEYS = ["sensor_id", "sensorId", "latitude", "longitude"];

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
  it("list(city) hides sensor fields", async () => {
    const rows = await mockStreetsRepo.list("dublin");
    assertClean(rows);
    expect(rows.length).toBeGreaterThan(0);
  });

  it("get(streetId) hides sensor fields", async () => {
    const row = await mockStreetsRepo.get("dame-st");
    assertClean(row);
  });

  it("readings() hides sensor fields", async () => {
    const rows = await mockStreetsRepo.readings({
      streetId: "dame-st",
      from: new Date("2026-04-14T00:00:00Z"),
      to: new Date("2026-04-22T00:00:00Z"),
      bucketMinutes: 15,
    });
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
