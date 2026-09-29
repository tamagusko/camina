// Map metrics cover active streets only, like list(): an inactive street's
// geometry is not served, so its metrics must not be either.

import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/mock-loader", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/mock-loader")>();
  return {
    ...real,
    loadStreets: async () =>
      (await real.loadStreets()).map((s, i) => (i === 0 ? { ...s, active: false } : s)),
  };
});

describe("mock adapter", () => {
  it("latestMetrics omits inactive streets", async () => {
    const { mockStreetsRepo } = await import("@/lib/repo/streets-mock");
    const listed = (await mockStreetsRepo.list("dublin")).map((s) => s.id).sort();
    const metrics = await mockStreetsRepo.latestMetrics({
      city: "dublin", metric: "counts", window: "24h",
    });
    expect(metrics.map((m) => m.streetId).sort()).toEqual(listed);
  });
});

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("live adapter", () => {
  const url = process.env.DATABASE_URL_TEST ?? "";
  const client = postgres(url, { max: 1 });
  const city = `active-test-${randomUUID()}`;
  const ids = [`${city}-on`, `${city}-off`] as const;

  beforeAll(async () => {
    process.env.DATABASE_URL = url;
    for (const [id, active] of [[ids[0], true], [ids[1], false]] as const) {
      await client`INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city, active)
        VALUES (${id}, 'Active Test', ARRAY[42]::bigint[],
          ST_GeomFromText('MULTILINESTRING((-6.3 53.3,-6.2 53.4))', 4326),
          ST_GeomFromText('POLYGON((-6.3 53.3,-6.2 53.3,-6.2 53.4,-6.3 53.4,-6.3 53.3))', 4326),
          ${city}, ${active})`;
    }
  });

  afterAll(async () => {
    await client`DELETE FROM streets WHERE city = ${city}`;
    await client.end();
  });

  it("latestMetrics omits inactive streets", async () => {
    const { liveStreetsRepo } = await import("@/lib/repo/streets-live");
    const metrics = await liveStreetsRepo.latestMetrics({ city, metric: "counts", window: "1h" });
    expect(metrics.map((m) => m.streetId)).toEqual([ids[0]]);
  });
});
