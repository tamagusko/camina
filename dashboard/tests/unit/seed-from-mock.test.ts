// db:seed loads the mock streets so a fresh database has a street to provision
// a sensor against. Idempotent: a second run inserts nothing.

import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import path from "node:path";
import postgres from "postgres";
import { afterAll, describe, expect, it } from "vitest";
import { seedStreets, type SeedStreet } from "../../scripts/seed-from-mock";

describe.runIf(Boolean(process.env.DATABASE_URL_TEST))("seed-from-mock", () => {
  const client = postgres(process.env.DATABASE_URL_TEST ?? "", { max: 1 });
  const suffix = randomUUID();
  const fixture = JSON.parse(
    readFileSync(path.resolve(process.cwd(), "..", "data/mock/dublin/streets.json"), "utf8")
  ) as SeedStreet[];
  const streets = fixture.map((s) => ({ ...s, id: `${s.id}-${suffix}`, city: `seed-${suffix}` }));

  afterAll(async () => {
    await client`DELETE FROM streets WHERE city = ${`seed-${suffix}`}`;
    await client.end();
  });

  it("inserts every street with PostGIS geometry, once", async () => {
    expect(await seedStreets(client, streets)).toBe(streets.length);
    expect(await seedStreets(client, streets)).toBe(0);
    const rows = await client`
      SELECT count(*)::int AS n, bool_and(ST_IsValid(geom) AND GeometryType(geom) = 'MULTILINESTRING'
        AND GeometryType(bbox) = 'POLYGON') AS ok
      FROM streets WHERE city = ${`seed-${suffix}`}`;
    expect(rows[0]).toEqual({ n: streets.length, ok: true });
  });
});
