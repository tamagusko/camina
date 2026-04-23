# Pitfalls Research

**Domain:** Privacy-first edge-CV + LoRaWAN + serverless dashboard (academic TRL-6 demo)
**Researched:** 2026-04-23
**Confidence:** HIGH (verified against current Raspberry Pi, TTN, Neon, and Vercel docs; 3 pitfalls pulled directly from `.planning/codebase/CONCERNS.md`)

> **Deadline context:** CAMINA has 5 weeks to TRL-6 (2026-05-31). Severity in every pitfall below is calibrated against that deadline: a CRITICAL pitfall can blow the date; a HIGH pitfall can push it by ≥3 days; MEDIUM costs 1–2 days; LOW is technical-debt that matters after demo.

---

## Critical Pitfalls

### Pitfall 1: Pi 5 thermal throttling collapses inference FPS mid-demo

**What goes wrong:**
The Pi 5 under sustained YOLO11n + tracker + capture load without active cooling hits 85 °C within ~90 seconds and throttles from 2.4 GHz down to ~1.8 GHz. FPS silently drops 25–40 %, tracker ID churn increases (slow frames = bigger inter-frame displacement = Hungarian mis-assignments), and windowed counts drift low. The demo shows "working" numbers that are quietly wrong.

**Why it happens:**
The Pi 5 ships without a cooler by default. A passive heatsink is not enough for >15 minutes of continuous inference in a street-mounted enclosure (no airflow, often direct sun). Developers benchmark on a desk, then deploy in a box.

**How to avoid:**
- Mandatory **Pi 5 Official Active Cooler** or equivalent 30 mm PWM fan on the deployment unit. Budget €10.
- Log `vcgencmd measure_temp`, `vcgencmd get_throttled`, and `vcgencmd measure_clock arm` in the `/heartbeat` payload. Surface throttle flags in the admin strip.
- Benchmark at the target FPS for **≥30 min continuously** inside the real enclosure, in ambient ≥25 °C, before the field deployment.
- If the NCNN INT8 model is still too hot, drop to 10 FPS or `imgsz=480` before shipping.

**Warning signs:**
- `vcgencmd get_throttled` returns anything non-zero.
- FPS counter in daemon logs drops after the first 2–3 minutes of operation.
- CPU temp in heartbeats climbs past 75 °C and plateaus.

**Phase to address:** M1 — before end-to-end Pi integration. Add thermal fields to `/heartbeat` schema and gate the deployment-readiness checklist on a 30-minute sustained benchmark.

**Severity:** **CRITICAL** — silently corrupts demo numbers, no alert without instrumentation.

---

### Pitfall 2: `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` leaks GPS to production

**What goes wrong:**
`NEXT_PUBLIC_*` env vars are inlined at build time into every client bundle. A single preview/production deploy with the dev-admin flag on ships every sensor's exact GPS coordinates, install date, firmware, and heartbeats to every anonymous visitor. Directly violates the GDPR design principle that is the public face of this research project. Unrecoverable — the leaked build is on Vercel's edge cache and any browser that fetched it; a git revert does not un-leak the coords already distributed.

**Why it happens:**
`.env.local` is set to `true` on the dev machine (already confirmed in `CONCERNS.md §3`). Vercel's env-var propagation is easy to misconfigure; `vercel env add` can land a preview value in production by accident. No build-time guard refuses the deploy today.

**How to avoid:**
- **Build-time guard in `vercel.ts`**: if `VERCEL_ENV ∈ {preview, production}` and `NEXT_PUBLIC_CAMINA_DEV_ADMIN === "true"`, throw in the build step. Fails loudly instead of shipping silently.
- Server route `/api/admin/streets/[id]/info`: tighten the mock-mode bypass so it also requires `NODE_ENV !== "production"`. Two locks, not one.
- Playwright E2E on every preview that hits `/api/admin/streets/[id]/info` with no session and asserts 401. Already listed in `TODO.md §12` — elevate to a D14 blocker.

**Warning signs:**
- `grep NEXT_PUBLIC_CAMINA_DEV_ADMIN=true dashboard/.env*` returns anything outside `.env.local`.
- `vercel env ls preview | grep DEV_ADMIN` returns any row.

**Phase to address:** M2 — **before first Vercel preview deploy**. Also: add to `dashboard/docs/RUNBOOK.md` as a pre-push checklist.

**Severity:** **CRITICAL** — sourced from `CONCERNS.md §3`; single-flag mistake blows the entire privacy story of the project.

---

### Pitfall 3: Dev-mode Google allowlist accepts any email when unset

**What goes wrong:**
`dashboard/src/lib/auth.ts:31-37` has `if (devAllowlist.length === 0) return true;` — with `CAMINA_DEV_ALLOWED_EMAILS` empty (default), any Google account signs into `/admin`. An admin account on a Vercel preview deploy (preview URLs are public-by-default) = any third-party can click through OAuth and land on admin pages before Neon/DB-backed `allowed_members` replaces the env-var path.

**Why it happens:**
"Fail-open" default for DX convenience; never hardened before preview deploys started.

**How to avoid:**
- Flip the default to **fail-closed** when `NODE_ENV === "production" || VERCEL_ENV !== undefined`.
- Module-init assertion: if the live DB path is not selected AND `CAMINA_DEV_ALLOWED_EMAILS` is empty, throw and refuse to boot.
- Vercel preview deploys should require a preview-protection password (Vercel setting) OR remain `CAMINA_DATA_SOURCE=mock` with a hardcoded preview allowlist.

**Warning signs:**
- `curl https://<preview>.vercel.app/sign-in` from an unrelated Gmail account gets through.
- Log entry `auth.allowlist.fallback=env_empty` on any non-local deploy.

**Phase to address:** M2 — **D2 (Auth wiring) must not merge without this fix**. Pair with Pitfall 2 as the "preview-safety" gate.

**Severity:** **CRITICAL** — sourced from `CONCERNS.md §3`; any attacker with a Google account gets admin before the DB cutover.

