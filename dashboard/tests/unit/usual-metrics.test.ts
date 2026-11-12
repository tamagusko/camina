// The map's "vs usual" mode: the mock adapter carries a usual total per street,
// built from the same published totals as the counts (src/lib/typical.ts).
import { describe, expect, it } from "vitest";

import { mockStreetsRepo } from "@/lib/repo/streets-mock";

describe("mock adapter: usual total", () => {
  it("gives streets with enough history a usual total for counts", async () => {
    for (const window of ["now", "24h", "7d"] as const) {
      const rows = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "counts", window });
      const withUsual = rows.filter((r) => r.typical !== null);
      expect(withUsual.length, window).toBeGreaterThan(0);
      for (const r of withUsual) expect(r.typical).toBeGreaterThanOrEqual(0);
    }
  });

  it("follows the class filter", async () => {
    const all = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "counts", window: "24h" });
    const cars = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "counts", window: "24h", classes: ["car"] });
    for (const row of cars) {
      const other = all.find((r) => r.streetId === row.streetId)!;
      if (row.typical !== null && other.typical !== null) expect(row.typical).toBeLessThan(other.typical);
    }
  });

  it("has no usual total for speed", async () => {
    const rows = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "speed", window: "24h" });
    expect(rows.every((r) => r.typical === null)).toBe(true);
  });
});
