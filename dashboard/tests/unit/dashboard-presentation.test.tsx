import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StreetSidePanel } from "@/components/panels/StreetSidePanel";
import { ROAD_USER_CLASSES, classLabel, type MetricValue, type StreetReading, type StreetSummary } from "@/lib/types";

const zeros = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as Record<(typeof ROAD_USER_CLASSES)[number], number>;
const street: StreetSummary = { id: "test", displayName: "Test Road", city: "dublin", speedLimitKmh: 50, geom: { type: "MultiLineString", coordinates: [[[-6.3, 53.3], [-6.2, 53.4]]] }, bbox: { type: "Polygon", coordinates: [[[-6.3, 53.3], [-6.2, 53.3], [-6.2, 53.4], [-6.3, 53.3]]] } };
const metric: MetricValue = { streetId: "test", value: 12, totalCount: 12, hasHidden: true, classBreakdown: { ...zeros, person: null, car: 12 }, speedBreakdown: {}, avgSpeedKmh: null, v85Breakdown: {}, v85Kmh: null, stale: false, lastSeen: "2026-09-26T13:30:00Z", typical: null };
const reading: StreetReading = { bucket: "2026-09-26T13:15:00Z", missing: false, hasHidden: true, counts: { ...zeros, person: null, car: 12, bus: 6 }, avgSpeedKmh: {}, v85Kmh: {}, countsByDirection: { AB: { ...zeros, person: null, car: 7, bus: null }, BA: { ...zeros, person: null, car: 5, bus: null } } };

describe("street panel states", () => {
  it("renders direction cells and suppressed counts without small numbers", () => {
    const html = renderToStaticMarkup(<StreetSidePanel street={street} metric={metric} reading={reading} onClose={() => {}} />);
    expect(html).toContain("Test Road");
    // Published sum only, one footnote, no "<5" / ">=" cells, hidden-only rows omitted.
    expect(html).toContain("Some values under 5 are hidden.");
    expect(html).not.toContain("&lt;5");
    expect(html).not.toContain("≥");
    expect(html).not.toContain(">person<");
    expect(html).toMatch(/Road users · last 15 min<\/p><p[^>]*>12</);
    // Tile: plain direction sums, no arrows; the arrows stay in the column headers.
    expect(html).toMatch(/>NE 7 · SW 5</);
    // Every shown row carries its count; a hidden direction pair shows dashes.
    expect(html).toMatch(/>Count<\/th><th[^>]*>→ NE<\/th><th[^>]*>→ SW<\/th><th[^>]*>km\/h</);
    expect(html).toMatch(/>Car<\/th><td[^>]*>12<\/td><td[^>]*>7<\/td><td[^>]*>5</);
    expect(html).toMatch(/>Bus<\/th><td[^>]*>6<\/td><td[^>]*>—<\/td><td[^>]*>—</);
    // Status line carries only freshness; the tile label carries the period.
    expect(html).not.toContain("Latest 15 min");
    expect(html).toContain("→ NE");
    expect(html).toContain("→ SW");
    expect(html).toContain("Detailed view");
  });

  it("shows no direction for a street whose sensor sends none", () => {
    const { countsByDirection: _, ...undirected } = reading;
    const html = renderToStaticMarkup(<StreetSidePanel street={street} metric={metric} reading={undirected} onClose={() => {}} />);
    expect(html).not.toMatch(/→ [NSEW]/);
    expect(html).not.toMatch(/>NE \d/);
    expect(html).toMatch(/>Class<\/th><th[^>]*>Count<\/th><th[^>]*>km\/h</);
    expect(html).toMatch(/>Car<\/th><td[^>]*>12<\/td><td[^>]*>—</);
  });

  it("shows a dash, not 0, when every class is hidden", () => {
    const hiddenAll = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, null])) as StreetReading["counts"];
    const html = renderToStaticMarkup(<StreetSidePanel street={street}
      metric={{ ...metric, value: 0, totalCount: 0, hasHidden: true, classBreakdown: { ...zeros, car: null } }}
      reading={{ ...reading, counts: { ...zeros, car: null }, countsByDirection: { AB: hiddenAll, BA: hiddenAll } }}
      onClose={() => {}} />);
    expect(html).toMatch(/Road users · last 15 min<\/p><p[^>]*>—</);
    expect(html).not.toMatch(/>NE \S+ · SW/);
    expect(html).toContain("Some values under 5 are hidden.");
  });

  it("keeps a true 0 as 0", () => {
    const html = renderToStaticMarkup(<StreetSidePanel street={street}
      metric={{ ...metric, value: 0, totalCount: 0, hasHidden: false, classBreakdown: zeros }}
      reading={{ ...reading, hasHidden: false, counts: zeros, countsByDirection: { AB: zeros, BA: zeros } }}
      onClose={() => {}} />);
    expect(html).toMatch(/Road users · last 15 min<\/p><p[^>]*>0</);
    expect(html).toMatch(/>NE 0 · SW 0</);
  });

  it("spells classes the same way everywhere", () => {
    expect(ROAD_USER_CLASSES.map(classLabel)).toEqual([
      "Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery van", "Truck",
    ]);
  });

  it("distinguishes stale from never reported", () => {
    const stale = renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...metric, stale: true }} onClose={() => {}} />);
    const never = renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...metric, lastSeen: null, stale: true }} onClose={() => {}} />);
    expect(stale).toContain("No recent data");
    expect(stale).toContain("last seen");
    expect(never).toContain("No data yet");
  });
  it("says in words how busy the street is compared with usual", () => {
    const busy = { ...metric, totalCount: 150, value: 150, hasHidden: false, typical: 100 };
    expect(renderToStaticMarkup(<StreetSidePanel street={street} metric={busy} onClose={() => {}} />)).toContain("Busier than usual");
    expect(renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...busy, typical: 150 }} onClose={() => {}} />)).toContain("About usual for this time");
    expect(renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...busy, stale: true }} onClose={() => {}} />)).not.toContain("usual");
    expect(renderToStaticMarkup(<StreetSidePanel street={street} metric={{ ...busy, typical: null }} onClose={() => {}} />)).not.toContain("usual");
  });
  it("puts the class icon beside each class name", () => {
    const html = renderToStaticMarkup(<StreetSidePanel street={street} metric={metric} reading={reading} onClose={() => {}} />);
    expect(html).toMatch(/<th scope="row"[^>]*>(?:(?!<\/th>).)*<svg[^>]*aria-hidden="true"(?:(?!<\/th>).)*Car<\/th>/);
  });
});