---

### Pitfall 4: `rpicam-apps` / `picamera2` memory leak OOMs the daemon after hours

**What goes wrong:**
Multiple open issues (`raspberrypi/rpicam-apps#640`, `picamera2#887`) document memory leaks after repeated camera configure/close cycles, sometimes hitting 100 % RAM within a few hours. For a 24/7 systemd daemon that re-initializes the camera on any exception, the Pi OOMs, systemd restarts the unit, the OfflineBuffer recovers — but fast enough to keep up with window boundaries? Not if the crash loop runs every 20 minutes for a week.

**Why it happens:**
The RPi camera stack uses mmap-based DMA buffers; every configureStill/configureVideo call allocates new pools; freeing is lazy and exception paths don't always release. Looks fine on a 30-min benchmark; shows up at day 2.

**How to avoid:**
- **Do not re-initialize the camera on transient errors.** Catch and log, keep the running pipeline, only recreate on a fatal error.
- Watchdog: use systemd `WatchdogSec=300` + `sd_notify` pings from the daemon. A hung camera blocks the main loop, watchdog kicks, OS restarts clean.
- RSS monitor: daemon reports `RssKb` in `/heartbeat`; admin alert when RSS > 1.5 GB.
- Run the full pipeline for ≥48 h on the benchmark rig before the real-street install.

**Warning signs:**
- `/heartbeat`'s `uptime_s` resets every few hours without a `systemctl restart` command in the audit log.
- `dmesg` shows `Out of memory: Killed process ... python` on the Pi.
- RSS in top grows monotonically over hours.

**Phase to address:** M1 — wire watchdog + RSS reporting into `SensorDaemon` heartbeat. Run the 48-hour soak test before M2 starts.

**Severity:** **CRITICAL** — a week-long TRL-6 demo is specifically what breaks here; a 30-min lab test does not catch it.

---

### Pitfall 5: TTN Fair Use Policy (30 s airtime/day) silently drops LoRa uplinks

**What goes wrong:**
The Things Network community plan enforces **an average of 30 seconds of uplink airtime per 24 hours per device** (plus a hard 10 downlinks/day cap). A spreading-factor SF9 payload of ~40 bytes burns ~185 ms on air. At 30 s/day budget that's **~160 uplinks/day max** — roughly one every 9 min. The CAMINA plan says 15-min windows (~96/day), which fits only if SF stays low (SF7–SF9) and payload stays under ~50 bytes. If Adaptive Data Rate lands on SF12 (weak signal, far from gateway), a single uplink is ~1.5 s — the budget is burned in 20 uplinks (**3 hours**) and TTN can disconnect the device or drop its messages for the rest of the day.

This is worse than EU868's regulatory 1 % duty cycle: the regulator limits *instantaneous* airtime per sub-band; TTN limits *cumulative daily* airtime per device.

**Why it happens:**
Developers calculate "payload under 200 bytes, 15-min cadence, easy" without modeling spreading factor. ADR is adaptive — the field behavior is unknowable until deployed.

**How to avoid:**
- **Pre-deployment airtime budget**: compute payload airtime at SF7/9/10/12 for the chosen region/DR. Reject the design if the worst-case SF busts 30 s/day.
- Shrink the payload codec aggressively: the 200-char ASCII constraint is self-imposed and generous. A pure-binary packed layout (1 byte camera ID, 4 bytes epoch, 9×1 byte counts = 14 bytes) fits SF12 in ~1.4 s/uplink.
- Monitor `f_cnt` gap on the dashboard: missing uplinks after FUP exhaustion show as a monotonic gap.
- If coverage pushes SF above 10, move that sensor to HTTPS/WiFi or deploy a private gateway near it. Don't fight the FUP.
- Document the failure mode in `docs/PROTOCOL.md` so future operators know why LoRa went silent.

**Warning signs:**
- TTN console shows device "airtime per 24h" approaching 30 s.
- Sudden cliff in LoRa uplinks arriving at `/api/ingest/lora/*` after a steady stream.
- Device is provisioned with SF10+ in its Session context.

**Phase to address:** M1 — LoRa phase. Airtime budget is a **gate** before `LoRaPublisher` merges.

**Severity:** **CRITICAL** — on a real Dublin street, ADR can absolutely pick SF10–12. A 3-hour data-loss window per day is demo-ending.

---

### Pitfall 6: Single-sensor SPOF kills the "≥1 week live" TRL-6 demo

**What goes wrong:**
CAMINA's demo requires **one Pi on one street publishing live for ≥1 week**. One Pi = zero redundancy. A router reboot, a camera glitch, a cable kick, thermal shutdown, or vandalism between 2026-05-24 and 2026-05-31 converts the demo result from "week of data" to "partial day of data" — and the INTERREG deliverable reads differently.

**Why it happens:**
Budget and solo-dev bandwidth. Legitimate trade-off, but not one that's currently documented or instrumented for.

**How to avoid:**
- **Pre-demo soak run** that starts 3 weeks before the deadline, not 1. If the first soak fails, there's time for a second.
- **Second identical Pi** configured and bench-tested as a cold spare. Same SD card image, same token (or fast token-rotation procedure via SSH). Swap time < 30 min.
- **Uptime monitor** on `/api/health` AND on `/api/ingest/sensors/dub-01/heartbeat` freshness (silent-sensor cron already planned for M2). Slack/email when a heartbeat is missed.
- Document the demo as "≥1 week of data" not "≥1 week of continuous uptime" — the OfflineBuffer + reconciliation already permit multi-hour gaps without data loss.
- On-site access plan: confirm who can physically touch the Pi if it needs a reboot.

**Warning signs:**
- Any unexplained heartbeat gap longer than the 15-min silent-sensor threshold.
- Power supply draw shows brownouts.
- Router/ISP maintenance window overlaps demo period.

**Phase to address:** M2 Deployment phase — build the cold-spare and silent-sensor cron before the soak starts.

