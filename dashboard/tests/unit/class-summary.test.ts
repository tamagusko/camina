import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ClassDetail } from "@/components/charts/ClassDetail";
import { classSummary, classesWithData } from "@/lib/class-summary";
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "@/lib/types";

const empty = () =>
  Object.fromEntries(ROAD_USER_CLASSES.map((cls) => [cls, 0])) as Record<RoadUserClass, number | null>;

function reading(bucket: string, car: number | null, extra: Partial<StreetReading> = {}): StreetReading {
  return { bucket, missing: false, hasHidden: car === null, counts: { ...empty(), car }, avgSpeedKmh: {}, ...extra };
}

describe("classSummary", () => {
  it("totals published counts and finds the busiest bucket", () => {
    const s = classSummary(
      [reading("2026-09-26T08:00:00Z", 12), reading("2026-09-26T08:15:00Z", 30), reading("2026-09-26T08:30:00Z", 30)],
      "car",
    );
    expect(s.total).toBe(72);
    expect(s.peak).toEqual({ count: 30, bucket: "2026-09-26T08:15:00Z" });
  });

  it("leaves hidden and missing buckets out of the total", () => {
    const missing: StreetReading = { ...reading("2026-09-26T09:00:00Z", null), missing: true, hasHidden: false };
    const s = classSummary([reading("2026-09-26T08:00:00Z", 10), reading("2026-09-26T08:15:00Z", null), missing], "car");
    expect(s.total).toBe(10);
  });

  it("weights the average speed by the count of each bucket", () => {
    const s = classSummary(
      [
        reading("2026-09-26T08:00:00Z", 10, { avgSpeedKmh: { car: 20 } }),
        reading("2026-09-26T08:15:00Z", 30, { avgSpeedKmh: { car: 40 } }),
        reading("2026-09-26T08:30:00Z", 5, { avgSpeedKmh: { car: null } }),
      ],
      "car",
    );
    expect(s.avgSpeedKmh).toBe(35);
  });

  it("has no speed when none is published", () => {
    expect(classSummary([reading("2026-09-26T08:00:00Z", 10)], "car").avgSpeedKmh).toBeNull();
  });

  it("sums each direction when the sensor sends them, and is null otherwise", () => {
    const split = (ab: number | null, ba: number | null) => ({
      AB: { ...empty(), car: ab },
      BA: { ...empty(), car: ba },
    });
    const s = classSummary(
      [
        reading("2026-09-26T08:00:00Z", 12, { countsByDirection: split(7, 5) }),
        reading("2026-09-26T08:15:00Z", 9, { countsByDirection: split(null, null) }),
      ],
      "car",
    );
    expect(s.byDirection).toEqual({ AB: 7, BA: 5 });
    expect(classSummary([reading("2026-09-26T08:00:00Z", 12)], "car").byDirection).toBeNull();
  });

  it("has no peak when nothing is published", () => {
    expect(classSummary([reading("2026-09-26T08:00:00Z", null)], "car").peak).toBeNull();
  });
});

describe("classesWithData", () => {
  it("lists only classes with a published count above zero, in wire order", () => {
    const r = reading("2026-09-26T08:00:00Z", 12, {});
    r.counts.person = 6;
    r.counts.bus = null;
    expect(classesWithData([r])).toEqual(["person", "car"]);
  });
});

describe("ClassDetail", () => {
  it("shows the class name and its total, with no separate way back (the All chip does that)", () => {
    const html = renderToStaticMarkup(
      createElement(ClassDetail, {
        cls: "car",
        colour: "#0072b2",
        readings: [reading("2026-09-26T08:00:00Z", 12), reading("2026-09-26T08:15:00Z", 30)],
        directions: ["N", "S"],
      }),
    );
    expect(html).toContain("Car");
    expect(html).toContain("42");
    expect(html).not.toContain("All classes");
  });

  it("names the directions when the sensor sends them", () => {
    const html = renderToStaticMarkup(
      createElement(ClassDetail, {
        cls: "car",
        colour: "#0072b2",
        readings: [
          reading("2026-09-26T08:00:00Z", 12, {
            countsByDirection: { AB: { ...empty(), car: 7 }, BA: { ...empty(), car: 5 } },
          }),
        ],
        directions: ["N", "S"],
      }),
    );
    expect(html).toContain("→ N");
    expect(html).toContain("→ S");
  });
});
