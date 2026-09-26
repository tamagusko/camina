// Complementary suppression — binding. No suppressed value (1..4) may be
// recoverable by subtraction from other values in the same public response:
// class count vs its AB/BA cells, and street total vs its per-class values.

import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";
import { K_MIN, publishDirectionPair, publishedTotal, suppressCount } from "@/lib/privacy";
import {
  ROAD_USER_CLASSES,
  type MetricValue,
  type RoadUserClass,
  type StreetReading,
  type TimeWindow,
} from "@/lib/types";
import { metricLeaks, readingLeaks } from "./recoverability";

describe("adversary sanity — the checker catches the leaky shapes", () => {
  it("flags count 6 / AB 5 / BA hidden", () => {
    const counts = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<
      RoadUserClass,
      number | null
    >;
    const row: StreetReading = {
      bucket: "2026-04-20T00:00:00.000Z",
      missing: false,
      counts: { ...counts, cyclist: 6 },
      avgSpeedKmh: {},
      countsByDirection: { AB: { ...counts, cyclist: 5 }, BA: { ...counts, cyclist: null } },
    };
    expect(readingLeaks([row])).toEqual(["2026-04-20T00:00:00.000Z cyclist BA=1"]);
  });

  it("flags a true total next to one hidden class", () => {
    const breakdown = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<
      RoadUserClass,
      number | null
    >;
    const row: MetricValue = {
      streetId: "s", value: 12, totalCount: 12, hasHidden: true,
      classBreakdown: { ...breakdown, car: 10, cyclist: null },
      speedBreakdown: {}, avgSpeedKmh: null, stale: false, lastSeen: null,
    };
    expect(metricLeaks([row], "counts").length).toBeGreaterThan(0);
  });
});

describe("publication rules", () => {
  it("hides a direction pair together when either cell is 1..4", () => {
    expect(publishDirectionPair(5, 1, true)).toEqual({ AB: null, BA: null });
    expect(publishDirectionPair(3, 0, true)).toEqual({ AB: null, BA: null });
    expect(publishDirectionPair(5, 0, true)).toEqual({ AB: 5, BA: 0 });
    expect(publishDirectionPair(7, 9, true)).toEqual({ AB: 7, BA: 9 });
  });

  it("hides a direction pair that does not cover every row of the class", () => {
    expect(publishDirectionPair(5, 0, false)).toEqual({ AB: null, BA: null });
  });

  it("publishes a total as the sum of published cells, flagged when partial", () => {
    expect(publishedTotal([10, null, 0])).toEqual({ total: 10, hasHidden: true });
    expect(publishedTotal([10, 5])).toEqual({ total: 15, hasHidden: false });
    expect(publishedTotal([null, 0])).toEqual({ total: 0, hasHidden: true });
    expect(publishedTotal([0, 0])).toEqual({ total: 0, hasHidden: false });
  });

  it("random buckets: no suppressed value is recoverable", () => {
    // Deterministic LCG so a failure is reproducible.
    let seed = 20260926;
    const rand = (n: number) => {
      seed = (seed * 1_103_515_245 + 12_345) % 2 ** 31;
      return seed % n;
    };
    for (let i = 0; i < 2000; i++) {
      const counts = {} as Record<RoadUserClass, number | null>;
      const ab = {} as Record<RoadUserClass, number | null>;
      const ba = {} as Record<RoadUserClass, number | null>;
      const breakdown: (number | null)[] = [];
      for (const cls of ROAD_USER_CLASSES) {
        const a = rand(9);
        const b = rand(3) === 0 ? rand(40) : rand(6);
        const complete = rand(10) !== 0;
        // An incomplete class has extra non-directional traffic on top of AB+BA.
        const count = a + b + (complete ? 0 : 1 + rand(4));
        counts[cls] = suppressCount(count);
        const pair = publishDirectionPair(a, b, complete);
        ab[cls] = pair.AB;
        ba[cls] = pair.BA;
        breakdown.push(counts[cls]);
      }
      const row: StreetReading = {
        bucket: `r${i}`, missing: false, counts, avgSpeedKmh: {},
        countsByDirection: { AB: ab, BA: ba },
      };
      expect(readingLeaks([row])).toEqual([]);
      const { total, hasHidden } = publishedTotal(breakdown);
      const metric: MetricValue = {
        streetId: `s${i}`, value: total, totalCount: total, hasHidden,
        classBreakdown: counts, speedBreakdown: {}, avgSpeedKmh: null,
        stale: false, lastSeen: null,
      };
      expect(metricLeaks([metric], "counts")).toEqual([]);
    }
    expect(K_MIN).toBe(5);
  });
});

describe("mock adapter over the one-day fixture", () => {
  const from = new Date("2026-04-20T00:00:00Z");
  const to = new Date("2026-04-21T00:00:00Z");

  it("readings: no suppressed value is recoverable at any bucket size", async () => {
    const streets = await mockStreetsRepo.list("dublin");
    let directional = 0;
    for (const street of streets) {
      for (const bucketMinutes of [15, 60, 1440]) {
        const rows = await mockStreetsRepo.readings({
          streetId: street.id, from, to, bucketMinutes,
        });
        directional += rows.filter((r) => r.countsByDirection && !r.missing).length;
        expect(readingLeaks(rows)).toEqual([]);
      }
    }
    expect(directional).toBeGreaterThan(0);
  });

  it("metrics: totals add nothing beyond the published class values", async () => {
    let partial = 0;
    for (const window of ["now", "1h", "24h", "7d", "30d"] as TimeWindow[]) {
      for (const metric of ["counts", "speed"] as const) {
        for (const classes of [undefined, ["car", "cyclist"] as RoadUserClass[]]) {
          const rows = await mockStreetsRepo.latestMetrics({ city: "dublin", metric, classes, window });
          partial += rows.filter((r) => r.hasHidden).length;
          expect(metricLeaks(rows, metric)).toEqual([]);
        }
      }
    }
    expect(partial).toBeGreaterThan(0);
  });
});
