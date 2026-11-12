import { describe, expect, it } from "vitest";
import { formatDublinUpdated } from "@/lib/format-time";

describe("formatDublinUpdated", () => {
  it("shows only the time on the same Dublin day", () => {
    expect(formatDublinUpdated("2026-09-26T12:15:00Z", new Date("2026-09-26T20:00:00Z"))).toBe("13:15");
  });
  it("adds the date on another Dublin day", () => {
    expect(formatDublinUpdated("2026-04-21T00:00:00Z", new Date("2026-09-26T20:00:00Z"))).toBe("21 Apr 01:00");
  });
  it("uses the Dublin calendar day, not UTC", () => {
    // 23:30 UTC on 25 Sep is 00:30 on 26 Sep in Dublin (IST).
    expect(formatDublinUpdated("2026-09-25T23:30:00Z", new Date("2026-09-26T10:00:00Z"))).toBe("00:30");
  });
});
