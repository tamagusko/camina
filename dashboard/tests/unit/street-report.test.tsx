import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MockBadge, MockNotice } from "@/components/layout/MockBadge";
import { CreditFooter, MAP_CREDIT_HTML, MapCredit } from "@/components/layout/CreditFooter";
import { ReportActions } from "@/components/report/ReportActions";
import { ReportSummary } from "@/components/report/ReportSummary";
import { dataUpdatedAt, shareLinks } from "@/lib/report";
import { ROAD_USER_CLASSES, type StreetReading } from "@/lib/types";

const zeros = Object.fromEntries(ROAD_USER_CLASSES.map((c) => [c, 0])) as StreetReading["counts"];
const row = (bucket: string, counts: Partial<StreetReading["counts"]>, missing = false): StreetReading =>
  ({ bucket, missing, hasHidden: false, counts: { ...zeros, ...counts }, avgSpeedKmh: {} });

describe("data updated", () => {
  it("is the end of the last bucket with published data", () => {
    const readings = [
      row("2026-04-21T12:00:00Z", { car: 10 }),
      row("2026-04-21T12:15:00Z", { car: 8 }),
      row("2026-04-21T12:30:00Z", {}, true),
    ];
    expect(dataUpdatedAt(readings, 15)).toBe("2026-04-21T12:30:00.000Z");
  });
  it("is null when nothing was published", () => {
    expect(dataUpdatedAt([row("2026-04-21T12:30:00Z", {}, true)], 15)).toBeNull();
  });
});

describe("share links", () => {
  it("builds WhatsApp, LinkedIn and email links with the title and URL encoded", () => {
    const links = shareLinks("N11 & Montrose", "https://camina-dublin.vercel.app/dublin/street/n11");
    expect(links.whatsapp).toBe("https://wa.me/?text=N11%20%26%20Montrose%20https%3A%2F%2Fcamina-dublin.vercel.app%2Fdublin%2Fstreet%2Fn11");
    expect(links.linkedin).toBe("https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fcamina-dublin.vercel.app%2Fdublin%2Fstreet%2Fn11");
    expect(links.email).toBe("mailto:?subject=N11%20%26%20Montrose&body=https%3A%2F%2Fcamina-dublin.vercel.app%2Fdublin%2Fstreet%2Fn11");
  });
});

describe("report actions", () => {
  it("offers two labelled icon buttons, hidden when printed", () => {
    const html = renderToStaticMarkup(createElement(ReportActions, { title: "N11" }));
    expect(html).toContain('aria-label="Share"');
    expect(html).toContain('aria-label="Print or save as PDF"');
    expect(html).toContain("print:hidden");
  });
});

describe("report summary", () => {
  it("prints one row per class with data, and only in print", () => {
    const readings = [row("2026-04-21T12:00:00Z", { car: 10, cyclist: 6 }), row("2026-04-21T12:15:00Z", { car: 20 })];
    const html = renderToStaticMarkup(createElement(ReportSummary, { readings }));
    expect(html).toMatch(/class="[^"]*\bhidden\b[^"]*print:table/);
    expect(html).toMatch(/Car<\/td><td[^>]*>30<\/td>/);
    expect(html).toMatch(/Cyclist<\/td><td[^>]*>6<\/td>/);
    expect(html).not.toContain(">Bus</td>");
  });
});

describe("mock notice", () => {
  const sentence = "Mock data: simulated values to demonstrate the dashboard, not actual counts.";
  it("says plainly that the values are simulated", () => {
    expect(renderToStaticMarkup(createElement(MockNotice))).toContain(sentence);
  });
  it("gives the badge the same sentence as its tooltip", () => {
    expect(renderToStaticMarkup(createElement(MockBadge))).toContain(`title="${sentence}"`);
  });
});

describe("credit footer", () => {
  it("names the author, links the email and the issue tracker", () => {
    const html = renderToStaticMarkup(createElement(CreditFooter));
    expect(html).toContain("Tiago Tamagusko");
    expect(html).toContain('href="mailto:tamagusko@gmail.com"');
    expect(html).toMatch(/href="https:\/\/github.com\/tamagusko\/camina\/issues"[^>]*>\s*Report a problem/);
  });
  it("spells out the issue link in print, where it cannot be clicked", () => {
    const html = renderToStaticMarkup(createElement(CreditFooter));
    expect(html).toMatch(/Report a problem<span class="hidden print:inline">: github.com\/tamagusko\/camina\/issues<\/span>/);
  });
});

describe("links in the printed report", () => {
  it("underlines the email and issue links so they read as clickable", () => {
    const html = renderToStaticMarkup(createElement(CreditFooter));
    expect(html.match(/<a [^>]*print:underline/g)).toHaveLength(2);
  });
});

describe("map credit", () => {
  it("fits the map's attribution line: name to email, and the issue tracker", () => {
    expect(MAP_CREDIT_HTML).toBe('<a href="mailto:tamagusko@gmail.com">Tiago Tamagusko</a> · <a href="https://github.com/tamagusko/camina/issues" target="_blank" rel="noopener noreferrer">Report a problem</a>');
    expect(renderToStaticMarkup(createElement(MapCredit))).toContain('href="mailto:tamagusko@gmail.com">Tiago Tamagusko</a>');
  });
});
