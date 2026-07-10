// Gap-fill regression — binding. readings() must return a contiguous grid over
// the requested [from, to) range, marking windows with no data as missing
// (null counts) rather than omitting them. Omission lets the time-series chart
// interpolate across an outage, making a downed sensor look like real traffic.
//
// The mock fixture (cam-dub-01 → ucd-stillorgan-rd-entrance) is a complete
// 15-min grid spanning
// 2026-04-14T00:00 … 2026-04-20T23:45 (window_start). Requesting a range that
// straddles the data end therefore yields present buckets followed by explicit
// missing buckets — a deterministic present→missing transition.

import { describe, expect, it } from "vitest";
import { mockStreetsRepo } from "@/lib/repo/streets-mock";
import { ROAD_USER_CLASSES } from "@/lib/types";

const BUCKET_MINUTES = 15;
const BUCKET_MS = BUCKET_MINUTES * 60_000;

describe("readings() gap-fill", () => {
  it("emits a contiguous grid with explicit missing buckets over an outage", async () => {
    const from = new Date("2026-04-20T22:00:00Z"); // within data
    const to = new Date("2026-04-21T02:00:00Z"); // 2h past last window (23:45)

    const rows = await mockStreetsRepo.readings({
      streetId: "ucd-stillorgan-rd-entrance",
      from,
      to,
      bucketMinutes: BUCKET_MINUTES,
    });

    // 4h / 15min = 16 buckets, none dropped.
    expect(rows.length).toBe(16);

    // Contiguous: every bucket is exactly one interval after the previous one.
    for (let i = 1; i < rows.length; i++) {
      const prev = new Date(rows[i - 1]!.bucket).getTime();
      const curr = new Date(rows[i]!.bucket).getTime();
      expect(curr - prev).toBe(BUCKET_MS);
    }

    // Present buckets (before the data end) carry numeric counts for classes
    // above the k-anonymity floor. `person` at this street is always well
    // above the floor in this window, so it stays numeric — proving the bucket
    // is genuinely present, not merely a missing window with null counts.
    // (Low counts of 1..4 are legitimately suppressed to null; see the privacy
    // regression test.)
    const present = rows.filter((r) => !r.missing);
    expect(present.length).toBeGreaterThan(0);
    for (const r of present) {
      expect(r.counts.person).not.toBeNull();
    }

    // Missing buckets (after the data end) carry an explicit marker + null counts.
    const missing = rows.filter((r) => r.missing);
    expect(missing.length).toBeGreaterThan(0);
    for (const r of missing) {
      for (const cls of ROAD_USER_CLASSES) {
        expect(r.counts[cls]).toBeNull();
      }
    }

    // Present prefix, then a contiguous missing tail past the data end — the
    // outage is marked explicitly and never spuriously "resumes" (which is
    // exactly what interpolation across a dropped window would look like).
    expect(rows[0]!.missing).toBe(false); // 22:00 has data
    expect(rows.at(-1)!.missing).toBe(true); // 01:45 is past the data end
    const firstMissingIdx = rows.findIndex((r) => r.missing);
    expect(firstMissingIdx).toBeGreaterThan(0);
    for (let i = firstMissingIdx; i < rows.length; i++) {
      expect(rows[i]!.missing).toBe(true);
    }

    // Everything at/after the 00:00 data-end boundary is a missing window.
    const boundary = rows.find((r) => r.bucket === "2026-04-21T00:00:00.000Z");
    expect(boundary?.missing).toBe(true);
  });
});
