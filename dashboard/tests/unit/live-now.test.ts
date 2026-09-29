// The street page shows the 24 h of 15-min buckets before the repo's now().
// With a wall-clock now (10:07) the first bucket (10:00 yesterday) was cut to
// its last 8 minutes and the last (10:00 today) was still in progress, so the
// live page painted both as "sensor offline" on every load. now() is the end
// of the last completed cell, as the mock's is the end of its latest window.
import { afterEach, describe, expect, it, vi } from "vitest";
import { liveStreetsRepo } from "@/lib/repo/streets-live";

describe("live now()", () => {
  afterEach(() => vi.useRealTimers());

  it("is the end of the last completed 15-min cell", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-03-10T10:07:30Z"));
    expect((await liveStreetsRepo.now()).toISOString()).toBe("2026-03-10T10:00:00.000Z");
  });
});
