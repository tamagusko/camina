// The initial map view must frame the street data that actually exists.
// Regression: CITY_VIEWS.dublin points at the city centre while every mock
// street is in south Dublin / UCD, so 7 of 8 segments opened off-screen and
// looked like there were no clickable streets at all.
import { describe, expect, it } from "vitest";

import { initialViewBounds } from "@/lib/geo";
import type { StreetSummary } from "@/lib/types";

function streetAt(id: string, lon: number, lat: number): StreetSummary {
  const d = 0.001;
  return {
    id,
    displayName: id,
    geom: {
      type: "MultiLineString",
      coordinates: [[[lon, lat], [lon + d, lat + d]]],
    },
    bbox: {
      type: "Polygon",
      coordinates: [[
        [lon - d, lat - d],
        [lon + d, lat - d],
        [lon + d, lat + d],
        [lon - d, lat + d],
        [lon - d, lat - d],
      ]],
    },
    city: "dublin",
  } as StreetSummary;
}

describe("initialViewBounds", () => {
  it("frames every street when the URL pins no viewport", () => {
    const streets = [
      streetAt("ucd", -6.2224, 53.3025),   // southernmost mock street
      streetAt("leeson", -6.2533, 53.3328), // northernmost mock street
    ];

    const bounds = initialViewBounds(streets, false);

    expect(bounds).not.toBeNull();
    const [[minLon, minLat], [maxLon, maxLat]] = bounds!;
    expect(minLon).toBeLessThanOrEqual(-6.2533);
    expect(maxLon).toBeGreaterThanOrEqual(-6.2224);
    expect(minLat).toBeLessThanOrEqual(53.3025);
    expect(maxLat).toBeGreaterThanOrEqual(53.3328);
  });

  it("yields to a viewport pinned in the URL", () => {
    const streets = [streetAt("ucd", -6.2224, 53.3025)];

    expect(initialViewBounds(streets, true)).toBeNull();
  });

  it("returns null when there are no streets to frame", () => {
    expect(initialViewBounds([], false)).toBeNull();
  });
});
