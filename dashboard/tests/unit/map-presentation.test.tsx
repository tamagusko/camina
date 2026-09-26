import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ColourLegend } from "@/components/map/ColourLegend";
import { rampExpression, streetPaintStatus, VIRIDIS_5 } from "@/lib/geo";
import { ROAD_USER_CLASSES, type MetricValue } from "@/lib/types";

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
});

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
