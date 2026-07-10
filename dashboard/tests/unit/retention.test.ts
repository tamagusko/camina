// Retention rollup + MV-refresh gate tests (audit C1, H14).
// Pure/injectable logic only — no live Postgres. Fake db objects stand in for
// the drizzle client, mirroring the ingest-routes.test.ts pattern.

import { describe, expect, it } from "vitest";

// ── Retention batch loop ───────────────────────────────────────────
interface BatchResult {
  deleted: number;
  hourly_upserts: number;
  daily_upserts: number;
}

/**
 * Build a fake db whose `transaction(cb)` runs the callback with a fake tx.
 * `tx.execute` returns queued results in order; the first execute per batch is
 * the advisory-lock probe, the second is the batch CTE result.
 */
function makeFakeDb(opts: {
  locked?: boolean[]; // per-batch lock outcomes
  batches?: BatchResult[]; // per-batch CTE results
}) {
  const locked = opts.locked ?? [];
  const batches = opts.batches ?? [];
  let call = 0;
  const tx = {
    execute() {
      const isLockProbe = call % 2 === 0;
      const batchIdx = Math.floor(call / 2);
      call++;
      if (isLockProbe) {
        return Promise.resolve([{ locked: locked[batchIdx] ?? true }]);
      }
      return Promise.resolve([
        batches[batchIdx] ?? { deleted: 0, hourly_upserts: 0, daily_upserts: 0 },
      ]);
    },
  };
  return {
    transaction<T>(cb: (t: typeof tx) => Promise<T>): Promise<T> {
      return cb(tx);
    },
  };
}

describe("runRetention — batch loop", () => {
  it("accumulates totals and stops when a batch drains below batchSize", async () => {
    const { runRetention } = await import(
      "@/app/api/cron/retention/retention-core"
    );
    const db = makeFakeDb({
      locked: [true, true],
      batches: [
        { deleted: 100, hourly_upserts: 10, daily_upserts: 3 },
        { deleted: 42, hourly_upserts: 5, daily_upserts: 2 }, // < batchSize → stop
      ],
    });
    const res = await runRetention(db as never, { batchSize: 100, maxBatches: 50 });
    expect(res.batches).toBe(2);
    expect(res.rowsDeleted).toBe(142);
    expect(res.hourlyUpserts).toBe(15);
    expect(res.dailyUpserts).toBe(5);
    expect(res.skippedLocked).toBe(false);
  });

  it("stops immediately and flags skippedLocked when the advisory lock is held", async () => {
    const { runRetention } = await import(
      "@/app/api/cron/retention/retention-core"
    );
    const db = makeFakeDb({ locked: [false], batches: [] });
    const res = await runRetention(db as never, { batchSize: 100 });
    expect(res.skippedLocked).toBe(true);
    expect(res.batches).toBe(0);
    expect(res.rowsDeleted).toBe(0);
  });

  it("respects maxBatches when the backlog never drains", async () => {
    const { runRetention } = await import(
      "@/app/api/cron/retention/retention-core"
    );
    const full: BatchResult = { deleted: 100, hourly_upserts: 1, daily_upserts: 1 };
    const db = makeFakeDb({
      locked: Array(10).fill(true),
      batches: Array(10).fill(full),
    });
    const res = await runRetention(db as never, { batchSize: 100, maxBatches: 3 });
    expect(res.batches).toBe(3);
    expect(res.rowsDeleted).toBe(300);
  });
});

describe("buildRetentionBatchSql", () => {
  it("produces a statement carrying the retentionDays and batchSize params", async () => {
    const { buildRetentionBatchSql } = await import(
      "@/app/api/cron/retention/retention-core"
    );
    const q = buildRetentionBatchSql(90, 5000);
    const serialised = JSON.stringify(q);
    expect(serialised).toContain("90");
    expect(serialised).toContain("5000");
  });
});

// ── MV-refresh min-interval gate ───────────────────────────────────
describe("shouldRefreshNow — MV refresh gate", () => {
  it("always refreshes when never refreshed before", async () => {
    const { shouldRefreshNow } = await import("@/lib/ingest-store");
    expect(shouldRefreshNow(null, Date.now(), 240_000)).toBe(true);
  });

  it("skips when the last refresh is within the min interval", async () => {
    const { shouldRefreshNow } = await import("@/lib/ingest-store");
    const now = Date.now();
    const recent = new Date(now - 60_000); // 1 min ago, min interval 4 min
    expect(shouldRefreshNow(recent, now, 240_000)).toBe(false);
  });

  it("refreshes once the min interval has elapsed", async () => {
    const { shouldRefreshNow } = await import("@/lib/ingest-store");
    const now = Date.now();
    const old = new Date(now - 300_000); // 5 min ago
    expect(shouldRefreshNow(old, now, 240_000)).toBe(true);
  });

  it("treats an exactly-elapsed interval as due", async () => {
    const { shouldRefreshNow } = await import("@/lib/ingest-store");
    const now = Date.now();
    expect(shouldRefreshNow(new Date(now - 240_000), now, 240_000)).toBe(true);
  });
});

// ── refreshBoundedAggregates — lock/gate branches (fake db) ─────────
describe("refreshBoundedAggregates — outcome branches", () => {
  function makeRefreshDb(rows: unknown[][]) {
    let i = 0;
    const tx = {
      execute() {
        return Promise.resolve(rows[i++] ?? []);
      },
    };
    return {
      transaction<T>(cb: (t: typeof tx) => Promise<T>): Promise<T> {
        return cb(tx);
      },
    };
  }

  it("returns skipped_locked when the try-lock is not acquired", async () => {
    const { refreshBoundedAggregates } = await import("@/lib/ingest-store");
    const db = makeRefreshDb([[{ locked: false }]]);
    expect(await refreshBoundedAggregates(db as never)).toBe("skipped_locked");
  });

  it("returns skipped_recent when within the min interval", async () => {
    const { refreshBoundedAggregates } = await import("@/lib/ingest-store");
    const now = Date.now();
    const db = makeRefreshDb([
      [{ locked: true }],
      [{ last_run_at: new Date(now - 10_000).toISOString() }],
    ]);
    expect(
      await refreshBoundedAggregates(db as never, { minIntervalMs: 240_000, now })
    ).toBe("skipped_recent");
  });

  it("refreshes when locked and past the interval", async () => {
    const { refreshBoundedAggregates } = await import("@/lib/ingest-store");
    const now = Date.now();
    const db = makeRefreshDb([
      [{ locked: true }],
      [{ last_run_at: new Date(now - 600_000).toISOString() }],
      [], // REFRESH 15m
      [], // REFRESH hourly
      [], // upsert cron_meta
    ]);
    expect(
      await refreshBoundedAggregates(db as never, { minIntervalMs: 240_000, now })
    ).toBe("refreshed");
  });
});
