import { describe, expect, it } from "vitest";

import { typicalDay } from "@/lib/typical-day";
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "@/lib/types";

function hour(iso: string, car: number | null, missing = false): StreetReading {
  const counts = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<RoadUserClass, number | null>;
  counts.car = car;
  counts.person = car === null ? null : 1;
  return { bucket: iso, missing, hasHidden: false, counts, avgSpeedKmh: {} };
}

describe("typicalDay", () => {
  // 2026-09-21 is a Monday, 2026-09-26 a Saturday. Dublin is UTC+1 in September.
  it("averages each Dublin hour over weekdays and weekends separately", () => {
    const rows = [
      hour("2026-09-21T07:00:00Z", 10), // Mon 08:00 Dublin
      hour("2026-09-22T07:00:00Z", 20), // Tue 08:00
      hour("2026-09-26T07:00:00Z", 4), //  Sat 08:00
    ];
    const day = typicalDay(rows, "car");
    expect(day).toHaveLength(24);
    expect(day[8]).toEqual({ hour: 8, weekday: 15, weekend: 4 });
    expect(day[9]).toEqual({ hour: 9, weekday: null, weekend: null });
  });

  it("sums every class when none is selected", () => {
    const day = typicalDay([hour("2026-09-21T07:00:00Z", 10)], null);
    expect(day[8]!.weekday).toBe(11);
  });

  it("leaves out offline hours and hidden values", () => {
    const rows = [
      hour("2026-09-21T07:00:00Z", 10),
      hour("2026-09-22T07:00:00Z", null),
      hour("2026-09-23T07:00:00Z", 0, true),
    ];
    expect(typicalDay(rows, "car")[8]!.weekday).toBe(10);
  });
});
