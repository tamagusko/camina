import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StreetSidePanel } from "@/components/panels/StreetSidePanel";
import { ROAD_USER_CLASSES, type MetricValue, type StreetReading, type StreetSummary } from "@/lib/types";

const zeros = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<(typeof ROAD_USER_CLASSES)[number], number>;
const street: StreetSummary = { id: "test", displayName: "Test Road", city: "dublin", geom: { type: "MultiLineString", coordinates: [[[-6.3, 53.3], [-6.2, 53.4]]] }, bbox: { type: "Polygon", coordinates: [[[-6.3, 53.3], [-6.2, 53.3], [-6.2, 53.4], [-6.3, 53.3]]] } };
const metric: MetricValue = { streetId: "test", value: 10, totalCount: 10, hasHidden: true, classBreakdown: { ...zeros, person: null, car: 10 }, speedBreakdown: {}, avgSpeedKmh: null, stale: false, lastSeen: "2026-09-26T13:30:00Z" };
const reading: StreetReading = { bucket: "2026-09-26T13:15:00Z", missing: false, counts: { ...zeros, person: null, car: 10 }, avgSpeedKmh: {}, countsByDirection: { AB: { ...zeros, person: null, car: 6 }, BA: { ...zeros, person: 0, car: null } } };

describe("street panel states", () => {
  it("renders direction cells and suppressed counts without small numbers", () => {
    const html = renderToStaticMarkup(<StreetSidePanel street={street} metric={metric} reading={reading} onClose={() => {}} />);
    expect(html).toContain("Test Road");
    // Published sum only, one footnote, no "<5" / ">=" cells, hidden-only rows omitted.
    expect(html).toContain("Some values under 5 are hidden.");
    expect(html).not.toContain("&lt;5");
    expect(html).not.toContain("≥");
    expect(html).not.toContain(">person<");
    expect(html).toMatch(/Total count<\/p><p[^>]*>10</);
    expect(html).toContain("→ NE");
    expect(html).toContain("→ SW");
    expect(html).toContain("Detailed view");
  });

  it("distinguishes stale from never reported", () => {
    const stale = renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...metric, stale: true }} onClose={() => {}} />);
    const never = renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...metric, lastSeen: null, stale: true }} onClose={() => {}} />);
    expect(stale).toContain("No recent data");
    expect(stale).toContain("last seen");
    expect(never).toContain("No data yet");
  });
});