**Severity:** **HIGH** (not CRITICAL because OfflineBuffer + reconciliation soften it) — plan explicitly for degraded-but-presentable outcomes.

---

### Pitfall 7: Clock drift on the Pi mis-aligns windows vs server

**What goes wrong:**
Pi 5 has no RTC. If NTP fails to sync at boot (captive portal, firewalled LAN, DNS down), the device clock drifts by minutes per day. 15-min windows labelled with a drifted `window_start` land in the wrong server bucket, breaking the `(sensor_id, window_start, class_name)` idempotency PK — and the daily reconciliation starts flagging phantom mismatches that the admin can't explain.

**Why it happens:**
Plan 01 §11 already mentions "NTP required at boot" but there's no **verification** that NTP actually synced before the daemon accepts its first detection.

**How to avoid:**
- Systemd `Requires=time-sync.target` + `After=time-sync.target` in `camina-sensor.service`. Unit does not start until `chrony` or `systemd-timesyncd` has synced.
- Daemon startup check: `timedatectl` `NTPSynchronized=yes`, else retry every 30 s for 5 min, else refuse to start and surface via next heartbeat's error field.
- Server-side guard: reject any `/counts` POST where `abs(produced_at - server_now) > 60 s`; return 400, device logs to dead-letter.

**Warning signs:**
- `produced_at` vs `received_at` delta > 1 min in server logs.
- Reconciliation flags mismatches that resolve when re-summed without time filters.

**Phase to address:** M1 — add to `deploy/systemd/camina-sensor.service` before first Pi deploy.

**Severity:** **HIGH** — creates data corruption that survives reconciliation and is visible to reviewers.

---

### Pitfall 8: Neon connection exhaustion under ingest retry storm

**What goes wrong:**
One sensor → Vercel function per POST → one DB connection. Usually fine. But if the device reconnects after an outage and drains its OfflineBuffer at 50 msgs/cycle, that's 50 concurrent Vercel invocations (Fluid Compute parallelises), each opening a DB conn, each running an `INSERT ON CONFLICT`. At the 500-device scale assumed in Plan 01, a cluster of reconnect storms after an ISP outage can spike to hundreds of connections instantly. Neon's pooler tops at its configured limit (default 10k clients but the backend connection pool is much smaller — typically 64–100 direct connections). Exhaustion returns `too many connections` errors, ingest returns 500, the OfflineBuffer backs up, cascade continues.

**Why it happens:**
Vercel Fluid Compute solves many cold-start connection-leak problems via `waitUntil`, but does not solve fan-out. Developers miss this until a real incident.

**How to avoid:**
- Always use **Neon's pooled connection string** (`?sslmode=require&pool=transaction` or Neon's pooled endpoint) — never the direct/unpooled URL in request-path code. Reserve unpooled for migrations.
- `waitUntil(() => pool.release())` pattern in every ingest route. Treat it as a code-review checklist item.
- Upstash Ratelimit on `/api/ingest/*` per sensor (already planned in `TODO.md §6`) — a sensor that's draining 50 msgs in a second hits the limiter, not the DB.
- Edge-side: bound the outbox drain rate to e.g. 5 msgs/second, not a pure 50-per-cycle batch burst.
- Document the Neon `DATABASE_URL` vs `DATABASE_URL_UNPOOLED` distinction loudly in `RUNBOOK.md`; grep CI to ensure unpooled never appears in `src/app/api/**`.

**Warning signs:**
- Sentry errors with `FATAL: sorry, too many clients already`.
- Neon dashboard shows compute connection count climbing, not plateauing.
- Ingest p95 latency spikes synchronously with OfflineBuffer drain events in daemon logs.

**Phase to address:** M2 — D5 (ingest API) and D13 (rate limits). Before the first real Pi starts publishing to the live DB.

**Severity:** **HIGH** — single-Pi demo likely survives, but the code pattern must be right before scale and before research partners plug in extra sensors.

---

### Pitfall 9: SD card corruption from power loss wrecks the OfflineBuffer

**What goes wrong:**
SQLite WAL is resilient *if fsync actually hits persistent storage*. SD cards lie about fsync. Raspberry Pi 5 + SD card + power cut in the middle of `OfflineBuffer.enqueue` → checkpointed WAL pages lost → `state.db` corrupt at next boot → daemon either crashes on startup or silently drops buffered windows. Two weeks of counts gone.

**Why it happens:**
SD cards are the worst possible medium for a write-heavy SQLite workload on a device without a UPS. Pi 5 caches more aggressively than Pi 4 (more RAM), so the window of lost writes is larger.

**How to avoid:**
- **Move `state.db` to a USB SSD** on the Pi. €15–25 for a small NVMe-in-USB enclosure; dramatic reliability upgrade, and the Pi 5 supports USB 3.0 at full speed.
- `PRAGMA synchronous=FULL` for critical `OfflineBuffer` writes (vs NORMAL); accept a few percent throughput cost.
- `PRAGMA integrity_check` on daemon startup; on failure, rename `state.db` → `state.db.broken.YYYYMMDDHHMM`, start fresh, surface alert via next heartbeat.
- Budget for a **small UPS HAT** (e.g. PiSugar, Waveshare, €30–40) — or at minimum a decent power supply with brownout tolerance. For a street deployment behind a POE/mains tap, document brownout risk.
- Daily backup of `state.db` to a second USB stick via cron.

**Warning signs:**
- Any `SQLITE_CORRUPT` or `SQLITE_NOTADB` in daemon logs.
- `daily_totals` table missing rows for yesterday despite windows being published.
- Pi occasionally boots to a filesystem check.

**Phase to address:** M1 — hardware choice. Make the storage decision before the soak test, not after.

**Severity:** **HIGH** — demo-ending single event, not a data-quality tax.

---

### Pitfall 10: Street-level aggregates still leak via one-sensor inference

