import { describe, expect, it } from "vitest";
import { buildDailyMismatch } from "@/lib/reconcile-daily";

describe("buildDailyMismatch", () => {
  it("returns null when class totals and window count match", () => {
    expect(
      buildDailyMismatch(
        { car: 12, cyclist: 3 },
        { car: 12, cyclist: 3 },
        96,
        96
      )
    ).toBeNull();
  });

  it("records missing and differing classes plus the window-count mismatch", () => {
    expect(
      buildDailyMismatch(
        { car: 12, cyclist: 3 },
        { car: 10, pedestrian: 2 },
        95,
        96
      )
    ).toEqual({
      classes: {
        car: { daily: 12, windows: 10, difference: -2 },
        cyclist: { daily: 3, windows: 0, difference: -3 },
        pedestrian: { daily: 0, windows: 2, difference: 2 },
      },
      windowCount: { daily: 96, windows: 95, difference: -1 },
    });
  });
});
