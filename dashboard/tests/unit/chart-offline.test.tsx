import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ClassIcon } from "@/components/ClassIcon";
import { offlineRanges } from "@/components/charts/chart-style";
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "@/lib/types";

const counts = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<RoadUserClass, number | null>;
const row = (t: string, missing: boolean): StreetReading => ({ bucket: t, missing, hasHidden: false, counts, avgSpeedKmh: {}, v85Kmh: {} });

describe("offlineRanges", () => {
  it("merges consecutive offline buckets into one band, by x label", () => {
    const rows = [row("a", false), row("b", true), row("c", true), row("d", false), row("e", true)];
    expect(offlineRanges(rows, (r) => r.bucket)).toEqual([["b", "c"], ["e", "e"]]);
  });
  it("has no band when the sensor never went down", () => {
    expect(offlineRanges([row("a", false)], (r) => r.bucket)).toEqual([]);
  });
});

describe("ClassIcon", () => {
  it("draws a decorative icon for every class", () => {
    for (const cls of ROAD_USER_CLASSES) {
      const html = renderToStaticMarkup(<ClassIcon cls={cls} />);
      expect(html, cls).toContain("<svg");
      expect(html, cls).toContain('aria-hidden="true"');
    }
  });
});