**What goes wrong:**
Plan 02 §7 has a k-sensor guard ("if a street has ever had only one covering sensor, drop it when that sensor is removed") — good. But a more subtle leak: even **with** a single sensor actively covering a street, the public API exposes fine-grained 15-minute buckets of per-class counts. An attacker who knows *when* CAMINA was installed on which street (public INTERREG announcement? local news?) can take those 15-min buckets + the sensor-install date and back-infer sensor position to within a few meters just from the street geometry — because a "street" in OSM can be 400 m long and the sensor only sees a 30 m cone.

Further, 15-min temporal resolution combined with low pedestrian counts (e.g. "3 cyclists in this window on a Sunday 04:00") makes **individual journeys** inferable. The 95%-re-identification-from-4-points finding from mobility-privacy research applies directly.

**Why it happens:**
"Street-level aggregation" sounds anonymous but isn't unless the aggregate is large enough to hide individuals. No k-anonymity threshold is currently documented.

**How to avoid:**
- **Add a k-anonymity floor** on public responses: if `count < k_min` (suggested `k_min = 5`) for a given `(street, class, bucket)`, return `null` or collapse into "< 5". Cividis ramp handles `null` gracefully via the existing coalesce guard.
- Coarser buckets for sparse times: fall back to hourly or daily aggregation when 15-min counts are sparse.
- Document the privacy model explicitly in a public-facing `PRIVACY.md` (needed for ethics review anyway).
- For the research ethics board (UCD): explicit data-protection-impact-assessment (DPIA) even though the outputs are "aggregated counts". The ICO expects DPIA for any public-space monitoring.

**Warning signs:**
- A public `/api/streets/[id]/readings` response with single-digit counts at 15-min resolution.
- Logs show repeated requests for the same `(street_id, class)` at high time resolution (suggests scraping / inference attempt).

**Phase to address:** M2 — before the public map goes live. Add the k-min threshold at repo layer (applies to both mock and live).

**Severity:** **HIGH** — not TRL-6-demo-ending, but ethics-review-failing and reputationally fatal if published without.

---

### Pitfall 11: Payload codec ambiguity (zero vs absent class count)

**What goes wrong:**
The LoRa payload codec carries 9 class counts in a fixed compact format. Two encoding choices bite:
1. **0 vs absent**: if a class is encoded as `00` when absent and `00` when count is zero, the server cannot distinguish "sensor saw nothing" from "sensor didn't report this class" (e.g. due to a class-filter change in config). Breaks reconciliation.
2. **Bit-packing off-by-one**: encoding 9 counts × 7 bits packed into 8 bytes is tempting; a single-bit shift somewhere in the decoder produces plausible-but-wrong numbers that pass zod validation. Base64 decoder issues like this are documented on RAK/TTN forums (`forum.rakwireless.com/t/rak7268-problem-decoding-cayennelpp`).

**Why it happens:**
Custom codec under payload pressure; no round-trip fuzz test.

**How to avoid:**
- **Schema versioning from v1.0**: 1-byte codec version prefix. Server rejects unknown versions; a later codec change never silently corrupts old data.
- **Round-trip property test**: Python `hypothesis` on the encoder, TypeScript `fast-check` on the decoder; any `(counts, timestamp, camera_id)` tuple must survive encode→decode→equals.
- **Always encode all 9 classes** (fixed layout); absence ≠ zero. If a class is disabled by config, send a sentinel `0xFF` count and handle explicitly server-side.
- Pin the cam-ID + timestamp + 9-counts layout in `docs/PROTOCOL.md §LoRa` as a **normative table** with byte offsets, before any device is provisioned.

**Warning signs:**
- A reconciliation mismatch that disappears when you manually re-parse the payload.
- Byte-boundary errors after firmware upgrade.

**Phase to address:** M1 — LoRa codec design phase. Property tests in the same PR as the codec.

**Severity:** **HIGH** — a codec bug is easy to fix but impossible to retroactively correct in historic data.

---

### Pitfall 12: MapLibre canvas sizing race returns when Strict Mode re-enabled

**What goes wrong:**
`dashboard/next.config.mjs:6` currently has `reactStrictMode: false` as a workaround for the mount/cleanup/mount race in MapLibre's init (documented in `CONCERNS.md §1`). Re-enabling Strict Mode (listed in `TODO.md:146-148` as future work) can resurrect the race if the inline-style + ResizeObserver guards are insufficient. The symptom is a white/empty map on first load — exactly what the dashboard demo is most judged by.

**Why it happens:**
React 18+ Strict Mode intentionally double-invokes effects in dev to catch cleanup bugs. MapLibre holds GPU resources across effect cycles.

**How to avoid:**
- Don't re-enable Strict Mode **during** the 5-week sprint. Defer to post-demo cleanup.
- If re-enabled later, wrap the `new Map(...)` call with an `isMounted` ref guard: the second invocation (from Strict Mode cleanup+remount) detects the existing instance and skips re-init.
- Retain the ResizeObserver and inline-style fallback as permanent belt-and-braces — they're cheap.
- Playwright test that simulates double-mount (unmount then re-render) and asserts the canvas has non-zero dimensions.

**Warning signs:**
- Blank white map where tiles should render.
- Console: "WebGL context lost" or "MapLibre: Already initialized".
- Intermittent CI flakes on the Playwright smoke test.

**Phase to address:** Post-M2 cleanup phase. **Do not touch during the TRL-6 sprint.**

**Severity:** **MEDIUM** (sourced from `CONCERNS.md §1`) — only MEDIUM because the fix is "leave it alone for 5 weeks".

---

### Pitfall 13: Live-mode 501 stubs silently accept sensor data into the void

**What goes wrong:**
`CONCERNS.md §1` captures this: every `/api/ingest/*` route in `live` mode returns `{ error: "live_mode_not_implemented" }` with HTTP 501. If a researcher points a Pi at a Vercel deploy that was flipped to `CAMINA_DATA_SOURCE=live` before the live repo is implemented, the sensor hits 501 on every POST. The OfflineBuffer treats 5xx as retryable and backs off — but 501 is a *permanent* client contract error, not a transient outage. The sensor buffers forever, drops oldest after 10k messages, and the researcher discovers a week of lost data on the morning of the demo.

