// Speeds against a limit (src/lib/speed.ts): counts above it from summed
// histograms of published cells, k-floored on both sides of the split.
import { describe, expect, it } from "vitest";
import { SPEED_BIN_EDGES, emptyHistogram } from "@/lib/privacy";
import { countAtOrAbove, speedFigures, speedResult, type SpeedFold } from "@/lib/speed";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";

// Keyed by a bin's lower edge in km/h.
function hist(bins: Record<number, number>): number[] {
  const h = emptyHistogram();
  for (const [edge, n] of Object.entries(bins)) h[SPEED_BIN_EDGES.indexOf(Number(edge))] = n;
  return h;
}

describe("countAtOrAbove", () => {
  it("counts whole bins from a limit that is a bin edge", () => {
    expect(countAtOrAbove(hist({ 28: 10, 30: 6, 44: 4 }), 30)).toBe(10);
    expect(countAtOrAbove(hist({ 28: 10, 30: 6, 44: 4 }), 40)).toBe(4);
  });
  it("takes a linear share of the bin a limit falls inside", () => {
    // [20, 22) holds 10; 21 is half-way.
    expect(countAtOrAbove(hist({ 20: 10 }), 21)).toBe(5);
  });
});

describe("speedFigures", () => {
  it("publishes the share above the limit", () => {
    const f = speedFigures(hist({ 28: 15, 34: 5 }), 20 * 29.5, 20, 30);
    expect(f.timed).toBe(20);
    expect(f.overLimit).toBe(5);
    expect(f.overLimitShare).toBeCloseTo(0.25);
    expect(f.overBy10).toBe(0);
  });

  it("hides a split whose smaller side counts 1 to 4 road users", () => {
    // 3 above 30 km/h: three people. Hidden, and so is its share.
    const few = speedFigures(hist({ 28: 17, 34: 3 }), 0, 0, 30);
    expect(few.overLimit).toBeNull();
    expect(few.overLimitShare).toBeNull();
    // 3 below: the rest above would give those three away.
    expect(speedFigures(hist({ 28: 3, 34: 17 }), 0, 0, 30).overLimit).toBeNull();
    // Nobody above, or everybody: nothing to single out.
    expect(speedFigures(hist({ 28: 20 }), 0, 0, 30).overLimit).toBe(0);
  });

  it("publishes nothing under K_MIN timed road users", () => {
    const f = speedFigures(hist({ 40: 4 }), 160, 4, 30);
    expect([f.timed, f.meanKmh, f.v85Kmh, f.overLimit]).toEqual([null, null, null, null]);
  });

  it("has no share without a limit", () => {
    expect(speedFigures(hist({ 28: 20 }), 560, 20, null).overLimit).toBeNull();
  });
});

describe("speedResult", () => {
  it("pools the motor classes for the focus and splits by hour", () => {
    const folds: SpeedFold[] = [
      { cls: "car", hour: null, hist: hist({ 28: 10 }), speedSum: 290, speedCount: 10 },
      { cls: "bus", hour: null, hist: hist({ 34: 10 }), speedSum: 345, speedCount: 10 },
      { cls: "cyclist", hour: null, hist: hist({ 40: 10 }), speedSum: 405, speedCount: 10 },
      { cls: "car", hour: 8, hist: hist({ 28: 10 }), speedSum: 290, speedCount: 10 },
    ];
    const r = speedResult(folds, "motor", 30);
    expect(r.focus.timed).toBe(20); // cyclists are not motor traffic
    expect(r.focus.overLimit).toBe(10);
    expect(r.byClass.cyclist?.timed).toBe(10);
    expect(r.byHour[8]?.overLimit).toBe(0);
    expect(r.byHour[9]?.timed).toBeNull();
  });
});

describe("mock repo speeds", () => {
  it("finds more cars above the limit on a 30 km/h road than on a 60 km/h one", async () => {
    const thirty = await mockStreetsRepo.speeds({ streetId: "leeson-st-lower", window: "7d", focus: "car", limitKmh: 30 });
    const sixty = await mockStreetsRepo.speeds({ streetId: "ucd-n11-belfield-flyover", window: "7d", focus: "car", limitKmh: 60 });
    expect(thirty.focus.overLimitShare!).toBeGreaterThan(0.1);
    expect(sixty.focus.overLimitShare!).toBeLessThan(0.1);
    expect(thirty.byHour.filter((h) => h.timed !== null).length).toBeGreaterThan(12);
  });

  it("gives every street its OpenStreetMap limit", async () => {
    const streets = await mockStreetsRepo.list("dublin");
    expect(streets.every((s) => s.speedLimitKmh !== null)).toBe(true);
    expect((await mockStreetsRepo.get("leeson-st-lower"))?.speedLimitKmh).toBe(30);
  });
});
