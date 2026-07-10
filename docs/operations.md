# CAMINA Operations

Runbook for the dashboard's storage-retention and cron topology. Implements
audit findings **C1** (retention), **H12** (bounded materialized views), and
**H14** (cron scheduling on Vercel Hobby).

## Cron topology

CAMINA runs on the **Vercel Hobby** plan, whose Cron scheduler honours **daily
granularity only**. Sub-daily jobs are therefore split across three drivers:

| Job | Route | Cadence | Driven by |
|---|---|---|---|
| Retention rollup + prune | `GET /api/cron/retention` | daily 03:00 UTC | Vercel Cron (`dashboard/vercel.ts`) |
| Daily reconciliation | `GET /api/cron/reconcile-daily` | daily 01:00 UTC | Vercel Cron (`dashboard/vercel.ts`) |
| Bounded MV refresh | `GET /api/cron/refresh-aggregates` | ~every 15 min | GitHub Actions (`.github/workflows/cron.yml`) + **piggybacked on every live ingest** |
| Silent-sensor detection | `GET /api/cron/detect-silent` | ~every 15 min | GitHub Actions (`.github/workflows/cron.yml`) |

All routes are protected by `verifyCron` (`dashboard/src/lib/cron-auth.ts`): a
request must carry `Authorization: Bearer <VERCEL_CRON_SECRET>`. Vercel Cron
signs its own calls with that secret; the GitHub Actions workflow sends the same
secret.

### Primary vs fallback MV refresh

The materialized views (`street_readings_15m`, `street_readings_hourly`) back
the painted map window and are bounded to the last **48 h** (H12), so a refresh
is cheap. They are refreshed by two paths:

1. **Piggyback (primary):** after a successful live counts upsert, the ingest
   route fires `refreshBoundedAggregatesSafe()` via `waitUntil()`
   (`dashboard/src/lib/ingest-store.ts`). It is guarded by a transaction-scoped
   `pg_try_advisory_xact_lock` (never blocks) plus a **4-minute** min-interval
   gate tracked in `cron_meta`, so an ingest burst triggers at most ~1 refresh
   per window. Failures are swallowed and never affect the ingest response.
2. **GitHub Actions (fallback):** covers quiet periods with no ingest. Hits the
   route with `minIntervalMs = 0` (always refresh when it fires; still
   advisory-lock guarded).

## Required GitHub configuration

The external scheduler needs (Repository → Settings → Secrets and variables →
Actions):

- **Secret** `VERCEL_CRON_SECRET` — must equal the `VERCEL_CRON_SECRET`
  environment variable set on the Vercel project (Production scope).
- **Variable** `CAMINA_BASE_URL` — the production origin with no trailing slash,
  e.g. `https://camina.vercel.app`.

GitHub-hosted schedules are best-effort and can lag under load; 15 minutes is
the practical floor. All hit endpoints are idempotent, so a delayed or dropped
run is harmless.

## Retention design (C1)

Neon's free tier caps at **0.5 GB**. Raw `sensor_readings` is the dominant
consumer; the audit measured **~3–6 GB/yr at 100 sensors**. Retention keeps raw
rows for **90 days**, rolling older rows up into durable aggregates before
deletion.

### Tables

- `sensor_readings` (raw) — pruned at 90 days.
- `street_hourly` — durable per-street/class/hour rollup. Backs history charts
  beyond the 48 h MV window.
- `street_daily` — durable per-street/class/day rollup for long-range history.
- `cron_meta` — one row per job; stores `last_run_at` for the MV-refresh gate.

Averages are stored as weighted-sum components (`speed_weighted_sum`,
`speed_count`) rather than a pre-divided mean, with `avg_speed_kmh` exposed as a
`GENERATED` column. This makes the additive `ON CONFLICT DO UPDATE` merges exact
even when an hour bucket is split across retention batches.

### Batch strategy

The retention job (`runRetention`) runs a sequence of **bounded batches**. Each
batch is a **single transaction** that:

1. Takes a transaction-scoped `pg_try_advisory_xact_lock` — if another run holds
   it, the batch yields (`skippedLocked`) instead of blocking.
2. Runs one data-modifying CTE: `DELETE` the oldest `batchSize` (default 5000)
   expired rows `RETURNING` them, then additively upsert their contributions
   into `street_hourly` and `street_daily`. Under one snapshot, each raw row is
   counted and deleted exactly once.

The loop stops when a batch drains fewer rows than `batchSize` (backlog cleared)
or after `maxBatches` (default 50) to bound work per invocation and avoid
function timeouts. Rows rolled/deleted are logged as one structured line.

### Storage math

Assumes ~5 non-zero classes reported per 15-min window (96 windows/day), aligned
with the audit's 3–6 GB/yr-at-100-sensors measurement (~30–60 MB/sensor/yr raw).

| Scenario | Raw footprint |
|---|---|
| 8 sensors, no retention | ~0.24–0.48 GB/yr — approaches the 0.5 GB free cap within a year |
| 8 sensors, 90-day retention | steady-state ~60–120 MB raw — comfortable |
| 100 sensors, no retention | ~3–6 GB/yr — exceeds 0.5 GB free in ~3–4 weeks |
| 100 sensors, 90-day retention | steady-state ~0.75–1.5 GB raw — **still over free tier** |

The `street_hourly` / `street_daily` rollups are tiny (a few MB per street per
year) and grow slowly, so the durable history store is negligible next to raw.

**Decision point (audit C1):** 90-day retention is necessary but **not
sufficient** at 100 sensors — steady-state raw still exceeds the Neon free tier.
Beyond ~10 sensors, plan for a Neon paid tier or a storage re-architecture
(e.g. shorter raw retention, or dropping raw once rolled up).
