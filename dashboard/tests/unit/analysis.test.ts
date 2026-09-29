// Road analysis figures (src/lib/analysis.ts): published numbers only.
import { describe, expect, it } from "vitest";
import { busiestHour, citySide, difference, hourlyProfile, mean, roadSide } from "@/lib/analysis";
import { ROAD_USER_CLASSES, type MetricValue, type RoadUserClass, type StreetReading } from "@/lib/types";

const zeros = () => Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<RoadUserClass, number | null>;

function metric(id: string, car: number, v85: number | null, hidden = false): MetricValue {
  return {
    streetId: id, value: car, totalCount: car, hasHidden: hidden, classBreakdown: { ...zeros(), car },
    speedBreakdown: { car: v85 === null ? null : v85 - 5 }, avgSpeedKmh: null,
    v85Breakdown: { car: v85 }, v85Kmh: v85, stale: false, lastSeen: null, typical: null,
  };
}

function reading(iso: string, car: number | null, missing = false): StreetReading {
  return { bucket: iso, missing, hasHidden: car === null, counts: { ...zeros(), car }, avgSpeedKmh: {}, v85Kmh: {} };
}

describe("road analysis", () => {
  it("averages each Dublin hour of the day, leaving out hidden and offline hours", () => {
    // 07:00 and 08:00 UTC in March are 07:00 and 08:00 in Dublin.
    const profile = hourlyProfile([
      reading("2026-03-10T07:00:00Z", 10), reading("2026-03-11T07:00:00Z", 20),
      reading("2026-03-10T08:00:00Z", null), reading("2026-03-11T08:00:00Z", 99, true),
    ], "car");
    expect(profile[7]).toBe(15);
    expect(profile[8]).toBeNull();
    expect(busiestHour(profile)).toBe(7);
  });

  it("takes the city average over roads with data only", () => {
    const side = citySide("City", [metric("a", 100, 40), metric("b", 50, null), metric("quiet", 0, null)], "car", [], 24);
    expect(side.total).toBe(75);
    expect(side.v85).toBe(40);
    expect(side.perHour).toBeCloseTo(75 / 24);
  });

  it("shows speeds only for a chosen class", () => {
    expect(roadSide("A", metric("a", 100, 40), null, [], 24).v85).toBeNull();
    expect(roadSide("A", metric("a", 100, 40), "car", [], 24).v85).toBe(40);
    expect(roadSide("A", undefined, "car", [], 24).total).toBeNull();
  });

  it("gives the relative difference, or none", () => {
    expect(difference(120, 100)).toBeCloseTo(0.2);
    expect(difference(1, 0)).toBeNull();
    expect(difference(null, 3)).toBeNull();
    expect(mean([null, undefined])).toBeNull();
  });
});