**Why it happens:**
501 is normally "not implemented yet" = tech-debt marker, not an operational signal. Edge agent doesn't distinguish.

**How to avoid:**
- **Boot-time guard on the dashboard**: if `CAMINA_DATA_SOURCE=live` and any ingest route's live implementation returns 501, refuse to start (or at minimum, have a `/api/health` route that reports degraded).
- **Edge agent: treat 501 as dead-letter**, not retry. Log ERROR loudly, flag in next heartbeat, don't fill the outbox.
- **Config sequencing**: never flip `CAMINA_DATA_SOURCE=live` until D5 (ingest) **and** D3 (DB migration) are green.

**Warning signs:**
- Daemon logs show `http_status=501` retries.
- OfflineBuffer depth grows without ever draining.
- Server `/api/health` reports OK while `/api/ingest/*` 501s.

**Phase to address:** M2 — before any `vercel env` change to `CAMINA_DATA_SOURCE=live`. Elevate in `TODO.md §D5` acceptance criteria.

**Severity:** **HIGH** (sourced from `CONCERNS.md §1`) — a misordered env change silently drops a week of data.

---

### Pitfall 14: Vercel Cron idempotency assumed but not enforced

**What goes wrong:**
Plan 02 §4 relies on Vercel Cron for `refresh-aggregates` (every 5 min), `detect-silent` (every 15 min), and `reconcile-daily` (01:00 UTC). Vercel Cron may retry up to 3× on non-2xx response. The materialized-view refresh is `CONCURRENTLY`, fine. But the reconciliation job inserts audit rows, emits admin events, and may toggle `sensors.active` — all non-idempotent if written naively. A flaky 01:00 UTC DB query → Vercel retries → duplicate events, duplicate audit entries, flipping active flag twice.

**Why it happens:**
"Vercel Cron = always once" is a common misassumption. It's at-least-once.

**How to avoid:**
- Verify the cron origin in every handler (`cron-auth.ts` — currently fails open when `VERCEL_CRON_SECRET` is unset per `CONCERNS.md §3`; fix that first).
- Every cron-triggered write uses an **idempotency key** = `(cron_job_name, triggered_at_minute)`. Either `INSERT ... ON CONFLICT DO NOTHING` on an idempotency table, or advisory lock via `pg_try_advisory_lock(hash(cron_name || minute))`.
- Long-running crons (reconciliation) should hold the advisory lock for the job's duration to prevent overlap.

**Warning signs:**
- Duplicate rows in `audit_log` with matching `actor_email='cron'` and identical content minutes apart.
- Admin events repeat.

**Phase to address:** M2 — D12 (crons). Before the silent-sensor cron fires in production.

**Severity:** **MEDIUM** — cleanable post-facto but pollutes the audit trail.

---

### Pitfall 15: Dataset/model licensing blocks academic publication

**What goes wrong:**
CAMINAv1 is a fine-tuned YOLO11 model trained on the `SDL fine-tuned_v3-cyclist_cleaned.zip` dataset (76 MB in `custom_model_train/`). The INTERREG deliverable implicitly expects a paper at TRL-7+. YOLO11 is AGPL-3.0 (Ultralytics); the training dataset provenance is not documented in `data.md`. If the dataset contains frames from CC-BY / non-commercial / unlicensed sources, the paper's accompanying artifact release (model weights + test images) can trigger a publication hold or retraction request.

**Why it happens:**
Datasets accumulate organically; provenance documentation often lags the training runs.

**How to avoid:**
- Write `custom_model_train/data.md` with: every source video/image, its license, who labelled it, when. Do this **now**, while memory is fresh.
- Confirm AGPL-3.0 obligations are manageable for the UCD publication: AGPL requires source disclosure of the server code if it's distributed. `CONCERNS.md §LICENSE` already flags the 189-byte LICENSE file as needing inspection.
- Plan a "clean" release dataset separate from the training set: 50–100 labelled test frames you own fully (film them yourself at a UCD-approved site) that can be shipped with the paper without licensing friction.

**Warning signs:**
- Anyone asks "where did this training image come from?" and there's no answer.
- The paper is written and the ethics reviewer asks for DPIA + dataset DSPA.

**Phase to address:** **Do not block TRL-6 on this — but document provenance during the M1 window while context is fresh.** Address fully post-demo, before any paper submission.

