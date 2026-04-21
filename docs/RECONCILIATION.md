# Daily Reconciliation

Goal: detect silent data loss between the 15-min count stream and the per-day
cumulative stream, and surface mismatches to admins.

## What is compared

For every `(sensor_id, day)` the backend runs:

    sum( sensor_readings.count
         WHERE sensor_id = X
           AND window_start >= day 00:00Z
           AND window_start <  day+1 00:00Z )
    vs.
    sensor_daily_totals.totals_json (for same sensor, day)

If any per-class delta is non-zero, the day is flagged:

    UPDATE sensor_daily_totals
    SET reconciled = FALSE,
        mismatch_json = <diff>
    WHERE sensor_id = X AND day = D;

Flagged rows appear in `/admin/events`.

## When it runs

`/api/cron/reconcile-daily` — scheduled at **01:00 UTC** via Vercel Cron
(declared in `vercel.ts`). Late daily payloads (`late=true`) are re-checked
on arrival.

## Why mismatches occur (and what they mean)

| Cause | Pattern |
|---|---|
| Outbox overflowed during a long offline period | 15-min windows short; daily total intact → missing windows visible |
| Device clock drifted across midnight | Some windows misattributed to neighbouring day |
| Config change mid-day (new window length) | Window count differs from expected 96 |
| Bug in windowed reset | Systematic under- or over-count; flag early |

The daily payload is the reconciliation truth by design: it's produced from
a running counter that the 15-min reset path cannot affect. Plan 01 §3.7
details the offline-buffer overflow scenario explicitly.

## Manual replay

If a mismatch is legitimate (data corruption upstream), admins can trigger
a replay by rewriting the 15-min windows from an archived edge log — no
automated tool for this in v1; do it via SQL and record the action in
`audit_log`.
