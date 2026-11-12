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
  it("does not guess inside the open top bin", () => {
    expect(countAtOrAbove(hist({ 120: 10 }), 120)).toBe(10);
    expect(countAtOrAbove(hist({ 120: 10 }), 130)).toBeNull();
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

describe("complementary suppression of the split", () => {
  const car = (hour: number | null, bins: Record<number, number>, dow: number | null = null): SpeedFold =>
    ({ cls: "car", hour, dow, hist: hist(bins), speedSum: 0, speedCount: 0 });

  it("hides a second hour when one hour alone is hidden", () => {
    // 08:00 has 3 above: hidden. Without a partner, the window's 13 above
    // minus 07:00's 10 would give those 3 away.
    const folds = [
      car(null, { 28: 40, 34: 13 }),
      car(7, { 28: 20, 34: 10 }),
      car(8, { 28: 20, 34: 3 }),
    ];
    const r = speedResult(folds, "motor", 30);
    expect(r.focus.overLimit).toBe(13);
    expect(r.byHour[8]?.overLimit).toBeNull();
    expect(r.byHour[7]?.overLimit).toBeNull();
    expect(r.byHour[7]?.timed).toBe(30); // the total stays
  });

  it("leaves the other hours alone when the hidden ones pass together", () => {
    const folds = [
      car(null, { 28: 150, 34: 16 }),
      car(6, { 28: 50, 34: 3 }),
      car(7, { 28: 50, 34: 3 }),
      car(8, { 28: 50, 34: 10 }),
    ];
    const r = speedResult(folds, "motor", 30);
    // 06:00 and 07:00 together have 6 above: enough, so 08:00 is shown.
    expect([r.byHour[6]?.overLimit, r.byHour[7]?.overLimit, r.byHour[8]?.overLimit]).toEqual([null, null, 10]);
  });

  it("protects a motor class against all motor vehicles, whatever the focus", () => {
    const folds: SpeedFold[] = [
      { cls: "car", hour: null, hist: hist({ 28: 20, 34: 10 }), speedSum: 0, speedCount: 0 },
      { cls: "bus", hour: null, hist: hist({ 28: 20, 34: 2 }), speedSum: 0, speedCount: 0 },
    ];
    expect(speedResult(folds, "car", 30).byClass.car?.overLimit).toBeNull();
    expect(speedResult(folds, "motor", 30).focus.overLimit).toBe(12);
  });

  it("splits an hour by weekday for the week, protected within the hour", () => {
    const folds = [
      car(null, { 28: 40, 34: 13 }),
      car(8, { 28: 40, 34: 13 }),
      car(8, { 28: 20, 34: 10 }, 0),
      car(8, { 28: 20, 34: 3 }, 1),
    ];
    const r = speedResult(folds, "motor", 30);
    expect(r.week).toHaveLength(7);
    expect(r.week[0]).toHaveLength(24);
    expect(r.byHour[8]?.overLimit).toBe(13);
    expect(r.week[1]![8]!.overLimit).toBeNull();
    expect(r.week[0]![8]!.overLimit).toBeNull(); // its partner
    expect(r.week[2]![8]!.timed).toBeNull();
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

  it("fills most of a typical week over 30 days on a busy road", async () => {
    const r = await mockStreetsRepo.speeds({ streetId: "leeson-st-lower", window: "30d", focus: "motor", limitKmh: 30 });
    const shown = r.week.flat().filter((f) => f.overLimitShare !== null).length;
    expect(shown).toBeGreaterThan(7 * 24 * 0.6);
  });

  it("gives every street its OpenStreetMap limit", async () => {
    const streets = await mockStreetsRepo.list("dublin");
    expect(streets.every((s) => s.speedLimitKmh !== null)).toBe(true);
    expect((await mockStreetsRepo.get("leeson-st-lower"))?.speedLimitKmh).toBe(30);
  });
});

describe("mock repo online", () => {
  it("reports the hours a sensor was up, and an outage as a gap", async () => {
    const steady = await mockStreetsRepo.online({ streetId: "ranelagh-rd", window: "7d" });
    const cut = await mockStreetsRepo.online({ streetId: "leeson-st-lower", window: "7d" });
    expect(steady.cells).toBe(7 * 96);
    expect(steady.onlineCells / steady.cells).toBeGreaterThan(0.95);
    // Leeson Street Lower's sensor was down for six hours (the mock's outage).
    expect(steady.onlineCells - cut.onlineCells).toBeGreaterThanOrEqual(6 * 4 - 8);
    expect(cut.byHour.reduce((s, n) => s + n, 0)).toBe(cut.onlineCells);
  });

  it("counts no hours before the data began", async () => {
    const month = await mockStreetsRepo.online({ streetId: "ranelagh-rd", window: "30d" });
    expect(month.cells).toBe(30 * 96);
    expect(month.onlineCells).toBeLessThanOrEqual(21 * 96); // 21 days of mock data
  });
});
