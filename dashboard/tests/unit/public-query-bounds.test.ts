// Public list endpoints are bounded: bad or oversized queries get 400, never a
// 500 or an unbounded response.

import { describe, expect, it } from "vitest";
import { GET as readings } from "@/app/api/streets/[id]/readings/route";
import { GET as metrics } from "@/app/api/metrics/route";
import { MAX_READING_ROWS } from "@/lib/schemas";

const STREET = "ucd-stillorgan-rd-entrance";

function readingsReq(query: string) {
  return readings(new Request(`http://test/api/streets/${STREET}/readings?${query}`), {
    params: Promise.resolve({ id: STREET }),
  });
}

describe("GET /api/streets/[id]/readings bounds", () => {
  it("serves the default last hour", async () => {
    const res = await readingsReq("");
    expect(res.status).toBe(200);
    const rows = (await res.json()) as unknown[];
    expect(rows.length).toBeGreaterThanOrEqual(4);
    expect(rows.length).toBeLessThanOrEqual(5);
  });

  it("serves a full-size range at every allowed bucket", async () => {
    for (const bucket of [15, 60, 1440]) {
      const to = new Date("2026-04-21T00:00:00Z");
      const from = new Date(to.getTime() - MAX_READING_ROWS * bucket * 60_000);
      const res = await readingsReq(
        `from=${from.toISOString()}&to=${to.toISOString()}&bucket=${bucket}`
      );
      expect(res.status).toBe(200);
      expect(((await res.json()) as unknown[]).length).toBe(MAX_READING_ROWS);
    }
  });

  it.each([
    ["bucket not in the allowed set", "bucket=1"],
    ["bucket not a number", "bucket=abc"],
    ["bad datetime", "from=yesterday"],
    ["from after to", "from=2026-04-21T00:00:00Z&to=2026-04-20T00:00:00Z"],
    ["empty range", "from=2026-04-21T00:00:00Z&to=2026-04-21T00:00:00Z"],
    ["too many rows (31 d at 15 min)", "from=2026-03-21T00:00:00Z&to=2026-04-21T00:00:00Z&bucket=15"],
    ["ten years at 1 min", "from=2016-04-21T00:00:00Z&to=2026-04-21T00:00:00Z&bucket=1"],
    ["too many rows (10 y daily)", "from=2016-04-21T00:00:00Z&to=2026-04-21T00:00:00Z&bucket=1440"],
    ["unknown class", "class=horse"],
  ])("rejects %s with 400", async (_label, query) => {
    const res = await readingsReq(query);
    expect(res.status).toBe(400);
  });
});

describe("GET /api/metrics bounds", () => {
  it("serves defaults", async () => {
    const res = await metrics(new Request("http://test/api/metrics"));
    expect(res.status).toBe(200);
  });

  it.each([
    ["unknown metric", "metric=bogus"],
    ["unknown window", "window=1y"],
    ["unknown class", "class=horse"],
    ["oversized city", `city=${"x".repeat(200)}`],
  ])("rejects %s with 400", async (_label, query) => {
    const res = await metrics(new Request(`http://test/api/metrics?${query}`));
    expect(res.status).toBe(400);
  });
});
