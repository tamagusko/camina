import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const migrations = path.resolve(process.cwd(), "drizzle/migrations");

describe("migration history", () => {
  it("registers the raw SQL migrations and direction columns in order", () => {
    const journal = JSON.parse(
      readFileSync(path.join(migrations, "meta/_journal.json"), "utf8")
    ) as { entries: { tag: string; idx: number }[] };
    expect(journal.entries.map((entry) => entry.tag)).toEqual([
      "0000_init",
      "0001_retention_and_bounded_mv",
      "0002_direction",
      "0003_snapshot_postgis",
    ]);
    for (const entry of journal.entries) {
      expect(readFileSync(path.join(migrations, `${entry.tag}.sql`), "utf8")).toBeTruthy();
      expect(readFileSync(path.join(migrations, `meta/${entry.idx.toString().padStart(4, "0")}_snapshot.json`), "utf8")).toBeTruthy();
    }
    expect(readFileSync(path.join(migrations, "0002_direction.sql"), "utf8"))
      .toMatch(/direction_ab_count[\s\S]*direction_ba_count/);
  });
});
