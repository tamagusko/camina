// The street page shows the 24 h before the repo's "now". The mock data is
// historical, so a wall-clock "now" left every mock street page empty.
import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";

describe("street page window", () => {
  it("mock now() is the end of the latest mock window", async () => {
    expect((await mockStreetsRepo.now()).toISOString()).toBe("2026-04-21T00:00:00.000Z");
  });

  it("every mock street has published counts in the 24 h before now()", async () => {
    const to = await mockStreetsRepo.now();
    const from = new Date(to.getTime() - 24 * 60 * 60_000);
    for (const street of await mockStreetsRepo.list("dublin")) {
      const rows = await mockStreetsRepo.readings({ streetId: street.id, from, to, bucketMinutes: 15 });
      const published = rows.some((row) => !row.missing && Object.values(row.counts).some((n) => n !== null && n > 0));
      expect(published, street.id).toBe(true);
    }
  });
});
