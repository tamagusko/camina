// Load the mock streets (data/mock/<city>/streets.json, written by
// scripts/generate_mock_dublin.py) into a database, so a fresh deployment has
// streets to provision sensors against. Streets only: sensors come from
// provision-sensor.ts, readings from real devices. Existing ids are kept.
//
//   DATABASE_URL_UNPOOLED=<url> pnpm db:seed [--city dublin]

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";

type Client = ReturnType<typeof postgres>;

export interface SeedStreet {
  id: string;
  display_name: string;
  osm_way_ids: number[];
  geom: GeoJSON.MultiLineString;
  bbox: GeoJSON.Polygon;
  city: string;
  active: boolean;
  speed_limit_kmh?: number | null;
}

/** Inserts the streets that do not exist yet; returns how many were inserted. */
export async function seedStreets(client: Client, streets: SeedStreet[]): Promise<number> {
  let inserted = 0;
  await client.begin(async (tx) => {
    for (const s of streets) {
      const rows = await tx`
        INSERT INTO streets (id, display_name, osm_way_ids, geom, bbox, city, active, speed_limit_kmh)
        VALUES (${s.id}, ${s.display_name}, ${s.osm_way_ids.map(String)}::bigint[],
                ST_SetSRID(ST_GeomFromGeoJSON(${JSON.stringify(s.geom)}), 4326),
                ST_SetSRID(ST_GeomFromGeoJSON(${JSON.stringify(s.bbox)}), 4326),
                ${s.city}, ${s.active}, ${s.speed_limit_kmh ?? null})
        ON CONFLICT (id) DO NOTHING RETURNING id
      `;
      inserted += rows.length;
    }
  });
  return inserted;
}

async function main(): Promise<void> {
  const cityFlag = process.argv.indexOf("--city");
  const city = cityFlag > 0 ? process.argv[cityFlag + 1] : "dublin";
  if (!city || !/^[a-z0-9-]+$/.test(city)) throw new Error("--city must be a lowercase slug");
  const url = process.env.DATABASE_URL_UNPOOLED ?? process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL_UNPOOLED or DATABASE_URL is required");
  const file = resolve(process.cwd(), "..", "data", "mock", city, "streets.json");
  const streets = JSON.parse(await readFile(file, "utf8")) as SeedStreet[];
  const client = postgres(url, { max: 1, prepare: false });
  try {
    const inserted = await seedStreets(client, streets);
    process.stdout.write(`${inserted} of ${streets.length} streets inserted from ${file}\n`);
  } finally {
    await client.end();
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