**Severity:** **MEDIUM** — does not block TRL-6 demo; does block publication.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Shared dev Bearer token for all sensors (`CAMINA_DEV_INGEST_TOKEN`) | Fast iteration in M1 | Replay + compromise affects all future sensors; must be rotated before multi-site | Only pre-first-real-deployment; **rotate and kill the shared token** before M2 goes live |
| `NEXT_PUBLIC_CAMINA_DEV_ADMIN` dev flag | Quick admin UI preview | Build-time inlined, catastrophic if leaked — see Pitfall 2 | Only with the build-time guard added; otherwise never |
| `reactStrictMode: false` in Next config | Unblocks MapLibre work | Masks every future effect cleanup bug | Only for this sprint; re-enable post-demo |
| `state.db` on SD card | Works out of the box | SD card corruption cliff — see Pitfall 9 | Never for a >24h deployment |
| `cacheComponents: false` in Next config | Unblocks `/[city]` routing | Leaves PPR perf wins on the table | Only until `<Suspense>` is added around uncached reads |
| Triplicated YOLO weights in git | Easy "git clone just works" | 230 MB of binary bloat; slow CI clones | Never; move to Git LFS or external artifact store |
| Manual Bearer rotation via SSH | No auth infra needed at TRL-5 | Every rotation = plane ride to Dublin | Acceptable at TRL-5/6; move to per-device argon2 hash before TRL-7 |
| Opaque `200-char` ASCII LoRa payload | Easy to eyeball in logs | ~25 % overhead vs pure binary, pushes SF to dangerous levels | Only if airtime budget (Pitfall 5) still passes at worst-case SF |
| Running Drizzle `0000_init.sql` by hand | Fast bootstrap | Schema drift, no rollback | Only on the first Neon branch; automate before D3 merges |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **TTN webhook → `/api/ingest/lora/*`** | Trust TTN's `hmac` header without verifying; miss the replay window | Verify HMAC per TTN docs; reject payloads older than 5 min; idempotency on `(dev_eui, f_cnt)` |
| **Neon Postgres** | Using unpooled `DATABASE_URL_UNPOOLED` in request-path code | Pooled for routes, unpooled only in migrations. Grep CI for `unpooled` in `src/app/api/**` |
| **Vercel Cron** | Assuming once-per-trigger | At-least-once; idempotency keys required (Pitfall 14) |
| **Google OAuth** | Verification lag on `ucd.ie` domain | Use **UCD Google Workspace internal app type** (no verification); start the OAuth client creation in week 1, not week 5 |
| **Protomaps PMTiles on Vercel Blob** | Hosting unversioned `dublin.pmtiles` | Include a hash in the filename, CDN caches forever; lets you iterate basemap without invalidating all caches |
| **Sentry** | PII scrubber forgotten; GPS leaks in breadcrumbs | Server: scrub `latitude`/`longitude` from every event body. Client: never capture admin-page context |
| **Vercel preview URLs** | Anonymous-by-default (publicly indexable) | Enable Vercel Deployment Protection (password) on preview; or keep `CAMINA_DATA_SOURCE=mock` for every preview |
| **Upstash Ratelimit** | Rate-limiter itself unavailable → fail-open | Explicitly `fail-closed` on ratelimit backend errors for admin mutations; fail-open acceptable for `/api/streets` |
| **libcamera on Pi 5** | Bookworm → Trixie upgrade changes the video pipeline | Pin OS to Raspberry Pi OS Bookworm 64-bit for the demo; don't `apt upgrade` the week before deploy |
| **systemd** | `Restart=always` with no `StartLimitBurst` | Loop-crash storm fills syslog and burns SD card I/O; use `Restart=on-failure` + `RestartSec=10` + `StartLimitIntervalSec=600` + `StartLimitBurst=5` |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `streets-mock.ts` reloads JSON fixtures every request | Slow cold starts; cold-start latency > 1 s | Wrap `loadReadings()` in `React.cache` at module scope | Any deploy with > 30 days of fake readings |
| Raw `sensor_readings` queried in hot path | `/api/streets/[id]/readings` slow, bad p95 | Always query `street_readings_15m` or `_hourly` MV; never the base table in request path | > 100k readings |
| Materialized view `REFRESH` without `CONCURRENTLY` | Admin queries block during refresh | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requires unique index, already planned) | Anytime with > 1 concurrent admin |
| OfflineBuffer drain sends 50 msgs in a tight loop | Neon connection spike, 5xx storm | Rate-limit the drain: `drain(send_fn, max=50, max_rps=5)` | Any reconnect after > 10 min outage |
| MapLibre re-renders entire `feature-state` on every metric change | Jank on metric toggle | Mutate only the changed keys, not `setFeatureState` in a loop | > 50 streets on the map |
| Admin writes without `revalidateTag` | Public map shows stale counts for up to cache TTL | Every admin mutation calls `revalidateTag('streets:list')` + relevant per-street tags | Always |
| Full `/api/streets` response per client page load | Big JSON payload on mobile 4G | Gzip + bounded bbox + `ETag`; 60 s `s-maxage` on the edge | > 100 streets |
| Heartbeat retention growing forever | `sensor_heartbeats` table fills Neon free tier | Cron that prunes rows > 14 days old (already in Plan 02 §8 comment — ensure it's actually scheduled) | ~30 days / 500 sensors |
| `useEffect(() => fetch(...), [])` in StreetMap without AbortController | Race between unmount + late response | Always pass an AbortController; cancel on unmount | Fast route changes / back-navigation |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` deployed to preview/prod | Full sensor GPS + metadata leak to anonymous visitors | Build-time guard (Pitfall 2); pre-push checklist |
| Auth allowlist defaults to allow-any | Any Google account reaches `/admin` | Fail-closed default (Pitfall 3); module-init assertion |
| Sensor token in git-tracked YAML (`configs/sensor.yaml:8`) | Token leak on any repo clone | Keep placeholder `REPLACE_WITH...`; real token only in Pi's local config, never committed |
| Privacy regression test only checks mock responses | Live responses can ship a GPS field and pass CI | Extend privacy regression to hit live adapter with Dockerized Postgres (already in `TODO.md §12` — elevate) |
| Sentry breadcrumbs include request bodies | GPS in error reports sent to Sentry cloud | `beforeSend` hook scrubs `latitude`, `longitude`, `sensor_id` from every event |
| `vercel env pull` into a committed file | Leaks `AUTH_SECRET` into git | `.gitignore .env.local` AND `.env*.local`; pre-commit hook (e.g. `gitleaks`) |
| Google OAuth redirect URI mismatch on preview | Login stuck in redirect loop, researcher pastes tokens in Slack to debug | Use wildcard-compatible `AUTH_URL` resolution, document the OAuth client URIs in RUNBOOK |
| Admin routes assume `role=admin` from JWT without server re-check | Stale session escalation after role revocation | Every `/admin/*` route server-side re-checks role against DB on every request |
| Cron secret unset in preview = open cron routes | Any visitor can trigger aggregate refresh | Fail-closed when `VERCEL_ENV` is preview/production (Pitfall 14) |
| Public `/api/streets/[id]/readings` returns single-digit counts | Individual journey re-identification | k-anonymity floor (Pitfall 10), `null` below threshold |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Blank white map on fresh clone (tiles not downloaded) | First-run confusion for collaborators | Dev-only banner: "Tiles missing. Run `pnpm exec node scripts/download-dublin-tiles.mjs`" (also per `CONCERNS.md §4`) |
| Panning outside covered Dublin bbox → 404 tile storm | "Is this broken?" | Set `maxBounds` on MapLibre (per `CONCERNS.md §4`); no invisible walls, just a hard edge |
| Colour-only encoding of metric | Inaccessible for colour-blind users | Numeric label in tooltip + side panel; verified viridis/cividis already per `plan/02 §9-ter` |
| "Awaiting device ack" never flips to "applied" | Admin thinks the system is broken when it's just waiting for next window | Show the exact expected ETA: "applied at HH:MM (next heartbeat)" |
| Silent sensor shown on map as "no data" | Looks like censorship of a street | Grey-out the street with "offline" label, not omission |
| Privacy pill hidden on small screens | Mobile visitor doesn't realise data is mocked | Keep "Mock data" pill always visible; move to top-centre on mobile per `plan/02 §9-bis` |
| Reconciliation mismatch shown as red error | Researchers panic | Neutral event with context: "Daily total differs by N; likely cause: buffered windows replayed late" |
| Admin preview colour-blind toggle only on `/admin` | Designers miss it | Accessible from any authenticated page via keyboard shortcut `?` + toggle |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Pi 5 sensor deployment:** Often missing active-cooler benchmark AND 48-hour soak — verify both in `docs/sensor_deployment.md`
- [ ] **LoRa codec:** Often missing airtime budget at worst-case SF — verify with TTN simulator / airtime calculator before provisioning
- [ ] **Neon connection:** Often missing pooled-URL distinction — grep `DATABASE_URL_UNPOOLED` in `src/app/api/**` returns empty
- [ ] **Privacy regression test:** Often missing live-adapter coverage — verify Dockerized Postgres CI job exists
- [ ] **Google OAuth:** Often missing the "verified app" step for external emails — verify `internal app type` in Google Cloud console
- [ ] **Vercel preview protection:** Often missing — verify `vercel.com/<team>/<project>/settings/deployment-protection` is not "None"
- [ ] **Cron auth:** Often missing — verify `VERCEL_CRON_SECRET` is set in every environment
- [ ] **Sentry PII scrubber:** Often missing — verify a test error with `latitude` in body does not leak that field to Sentry project
- [ ] **Silent-sensor alert:** Often missing email/Slack integration — verify the cron actually pages on a simulated outage
- [ ] **systemd watchdog:** Often missing — verify `systemctl status camina-sensor` shows `WatchdogSec`, and kill the process to confirm recovery
- [ ] **SD-card vs SSD for state.db:** Often missing — verify `lsblk` on Pi shows `state.db` is on a block device that is not the SD card
- [ ] **Clock sync:** Often missing `Requires=time-sync.target` — verify daemon refuses to start when NTP not yet synced
- [ ] **Dataset provenance:** Often missing `custom_model_train/data.md` with sources and licenses — verify before paper submission
- [ ] **k-anonymity floor:** Often missing on public readings API — verify single-digit counts in fixtures return `null`
- [ ] **Rolling release health gate:** Often missing — verify a synthetic 5xx causes auto-rollback

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Pi thermal throttling discovered at demo | LOW | Drop target FPS in config, push config bump; the `ConfigPoller` applies within 15 min |
| `NEXT_PUBLIC_CAMINA_DEV_ADMIN` leaked GPS | HIGH | 1) Immediate redeploy with flag removed. 2) Assume coords are public; they cannot be un-leaked. 3) Document the incident for ethics board. 4) Move the affected sensors (physically) if they're still operational |
| Allowlist-any Google signin exploited | HIGH | 1) Remove preview deploy. 2) Rotate `AUTH_SECRET`, forcing all sessions invalid. 3) Audit `audit_log` for unauthorized rows. 4) Fix the auth default before redeploy |
| `rpicam` OOM loop | MEDIUM | 1) Enable systemd watchdog immediately (minutes). 2) Downgrade `rpicam-apps` to last known good (hours). 3) Patch camera re-init path to not re-allocate on exception |
| TTN FUP exhaustion | MEDIUM | 1) Switch affected sensor to HTTPS transport via config flag. 2) Re-deploy with lower publish frequency or smaller payload codec |
| Neon connection exhaustion | LOW | 1) Increase Neon pool size in Neon console (immediate). 2) Add Upstash ratelimit in next deploy. 3) Rate-limit OfflineBuffer drain in next firmware |
| SD card corrupt `state.db` | MEDIUM | 1) Rename to `state.db.broken.*` on boot; start fresh. 2) Restore `daily_totals` from last reconciliation on server. 3) Swap to SSD on next site visit |
| Clock drift corrupting windows | LOW | 1) Fix NTP at boot. 2) Re-run reconciliation with `produced_at` vs `received_at` delta tolerance. 3) Accept the bad day as "partial" in the audit log |
| Street-level inference leak discovered post-launch | HIGH | 1) Flip k-anonymity floor on immediately. 2) Purge historical `sensor_readings` older than necessary. 3) Notify ethics board |
| LoRa codec version mismatch | MEDIUM | 1) Server rejects new version payloads until decoder deployed. 2) Historic payloads remain correctly decoded via version prefix |
| MapLibre canvas race (after Strict Mode re-enabled) | LOW | Revert Strict Mode change; re-enable post-demo |
| Live-mode 501 silently buffered | MEDIUM | 1) Add `/api/health` check for ingest route. 2) Replay OfflineBuffer after live-mode fix deployed |
| Cron duplicate audit rows | LOW | Deduplicate in a backfill query; add idempotency key going forward |
| Dataset license issue | HIGH (for paper) | Re-shoot test frames the team owns fully; re-release dataset. Demo unaffected |
| Single Pi fails during demo | MEDIUM | Swap in cold-spare Pi (if provisioned per Pitfall 6); OfflineBuffer covers the gap; reconciliation stitches the day |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Pi thermal throttling | M1 — Pi integration | 30-min sustained benchmark log in `docs/sensor_deployment.md`; `vcgencmd get_throttled == 0x0` |
| 2. `NEXT_PUBLIC` leak | M2 — D14 deploy hardening (pre-preview) | Build fails when env misconfigured; test in `dashboard/tests/unit/` |
| 3. Auth allowlist fail-open | M2 — D2 Auth wiring | Unit test: empty allowlist + `NODE_ENV=production` raises at module init |
| 4. `rpicam` OOM | M1 — sensor daemon wiring | 48-h soak on bench; watchdog proven via kill-9 |
| 5. TTN FUP | M1 — LoRa codec phase | Airtime calculator result committed next to codec; ADR simulation covers SF7–SF12 |
| 6. Single-sensor SPOF | M2 — deployment phase | Cold-spare Pi exists and is bench-tested; uptime monitor pages a test phone |
| 7. Clock drift | M1 — systemd service | Daemon refuses to start without NTP sync; integration test with clock skew |
| 8. Neon connection exhaustion | M2 — D5 ingest API + D13 rate limits | Grep CI: no unpooled URL in hot path; load test (k6) with 50 concurrent devices |
| 9. SD-card corruption | M1 — hardware provisioning | `lsblk` shows `state.db` on SSD; `integrity_check` in daemon start; backup cron |
| 10. Street-level inference | M2 — D4 public API | Privacy regression extended: count < 5 returns null; DPIA filed |
| 11. Codec ambiguity | M1 — LoRa codec PR | Property-based round-trip test in CI; codec version byte mandated |
| 12. MapLibre Strict Mode race | **Deferred** (post-TRL-6) | Playwright double-mount test before re-enabling Strict Mode |
| 13. Live-mode 501 silent drop | M2 — D5 ingest API | `/api/health` reports degraded when ingest routes return 501; edge agent treats 501 as dead-letter |
| 14. Vercel Cron non-idempotency | M2 — D12 crons | Idempotency key unit test; advisory lock on reconciliation; cron secret required in preview/prod |
| 15. Dataset licensing | Parallel to M1 (research backlog), not demo-blocking | `custom_model_train/data.md` complete and reviewed by UCD ethics |

---

## Sources

- Raspberry Pi thermal behaviour:
  - [Raspberry Pi Heating and Cooling article (official)](https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/)
  - [Raspberry Pi 5 Thermal Showdown: Active Cooler vs Passive (Medium, 2026)](https://medium.com/@mahinshanazeer/raspberry-pi-5-thermal-showdown-active-cooler-vs-passive-cooling-796d5f68b8fb)
  - [SunFounder Pi Temperature Guide](https://www.sunfounder.com/blogs/news/raspberry-pi-temperature-guide-how-to-check-throttling-limits-cooling-tips)
- Camera stack issues:
  - [rpicam-apps issue #640 — memory leak leading to OOM](https://github.com/raspberrypi/rpicam-apps/issues/640)
  - [picamera2 issue #887 — cannot allocate memory after repeated camera lifecycle](https://github.com/raspberrypi/picamera2/issues/887)
- TTN / LoRaWAN:
  - [TTN Fair Use Policy — 30 s airtime / 10 downlinks per 24 h per device](https://www.thethingsnetwork.org/forum/t/fair-use-policy-explained/1300)
  - [TTN Duty Cycle documentation](https://www.thethingsnetwork.org/docs/lorawan/duty-cycle/)
  - [TTN Fair Use Policy (Forum guidelines)](https://www.thethingsnetwork.org/forum/t/the-things-network-fair-use-policy/47689)
  - [LoRaWAN payload encoding (Tetraedre)](https://www.tetraedre.com/publication.php?publication_id=169&book_id=7&chapter_id=12)
  - [CayenneLPP payload format (The Things Industries)](https://www.thethingsindustries.com/docs/integrations/payload-formatters/cayenne/)
  - [RAK7268 Base64 CayenneLPP decoding issue (forum)](https://forum.rakwireless.com/t/rak7268-problem-decoding-cayennelpp/6505)
- Vercel + Neon:
  - [Neon Docs — Connecting from Vercel](https://neon.com/docs/guides/vercel-connection-methods)
  - [Vercel KB — Managing DB connection pools with Fluid Compute](https://vercel.com/kb/guide/efficiently-manage-database-connection-pools-with-fluid-compute)
  - [Vercel Blog — Serverless compute-to-database connection problem](https://vercel.com/blog/the-real-serverless-compute-to-database-connection-problem-solved)
  - [Postgres Connection Exhaustion with Vercel Fluid (Sólberg)](https://www.solberg.is/vercel-fluid-backpressure)
- SQLite + SD card reliability:
  - [SQLite — How to corrupt an SQLite database file](https://sqlite.org/howtocorrupt.html)
  - [SQLite — Write-Ahead Logging](https://sqlite.org/wal.html)
  - [Raspberry Pi Forums — SD card power failure resilience](https://forums.raspberrypi.com/viewtopic.php?t=253104)
- Privacy / GDPR:
  - [ICO — Ensuring anonymisation is effective](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/how-do-we-ensure-anonymisation-is-effective/)
  - [PNAS — Towards formalizing the GDPR's notion of singling out](https://www.pnas.org/doi/10.1073/pnas.1914598117)
  - [TechGDPR — Privacy by Design for Technology Development Teams](https://techgdpr.com/blog/privacy-by-design-for-technology-development-teams/)
  - [Terabee — Are People Counting devices GDPR compliant?](https://www.terabee.com/are-people-counting-devices-gdpr-compliant/)
- Internal:
  - `.planning/PROJECT.md` (CAMINA project brief, 2026-04-23)
  - `.planning/codebase/CONCERNS.md` (codebase concerns audit, 2026-04-23) — pitfalls 2, 3, 12, 13 sourced here
  - `plan/01-windowed-counter-and-ingest.md` (Plan 01 design)
  - `plan/02-dashboard-vercel.md` (Plan 02 design)
  - `TODO.md` (open items)

---
*Pitfalls research for: Privacy-first edge-CV + LoRaWAN + serverless dashboard — CAMINA TRL-6 demo*
*Researched: 2026-04-23*
