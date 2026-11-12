import { describe, expect, it } from "vitest";

import { TYPICAL_MIN_WEEKS, typicalTotal, usualLevel } from "@/lib/typical";

describe("typicalTotal", () => {
  it("scales the past rate per 15-min cell to the cells the current window has", () => {
    // Two past weeks: 400 over 96 cells and 200 over 48 cells → 600 / 144 per cell.
    const t = typicalTotal({ total: 0, cells: 72 }, [
      { total: 400, cells: 96 },
      { total: 200, cells: 48 },
    ]);
    expect(t).toBeCloseTo((600 / 144) * 72);
  });

  it("ignores past weeks with no data at all", () => {
    const t = typicalTotal({ total: 0, cells: 4 }, [
      { total: 40, cells: 4 },
      { total: 0, cells: 0 },
      { total: 60, cells: 4 },
    ]);
    expect(t).toBe(50);
  });

  it(`needs ${TYPICAL_MIN_WEEKS} past weeks with data`, () => {
    expect(typicalTotal({ total: 10, cells: 4 }, [{ total: 40, cells: 4 }, { total: 0, cells: 0 }])).toBeNull();
  });

  it("is null when the current window has no data", () => {
    expect(typicalTotal({ total: 0, cells: 0 }, [{ total: 40, cells: 4 }, { total: 40, cells: 4 }])).toBeNull();
  });
});

describe("usualLevel", () => {
  it("names the level from the ratio to the usual total", () => {
    expect(usualLevel(40, 100)).toBe("much-lower");
    expect(usualLevel(70, 100)).toBe("lower");
    expect(usualLevel(100, 100)).toBe("usual");
    expect(usualLevel(124, 100)).toBe("usual");
    expect(usualLevel(150, 100)).toBe("higher");
    expect(usualLevel(250, 100)).toBe("much-higher");
  });

  it("gives no level without a usual total or when the street is very quiet", () => {
    expect(usualLevel(10, null)).toBeNull();
    expect(usualLevel(3, 2)).toBeNull();
    expect(usualLevel(null, 100)).toBeNull();
  });
});
