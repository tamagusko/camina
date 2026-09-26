import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ColourLegend } from "@/components/map/ColourLegend";
import { rampExpression, streetPaintStatus, VIRIDIS_5 } from "@/lib/geo";
import { ROAD_USER_CLASSES, type MetricValue } from "@/lib/types";

const zeros = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as MetricValue["classBreakdown"];
const metric: MetricValue = { streetId: "test", value: 12, totalCount: 12, hasHidden: false, classBreakdown: zeros, speedBreakdown: {}, avgSpeedKmh: null, stale: false, lastSeen: "2026-09-26T13:30:00Z" };

describe("fixed map legend", () => {
  it("uses fixed count thresholds and a readable text equivalent", () => {
    expect(rampExpression(VIRIDIS_5, "counts")).toEqual(["step", expect.any(Array), VIRIDIS_5[0], 25, VIRIDIS_5[1], 75, VIRIDIS_5[2], 200, VIRIDIS_5[3], 500, VIRIDIS_5[4]]);
    const html = renderToStaticMarkup(<ColourLegend metric="counts" />);
    expect(html).toContain("Road users per 15 min");
    expect(html).toContain("5–24");
    expect(html).toContain("500+");
    expect(html).toContain("No recent data");
    expect(html).toContain("Suppressed");
  });
  it("keeps suppressed totals solid and stale streets separate", () => {
    expect(streetPaintStatus(metric)).toBe("live");
    expect(streetPaintStatus({ ...metric, value: null })).toBe("suppressed");
    expect(streetPaintStatus({ ...metric, value: 0, totalCount: 0, hasHidden: true })).toBe("suppressed");
    expect(streetPaintStatus({ ...metric, value: 0, totalCount: 0 })).toBe("live");
    expect(streetPaintStatus({ ...metric, stale: true })).toBe("stale");
    expect(streetPaintStatus({ ...metric, lastSeen: null })).toBe("stale");
    expect(streetPaintStatus(undefined)).toBe("stale");
  });
});
