import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StreetTimeSeries } from "@/components/charts/StreetTimeSeries";

describe("StreetTimeSeries", () => {
  it("replaces the chart with a clear message when no counts are published", () => {
    const html = renderToStaticMarkup(
      createElement(StreetTimeSeries, { readings: [] }),
    );

    expect(html).toContain("No published counts in the last 24 h");
    expect(html).not.toContain("recharts");
  });
});
