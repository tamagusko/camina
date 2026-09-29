// The drizzle schema and the latest migration snapshot agree with the SQL
// migrations: `drizzle-kit generate` finds nothing to do, and the snapshot
// knows the PostGIS columns (a snapshot without them lets drizzle tooling
// propose DROP COLUMN geom/bbox).

import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const migrations = path.join(root, "drizzle/migrations");

function latestSnapshot(): { tables: Record<string, { columns: Record<string, { type: string }> }> } {
  const journal = JSON.parse(readFileSync(path.join(migrations, "meta/_journal.json"), "utf8")) as {
    entries: { idx: number }[];
  };
  const idx = journal.entries.at(-1)!.idx.toString().padStart(4, "0");
  return JSON.parse(readFileSync(path.join(migrations, `meta/${idx}_snapshot.json`), "utf8"));
}

describe("drizzle schema vs migrations", () => {
  it("the latest snapshot has the PostGIS street columns", () => {
    const streets = latestSnapshot().tables["public.streets"]!.columns;
    expect(streets.geom?.type).toBe("geometry(MultiLineString,4326)");
    expect(streets.bbox?.type).toBe("geometry(Polygon,4326)");
  });

  it("drizzle-kit generate produces no new migration", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "camina-drizzle-"));
    try {
      cpSync(migrations, path.join(dir, "migrations"), { recursive: true });
      const config = path.join(dir, "drizzle.config.ts");
      writeFileSync(config, `export default ${JSON.stringify({
        // drizzle-kit prefixes "./" to these, so they must be relative to cwd.
        schema: "./drizzle/schema.ts",
        out: path.relative(root, path.join(dir, "migrations")),
        dialect: "postgresql",
      })};\n`);
      const before = readdirSync(path.join(dir, "migrations")).sort();
      const output = execFileSync(path.join(root, "node_modules/.bin/drizzle-kit"),
        ["generate", "--config", config], { cwd: root, encoding: "utf8" });
      expect(output).toMatch(/No schema changes/);
      expect(readdirSync(path.join(dir, "migrations")).sort()).toEqual(before);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }, 60_000);
});
