import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StreetTimeSeries } from "@/components/charts/StreetTimeSeries";
import { ROAD_USER_CLASSES, type StreetReading } from "@/lib/types";

describe("StreetTimeSeries", () => {
  it("replaces the chart with a clear message when no counts are published", () => {
    const html = renderToStaticMarkup(
      createElement(StreetTimeSeries, { readings: [] }),
    );

    expect(html).toContain("No published counts in the last 24 h");
    expect(html).not.toContain("recharts");
  });
  it("treats gap-filled and fully suppressed buckets as empty", () => {
    const counts = Object.fromEntries(ROAD_USER_CLASSES.map((cls) => [cls, null])) as StreetReading["counts"];
    const readings: StreetReading[] = [
      { bucket: "2026-09-26T00:00:00Z", missing: true, hasHidden: false, counts, avgSpeedKmh: {} },
      { bucket: "2026-09-26T00:15:00Z", missing: false, hasHidden: true, counts, avgSpeedKmh: {} },
    ];
    const html = renderToStaticMarkup(createElement(StreetTimeSeries, { readings }));
    expect(html).toContain("No published counts in the last 24 h");
    expect(html).not.toContain("recharts");
  });
  it("starts on All, as the first class chip, already selected", () => {
    const counts = Object.fromEntries(ROAD_USER_CLASSES.map((cls) => [cls, 0])) as StreetReading["counts"];
    const readings: StreetReading[] = [
      { bucket: "2026-09-26T00:00:00Z", missing: false, hasHidden: false, counts: { ...counts, car: 12 }, avgSpeedKmh: {} },
    ];
    const html = renderToStaticMarkup(createElement(StreetTimeSeries, { readings }));
    expect(html).toMatch(/aria-label="Classes"><li><button[^>]*aria-pressed="true"[^>]*>All<\/button>/);
    expect(html).toMatch(/aria-pressed="false"[^>]*>.*Car<\/button>/);
    expect(html).not.toContain("All classes");
  });
});
