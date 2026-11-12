// Every metrics window ends at the last completed 15-min cell before `now`
// (src/lib/repo/streets-mock.ts lastCompletedCellEnd), as the live adapter's
// SQL does. Readings after that cell must not count.
import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";
import { ROAD_USER_CLASSES } from "@/lib/types";

describe("mock latestMetrics — window end", () => {
  it("leaves out readings after the last completed cell, like the live adapter", async () => {
    // Mid-way through the mock data, so readings exist after `now`.
    const now = new Date("2026-04-20T12:07:00Z");
    const end = new Date("2026-04-20T12:00:00Z");
    const from = new Date("2026-04-20T11:00:00Z");
    const metrics = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "counts", window: "1h", now });
    for (const row of metrics) {
      const readings = await mockStreetsRepo.readings({ streetId: row.streetId, from, to: end, bucketMinutes: 60 });
      const expected = ROAD_USER_CLASSES.reduce((sum, cls) => sum + (readings[0]!.counts[cls] ?? 0), 0);
      expect(row.totalCount, row.streetId).toBe(expected);
    }
  });
});
