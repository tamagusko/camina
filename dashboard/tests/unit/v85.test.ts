// v85: the 85th-percentile speed, read from summed speed histograms of
// published base cells only (src/lib/privacy.ts).
import { describe, expect, it } from "vitest";
import {
  K_MIN,
  SPEED_BIN_EDGES,
  addRowHistogram,
  emptyFold,
  emptyHistogram,
  emptyRawCell,
  foldCell,
  publishFold,
  v85FromHistogram,
} from "@/lib/privacy";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";

// Keyed by a bin's lower edge in km/h.
function hist(bins: Record<number, number>): number[] {
  const h = emptyHistogram();
  for (const [edge, n] of Object.entries(bins)) h[SPEED_BIN_EDGES.indexOf(Number(edge))] = n;
  return h;
}

describe("v85FromHistogram", () => {
  it("is null under K_MIN timed road users", () => {
    expect(v85FromHistogram(hist({ 30: K_MIN - 1 }))).toBeNull();
    expect(v85FromHistogram(emptyHistogram())).toBeNull();
  });

  it("interpolates inside the bin that holds the 85th percentile", () => {
    // 20 users, all in [30, 32): the 17th of 20 sits 85 % into the bin.
    expect(v85FromHistogram(hist({ 30: 20 }))).toBeCloseTo(31.7);
    // 10 in [20, 22), 10 in [40, 42): target 17 is 7 of 10 into the upper bin.
    expect(v85FromHistogram(hist({ 20: 10, 40: 10 }))).toBeCloseTo(41.4);
  });

  it("keeps a walking v85 at walking speed", () => {
    // 15 at 4 km/h and 5 at 5 km/h: v85 inside [5, 6), not up to 10.
    expect(v85FromHistogram(hist({ 4: 15, 5: 5 }))).toBeCloseTo(5.4);
  });

  it("reads the open last bin as its lower edge, a floor", () => {
    expect(v85FromHistogram(hist({ 120: 10 }))).toBe(120);
  });
});

describe("folding histograms", () => {
  it("leaves out the histogram of a base cell whose speed is hidden", () => {
    const shown = emptyRawCell();
    shown.count = 10; shown.rows = 1; shown.speedSum = 300; shown.speedCount = 10;
    addRowHistogram(shown, hist({ 30: 10 }));
    const hidden = emptyRawCell();
    hidden.count = 3; hidden.rows = 1; hidden.speedSum = 300; hidden.speedCount = 3;
    addRowHistogram(hidden, hist({ 100: 3 })); // would pull v85 up
    const fold = emptyFold();
    foldCell(fold, shown);
    foldCell(fold, hidden);
    expect(publishFold(fold).v85).toBeCloseTo(31.7);
  });
});

describe("mock repo", () => {
  it("publishes a per-class v85 at or above the mean speed on a busy street", async () => {
    const rows = await mockStreetsRepo.latestMetrics({ city: "dublin", metric: "counts", window: "24h" });
    const withCar = rows.filter((row) => row.v85Breakdown.car != null);
    expect(withCar.length).toBeGreaterThan(0);
    for (const row of withCar) {
      expect(row.v85Breakdown.car!).toBeGreaterThanOrEqual(row.speedBreakdown.car!);
    }
  });

  it("gives readings a v85 per class", async () => {
    const [street] = await mockStreetsRepo.list("dublin");
    const to = await mockStreetsRepo.now();
    const readings = await mockStreetsRepo.readings({
      streetId: street!.id, from: new Date(to.getTime() - 24 * 3600_000), to, bucketMinutes: 60,
    });
    expect(readings.some((r) => Object.values(r.v85Kmh).some((v) => v != null))).toBe(true);
  });
});
