import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ColourLegend } from "@/components/map/ColourLegend";
import { mapColourValue, rampExpression, streetPaintStatus, VIRIDIS_5 } from "@/lib/geo";
import { ROAD_USER_CLASSES, type MetricValue } from "@/lib/types";

const QUIET = "#a8a8a8";
const zeros = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as MetricValue["classBreakdown"];
const metric: MetricValue = { streetId: "test", value: 12, totalCount: 12, hasHidden: false, classBreakdown: zeros, speedBreakdown: {}, avgSpeedKmh: null, stale: false, lastSeen: "2026-09-26T13:30:00Z" };

// Just enough of the MapLibre expression language to evaluate the ramp against
// a feature: step, coalesce, to-number, get, feature-state (always unset here,
// because the map writes the value as a feature property).
type Expr = unknown;
function evaluate(expr: Expr, properties: Record<string, unknown>): unknown {
  if (!Array.isArray(expr)) return expr;
  const [op, ...args] = expr as [string, ...Expr[]];
  switch (op) {
    case "get": return properties[args[0] as string] ?? null;
    case "feature-state": return null;
    case "to-number": { const v = evaluate(args[0], properties); return v === null ? null : Number(v); }
    case "coalesce": return args.map((a) => evaluate(a, properties)).find((v) => v !== null) ?? null;
    case "step": {
      const input = evaluate(args[0], properties) as number;
      let out = args[1];
      for (let i = 2; i < args.length; i += 2) if (input >= (args[i] as number)) out = args[i + 1];
      return out;
    }
    default: throw new Error(`unsupported op ${op}`);
  }
}

describe("map colour ramp", () => {
  it("colours a street by its metric property", () => {
    const counts = rampExpression(VIRIDIS_5, "counts");
    expect(evaluate(counts, { metric: 10 })).toBe(VIRIDIS_5[0]);
    expect(evaluate(counts, { metric: 300 })).toBe(VIRIDIS_5[3]);
    expect(evaluate(counts, { metric: 900 })).toBe(VIRIDIS_5[4]);
    expect(evaluate(rampExpression(VIRIDIS_5, "speed"), { metric: 25 })).toBe(VIRIDIS_5[2]);
  });
  it("paints a published 0 (and a mean under 5) quiet grey, not the 5–24 step", () => {
    const counts = rampExpression(VIRIDIS_5, "counts", QUIET);
    expect(evaluate(counts, { metric: 0 })).toBe(QUIET);
    expect(evaluate(counts, {})).toBe(QUIET);
    expect(evaluate(counts, { metric: 4.9 })).toBe(QUIET);
    expect(evaluate(counts, { metric: 5 })).toBe(VIRIDIS_5[0]);
  });
});

describe("legend stays true in every window", () => {
  it("colours counts by the mean per 15 min", () => {
    expect(mapColourValue(40, "counts", "now")).toBe(40);
    expect(mapColourValue(96 * 40, "counts", "24h")).toBe(40);
    expect(mapColourValue(672 * 300, "counts", "7d")).toBe(300);
    expect(evaluate(rampExpression(VIRIDIS_5, "counts"), { metric: mapColourValue(100_000, "counts", "7d") })).toBe(VIRIDIS_5[2]);
  });
  it("leaves speed alone (already an average)", () => {
    expect(mapColourValue(25, "speed", "7d")).toBe(25);
  });
  it("names the average in the legend title", () => {
    expect(renderToStaticMarkup(<ColourLegend metric="counts" timeWindow="now" />)).toContain("Road users per 15 min</p>");
    expect(renderToStaticMarkup(<ColourLegend metric="counts" timeWindow="24h" />)).toContain("Road users per 15 min · 24 h average");
    expect(renderToStaticMarkup(<ColourLegend metric="counts" timeWindow="7d" />)).toContain("Road users per 15 min · 7 d average");
    expect(renderToStaticMarkup(<ColourLegend metric="speed" timeWindow="7d" />)).toContain("Speed · km/h");
  });
});

describe("fixed map legend", () => {
  it("uses fixed count thresholds and a readable text equivalent", () => {
    expect(rampExpression(VIRIDIS_5, "counts", QUIET)).toEqual(["step", expect.any(Array), QUIET, 5, VIRIDIS_5[0], 25, VIRIDIS_5[1], 75, VIRIDIS_5[2], 200, VIRIDIS_5[3], 500, VIRIDIS_5[4]]);
    const html = renderToStaticMarkup(<ColourLegend metric="counts" />);
    expect(html).toContain("Road users per 15 min");
    // The quiet grey has its own key: under 5 (none, or hidden).
    expect(html).toContain("var(--ink-3)");
    expect(html).toMatch(/>&lt;5</);
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
