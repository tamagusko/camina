// Privacy across aggregation levels — binding. A hidden 15-min cell must not be
// recoverable by differencing any two published numbers: a 60- or 1440-min
// bucket against the 15-min cells under it, a metrics window against another
// window or against readings, or two class filters. Every coarser number is
// the sum of the published 15-min cells beneath it (src/lib/privacy.ts).

import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";
import { ROAD_USER_CLASSES } from "@/lib/types";
import { attackAggregation } from "./recoverability";

describe("mock week: no hidden cell is recoverable across aggregation levels", () => {
  it("differences every pair of levels, windows and class filters", async () => {
    const now = await mockStreetsRepo.now();
    const from = new Date(now.getTime() - 7 * 24 * 60 * 60_000);
    const report = await attackAggregation(mockStreetsRepo, "dublin", from, now, now);
    console.info(
      `aggregation attack (mock week): ${report.pairs} differences, ` +
        `${report.targets} hidden cells under published numbers, ` +
        `${report.leaks.length} informative, ${report.recovered.length} recovered`
    );
    // Not vacuous: there are hidden cells under coarser published numbers.
    expect(report.targets).toBeGreaterThan(0);
    expect(report.recovered.filter((cell) => cell.includes("e-scooter 2026-04-20T14"))).toEqual([]);
    expect(report.recovered.slice(0, 5)).toEqual([]);
    expect(report.recovered).toHaveLength(0);
    expect(report.leaks.slice(0, 5)).toEqual([]);
    expect(report.leaks).toHaveLength(0);
  }, 60_000);
});

describe("mock week: coarser speeds average published 15-min speeds only", () => {
  it("every hourly and daily mean lies within the published 15-min means under it", async () => {
    const now = await mockStreetsRepo.now();
    const from = new Date(now.getTime() - 7 * 24 * 60 * 60_000);
    let checked = 0;
    for (const { id } of await mockStreetsRepo.list("dublin")) {
      const grid = await mockStreetsRepo.readings({ streetId: id, from, to: now, bucketMinutes: 15 });
      for (const bucketMinutes of [60, 1440]) {
        const rows = await mockStreetsRepo.readings({ streetId: id, from, to: now, bucketMinutes });
        for (const row of rows) {
          const t0 = new Date(row.bucket).getTime();
          const under = grid.filter((cell) => {
            const t = new Date(cell.bucket).getTime();
            return t >= t0 && t < t0 + bucketMinutes * 60_000;
          });
          for (const cls of ROAD_USER_CLASSES) {
            const speed = row.avgSpeedKmh[cls] ?? null;
            const shown = under
              .map((cell) => cell.avgSpeedKmh[cls] ?? null)
              .filter((s): s is number => s !== null);
            if (shown.length === 0) {
              expect(speed).toBeNull();
              continue;
            }
            expect(speed).not.toBeNull();
            expect(speed!).toBeGreaterThanOrEqual(Math.min(...shown) - 1e-9);
            expect(speed!).toBeLessThanOrEqual(Math.max(...shown) + 1e-9);
            checked += 1;
          }
        }
      }
    }
    expect(checked).toBeGreaterThan(0);
  }, 60_000);
});
