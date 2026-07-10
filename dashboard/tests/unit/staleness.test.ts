// Silent-sensor staleness — binding. A sensor that stopped reporting must not
// paint as a quiet street: streets go `stale` once no reading has landed for
// more than two 15-min windows (> 30 min), and carry a `lastSeen` timestamp.

import { describe, expect, it } from "vitest";
import {
  STALE_AFTER_MS,
  isStale,
  mockStreetsRepo,
} from "@/lib/repo/streets-mock";

describe("isStale — > 2 windows (> 30 min) without a reading", () => {
  const now = new Date("2026-04-21T00:00:00Z");
  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();
  const MIN = 60_000;

  it("threshold is two 15-min windows", () => {
    expect(STALE_AFTER_MS).toBe(30 * MIN);
  });

  it("fresh reading (now) is not stale", () => {
    expect(isStale(ago(0), now)).toBe(false);
  });

  it("one window ago (15 min) is not stale", () => {
    expect(isStale(ago(15 * MIN), now)).toBe(false);
  });

  it("exactly two windows (30 min) is not yet stale", () => {
    expect(isStale(ago(30 * MIN), now)).toBe(false);
  });

  it("just past two windows (30 min + 1 ms) is stale", () => {
    expect(isStale(ago(30 * MIN + 1), now)).toBe(true);
  });

  it("well past the window (45 min) is stale", () => {
    expect(isStale(ago(45 * MIN), now)).toBe(true);
  });

  it("never seen (null lastSeen) is stale", () => {
    expect(isStale(null, now)).toBe(true);
  });
});

describe("latestMetrics — surfaces staleness on every street", () => {
  it("each metric row carries a boolean `stale` and a `lastSeen` field", async () => {
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "24h",
    });
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(typeof row.stale).toBe("boolean");
      expect(row).toHaveProperty("lastSeen");
      if (row.lastSeen !== null) {
        expect(Number.isNaN(new Date(row.lastSeen).getTime())).toBe(false);
      }
    }
  });

  it("a live street (reporting up to the data end) is not stale", async () => {
    // In mock mode `now` is the most recent window in the fixtures, so a street
    // still reporting at the data end must not be flagged stale.
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "24h",
    });
    const live = rows.find((r) => r.lastSeen !== null && !r.stale);
    expect(live).toBeDefined();
  });
});

describe("latestMetrics — totalCount is the true all-class total", () => {
  it("includes suppressed classes (>= visible sum) and stays k-floored", async () => {
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "24h",
    });
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      // k-floor: never a re-identifiable small total.
      if (row.totalCount !== null) {
        expect(row.totalCount === 0 || row.totalCount >= 5).toBe(true);
        // True total covers every class, so it is >= the sum of the
        // visible (non-suppressed) per-class counts.
        const visibleSum = Object.values(row.classBreakdown).reduce<number>(
          (a, b) => a + (b ?? 0),
          0
        );
        expect(row.totalCount).toBeGreaterThanOrEqual(visibleSum);
      }
    }
  });

  it("exceeds the visible sum on at least one street with suppressed classes", async () => {
    // Short window keeps per-class sums small enough for the k-floor to bite.
    const rows = await mockStreetsRepo.latestMetrics({
      city: "dublin",
      metric: "counts",
      window: "1h",
    });
    const withSuppressed = rows.filter(
      (r) =>
        r.totalCount !== null &&
        Object.values(r.classBreakdown).some((v) => v === null)
    );
    // Non-vacuous: the fixtures' quiet hour has low-count classes somewhere.
    expect(withSuppressed.length).toBeGreaterThan(0);
    const strict = withSuppressed.some((r) => {
      const visibleSum = Object.values(r.classBreakdown).reduce<number>(
        (a, b) => a + (b ?? 0),
        0
      );
      return (r.totalCount as number) > visibleSum;
    });
    expect(strict).toBe(true);
  });
});
