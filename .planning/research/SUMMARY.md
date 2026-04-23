# Project Research Summary

**Project:** CAMINA — privacy-first traffic-sensor network (TRL-6, one-Pi one-street Dublin demo)
**Domain:** Brownfield — edge-CV (Python/NCNN on Pi 5) + LoRaWAN + Next.js 16 on Vercel
**Researched:** 2026-04-23
**Confidence:** HIGH (stack, features, architecture) / MEDIUM (LoRa, pending hardware + TTN coverage)

> **One-stop briefing.** If you are the REQUIREMENTS or ROADMAP agent, you do not need to open `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, or `PITFALLS.md` unless drilling into detail. Each section below points back to the authoritative file when depth is needed.

---

## Executive Summary

CAMINA is a **brownfield finishing sprint, not a greenfield architecture problem.** Plan 01 shipped (60 tests green) and Plan 02 is scaffolded in mock mode. The 2026-04-23 research confirms the existing stack choices (YOLO11n + NCNN on Pi 5, Next.js 16 App Router on Fluid Compute, Neon + Drizzle + PostGIS, Auth.js v5 + Google, MapLibre + Protomaps, MQTT rejected, Docker rejected, TimescaleDB rejected) are **correct for 2026**. No architecture changes are required. What remains is wiring, one important driver-lifecycle fix (`attachDatabasePool`), one transport refactor (extract a `Publisher` interface before writing `LoRaPublisher`), one procurement-gated unknown (RAK3172 + TTN Dublin coverage), and three regulatory artefacts missing from PROJECT.md (DPIA, public privacy statement, physical signage).

The two highest-risk unknowns are **Pi 5 FPS on the fine-tuned CAMINAv1 NCNN model with picamera2 + tracker + windowed counter in-enclosure** (derisks the entire demo — must run in week 1) and **TTN Community coverage at the target Dublin street** (procurement-lead item — must be verified in week 1 even if code lands later). Every other risk is downstream of these two. The architecture research re-weights the PROJECT.md M1/M2 split into a week-by-week plan that starts both derisk spikes in week 1, fixes the Vercel pool lifecycle + PPR Suspense boundaries in parallel, delivers the LoRa codec + publisher in week 2, lands the Neon + OAuth + admin CRUD + crons in week 3, hardens and deploys in week 4, and reserves week 5 for integration soak and slip-absorption.

The **single most-impactful code change surfaced by research** is adding `attachDatabasePool(client)` from `@vercel/functions` to `dashboard/src/lib/db.ts` — without it, Rolling Releases on Vercel Fluid Compute will exhaust Neon's connection pool when the new and old deployments both hold warm pools. This is one line of code and the single highest-leverage stack fix.

---

## Key Findings

### Stack decision — lock-in

**Confidence: HIGH.** The existing stack survives the 2026 review intact. Detail in `STACK.md`.

**Locked-in core (keep):** Python 3.11 + Ultralytics 8.3.x + YOLO11n NCNN on Pi 5 8GB; picamera2 + libcamera (switch off `cv2.VideoCapture` for Pi Cam 3); filterpy + scipy Kalman/Hungarian; httpx + pydantic; systemd with `Type=notify` + `WatchdogSec=60` + `sd_notify`; `opencv-python-headless` on the Pi. RAK3172 breakout/WisBlock over UART with a hand-rolled `pyserial` AT driver; TTN Community v3 webhook → `/api/ingest/lora/uplink`; custom 17-byte `struct.pack` codec (3 B camera ID + 4 B epoch + 9 B class counts + 1 B schema version), base64 to ~24 chars on the wire. Next.js 16 App Router on Fluid Compute (never Edge runtime); Drizzle 0.36 + `drizzle-kit` 0.29; postgres.js 3.4 with `{ max: 5, prepare: false, idle_timeout: 5 }`; Neon Postgres + PostGIS (pooled URL for routes, unpooled for migrations); Auth.js v5 + Google; MapLibre GL 4.7 + PMTiles on Vercel Blob; Tailwind 3.4 (no v4 migration in sprint); zod 3.23 (no v4 migration in sprint).

**One critical missing dep** — install `@vercel/functions` and call `attachDatabasePool(client)` immediately after constructing the `postgres()` client. This is the highest-leverage single change in the stack review and prevents connection exhaustion under Rolling Releases. **Confidence: HIGH** (Vercel official docs).

**Also add:** `@upstash/ratelimit` + `@upstash/redis` (sliding-window rate limiting); `@sentry/nextjs` with PII scrubber stripping `sensor_id`/`latitude`/`longitude`; `@vercel/analytics`; `@vercel/speed-insights`; `systemd-watchdog` on the Pi.

### Feature roll-up

**Confidence: HIGH for competitor/table-stakes items, MEDIUM for GDPR interpretation.** Detail in `FEATURES.md`.

| Tier | Feature | Status | Phase |
|---|---|---|---|
| **Table stakes** | Multi-class classification, 15-min aggregation, edge-only inference, public map, metric toggle, class filter, time-window selector, per-street time series, device-health visibility, admin auth, Bearer device auth, offline buffer, daily reconciliation, HTTPS+TLS, documented retention, audit log, CSV/JSON export | Mostly validated; CSV export + audit-log writer still open | M2 (W3) |
| **Differentiators (CAMINA-only)** | 9 domain-tuned classes incl. e-scooter/SUV/delivery-van, dual-transport HTTPS+LoRaWAN, full open reproducibility, street-level k-sensor guard, version-gated hot config, shareable `#z/lat/lon` URL hashes, CB-safe ramps with admin preview, mobile-first bottom sheet, dev-mode mock dashboard, per-class speed breakdown | Most validated; k-sensor guard + CSV export still open | M1/M2 |
| **Anti-features (never)** | Facial recognition, ANPR, cross-camera re-ID, exact GPS in public UI, raw image/video upload, ML forecasting, anonymous admin, short-lived JWT in v1, multi-city, native mobile apps, 99.9 % SLA, OTA in v1, i18n beyond English | Enforced by design + tests | — |

**Three regulatory gaps NOT currently in PROJECT.md Active — must be added to REQUIREMENTS as M2 deliverables (W3–W4):**

1. **DPIA document** (`docs/PRIVACY/DPIA.md`) — ICO mandates a Data Protection Impact Assessment for any public-space surveillance system before deployment. UCD ethics will also request it.
2. **Public privacy statement / data-collection notice** on the dashboard (`/about` or footer link).
3. **Physical signage at the sensor site** ("CAMINA research sensor — aggregate counts only, no video recorded, contact …") — ICO CCTV/ANPR guidance requires clear signage at the deployment site.

All three are LOW–MEDIUM complexity individually; together they are a 1-day documentation task that unblocks ethics sign-off.

### Architecture directives (load-bearing)

**Confidence: HIGH** on cloud patterns, **MEDIUM** on LoRa (procurement-gated). Detail in `ARCHITECTURE.md`.

Six directives the ROADMAP must honour:

1. **Extract `Publisher` interface before writing `LoRaPublisher`.** `HttpsPublisher` is currently concrete and `SensorDaemon` knows it. Hoist to a `Protocol` with `publish(endpoint, payload) -> PublishResult`. `OfflineBuffer`'s `(endpoint, payload)` schema is already transport-agnostic. ~50–100 line refactor; zero behaviour change; unblocks LoRa cleanly. **Must land in W1.**
2. **LoRa is counts-only, uplink-only, 15-min cadence.** TTN Fair Use Policy: 30 s airtime/day per device, 10 downlinks/day per device. Heartbeats and config polls stay on HTTPS. Sensors configured `transport=lora` have no `ConfigPoller` and no heartbeat loop; silent-sensor cron uses uplink timestamps for liveness on LoRa-only devices.
3. **Pi FPS benchmark is a W1 derisker, not a W4 check.** FPS / thermal / memory on Pi 5 with CAMINAv1 NCNN + tracker + in-enclosure is the highest-risk unknown. Expected 6.8–8 FPS at `imgsz=640`, 10–12 FPS at `imgsz=480`. If below 5 FPS at `imgsz=480`, scope collapses to HTTPS-only; Hailo-8L HAT is **not** the fallback.
4. **Static shell + streamed metrics (PPR / Next.js 16 `cacheComponents`).** Wrap dynamic reads in `<Suspense>`, annotate `MapShell` with `'use cache'`, re-enable `cacheComponents: true`. 1-day cleanup in W1.
5. **Right-to-erasure via `ON DELETE CASCADE` from `sensors`.** The public MV `street_readings_15m` is aggregate-only (no `sensor_id`) — EDPB-compatible. Add **k-anonymity floor on public responses** (`k_min = 5`; collapse to `null` below threshold) in the repo layer for both mock and live adapters.
6. **systemd over Docker on the Pi.** Single-node, solo-researcher, TRL-6. Balena/Docker becomes compelling at 10+ devices with OTA — explicitly deferred to TRL-7.

### Pitfall top-10 (ranked by severity × timeline-risk)

**Confidence: HIGH.** Full 15-pitfall catalogue in `PITFALLS.md`.

| # | Pitfall | Severity | Phase | Mitigation (one-line) |
|---|---|---|---|---|
| 1 | `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` leaks GPS to prod (inlined at build time) | **CRITICAL** | M2 W4 | Build-time guard in `vercel.ts`: fail build if `VERCEL_ENV ∈ {preview, production}` and flag is true |
| 2 | Dev Google allowlist accepts any email when `CAMINA_DEV_ALLOWED_EMAILS` empty (fail-open) | **CRITICAL** | M2 W3 | Fail-closed when `NODE_ENV=production` or `VERCEL_ENV` set; module-init assertion |
| 3 | TTN Fair Use Policy (30 s/day airtime) silently drops uplinks if ADR picks SF10+ | **CRITICAL** | M1 W1–W2 | Airtime budget at worst-case SF7–SF12 gate before `LoRaPublisher` merges; 17-byte payload; fall back to HTTPS if SF > 10 |
| 4 | `rpicam-apps` / `picamera2` memory leak OOMs daemon after hours | **CRITICAL** | M1 W1–W2 | Don't re-init camera on transient errors; systemd `WatchdogSec=300` + `sd_notify`; RSS in heartbeat; 48-h soak before M2 |
| 5 | Pi 5 thermal throttle silently corrupts FPS (85 °C in 90 s without active cooling) | **CRITICAL** | M1 W1 | Mandatory Pi 5 Official Active Cooler (€10); log `vcgencmd get_throttled` + temp in heartbeat |
| 6 | Neon connection exhaustion under ingest retry storm | HIGH | M2 W3 | `attachDatabasePool(client)`; pooled `DATABASE_URL` in request path; Upstash rate-limit per sensor |
| 7 | Live-mode 501 stubs silently accepted as retryable 5xx → OfflineBuffer fills | HIGH | M2 W3 | Edge agent treats 501 as dead-letter; boot-time guard refuses `CAMINA_DATA_SOURCE=live` if any ingest route returns 501 |
| 8 | SD-card corruption of `state.db` on power loss | HIGH | M1 W1 | Move `state.db` to USB SSD (€15–25); `PRAGMA synchronous=FULL`; `PRAGMA integrity_check` at boot; small UPS HAT |
| 9 | Clock drift on Pi (no RTC) mis-aligns windows vs server | HIGH | M1 W1 | systemd `Requires=time-sync.target`; daemon refuses to start until NTP synced; server rejects `abs(produced_at - server_now) > 60 s` |
| 10 | Street-level aggregates still leak journeys without k-anonymity floor | HIGH | M2 W3–W4 | `k_min = 5` on public responses; collapse to `null` / "< 5"; document in DPIA; hourly/daily fallback for sparse times |

---

## Re-weighted build order — authoritative week-by-week plan

**Confidence: HIGH.** Re-orders PROJECT.md's two-milestone shape into a 5-week plan. ROADMAP.md should expand each week into phase-level detail.

| Week | Dates | Theme | Deliverables | Gates |
|---|---|---|---|---|
| **W1** | 2026-04-24 → 2026-05-01 | **Kill highest-risk unknowns in parallel** | 1. `scripts/run_sensor.py` composes CAMINAv1 NCNN + tracker + `SensorDaemon`; first Pi FPS/thermal/memory benchmark (30-min sustained, in-enclosure). 2. Extract `Publisher` interface from `HttpsPublisher` (zero-behaviour refactor). 3. LoRa pre-work (no code): confirm TTN Dublin coverage (TTN Mapper + community forum), procure RAK3172 breakout + TTIG EU868 gateway if needed, design 17-byte codec on paper, compute airtime at SF7–SF12. 4. Dashboard cleanup: wrap `[city]/page.tsx` and `street/[slug]/page.tsx` in `<Suspense>`, re-enable `cacheComponents: true`, install `@vercel/functions` + wire `attachDatabasePool`. 5. Start Google OAuth client creation. | Pi FPS ≥ 5 at `imgsz=480`; TTN coverage confirmed OR TTIG gateway ordered; `attachDatabasePool` deployed to preview. |
| **W2** | 2026-05-02 → 2026-05-08 | **Deliver the edge demo** | 1. Pi benchmark fully documented; 48-h soak on bench; watchdog proven via `kill -9`. 2. End-to-end Pi → Vercel-preview HTTPS → mock DB for 24 h. 3. `LoRaPublisher` + `lora_codec.py` + mirrored TS `lora-codec.ts` + joint `hypothesis`/`fast-check` round-trip vectors in `tests/fixtures/lora/`. 4. `/api/ingest/lora/uplink` wired against a real TTN dev device. 5. NTP sync gating + SD-card → USB-SSD swap on deployment Pi. | Round-trip codec tests green; airtime budget documented; Pi 48-h soak passes with RSS flat. |
| **W3** | 2026-05-09 → 2026-05-15 | **Land the cloud live half** | 1. Neon provisioned via Vercel Marketplace; `0000_init.sql` applied; `streets-live.ts` implemented; mock/live parity tests green. 2. Google OAuth live; dev-allowlist env fallback removed; fail-closed default. 3. Admin CRUD: `<SensorForm>`, `<StreetDrawTool>`, `/admin/members`, audit log writer. 4. Cron bodies: `refresh-aggregates` (CONCURRENTLY + advisory lock), `detect-silent`, `reconcile-daily`. 5. `k_min = 5` floor in the repo layer. 6. Retention-enforcement cron (13-month raw). | CI grep: no `DATABASE_URL_UNPOOLED` in `src/app/api/**`; privacy regression extended to live adapter via Dockerized PG+PostGIS; first unauthenticated admin probe returns 401. |
| **W4** | 2026-05-16 → 2026-05-22 | **Harden and deploy** | 1. BotID on `/sign-in` + admin mutations; CSP + HSTS in `vercel.ts`; Upstash rate-limits. 2. Sentry client + server with `beforeSend` PII scrubber; Speed Insights; Analytics. 3. Rolling Releases 10 % → 50 % → 100 % with health gates + auto-rollback. 4. Uptime monitor on `/api/health`. 5. `dashboard/docs/RUNBOOK.md`. 6. **DPIA, public privacy statement, physical signage** committed. 7. Pi installed on the real Dublin street; 7-day soak begins. | Synthetic 5xx triggers auto-rollback in preview; Sentry test event with `latitude` in body confirms scrubber; DPIA + signage reviewed by UCD ethics. |
| **W5** | 2026-05-23 → 2026-05-31 | **TRL-6 soak + slip-absorption** | 1. Pi publishes to production Vercel → live Neon → public map for ≥ 7 days. 2. Cold-spare Pi bench-tested and swap-ready. 3. Daily reconciliation mismatches investigated. 4. RUNBOOK finalised; demo script rehearsed. 5. Any W2/W3 slip absorbed. | Continuous counts for ≥ 1 week (degraded-but-presentable acceptable); heartbeat-gap alert paged on simulated outage; INTERREG deliverable README ready. |

**What this re-ordering changes vs PROJECT.md's M1/M2 split:** PROJECT.md currently puts `scripts/run_sensor.py` AND the full LoRa stack both inside M1 (2026-05-15). Architecture research flags this as too much unvalidated hardware work for one milestone. The re-weighted plan splits M1 into W1 (risk-kill + refactor) and W2 (edge demo), giving M2 (W3–W5) two full weeks plus a buffer for Neon + OAuth + admin CRUD + crons + Rolling Releases + 7-day soak. The 2026-05-31 TRL-6 deadline is preserved.

---

## Implications for the ROADMAP

| ROADMAP phase | Source week | Research-depth needed | Why |
|---|---|---|---|
| Pi real-hardware integration + Publisher refactor + PPR cleanup | W1 | Skip research | Standard refactor + documented Next.js 16 PPR path |
| LoRa codec + publisher + TTN webhook + 48-h soak | W2 | **Needs `/gsd-research-phase`** | Procurement-gated; codec bit-layout and airtime numbers need verification on real hardware |
| Neon live half + Auth.js v5 + admin CRUD + cron bodies + k-anonymity | W3 | Skip research | Patterns verified |
| Security hardening + Rolling Releases + DPIA + signage | W4 | **Needs `/gsd-research-phase` for DPIA template** | UCD-specific ethics template not researched |
| 7-day TRL-6 soak | W5 | Skip research | Integration-only; slip-absorption window |

---

## Open questions — explicit pre-phase blockers

Must be resolved in W1 before the corresponding phase can start:

1. **TTN Dublin coverage at the target street.** Verify via TTN Mapper + on-site walk-test. If no gateway in range, plan for TTIG EU868 indoor gateway (€90) at UCD or deployment site, or drop to HTTPS-only. **Blocks W2 LoRa phase.**
2. **Pi FPS on the fine-tuned CAMINAv1 NCNN model** (not generic COCO YOLO11n) with picamera2 + tracker + windowed counter, in target enclosure, for 30 min sustained at ≥ 25 °C ambient. **Blocks W2 edge-demo phase.**
3. **Cars-count encoding: `uint8` vs `uint16` per 15-min window.** On a busy Dublin arterial, cars may exceed 255. If yes, codec grows to 18 bytes. **Decide before codec freezes in W2.**
4. **UCD Google Workspace OAuth app type.** "Internal" app type for `ucd.ie` skips external-app verification. Confirm OAuth client provisioned under UCD Workspace. **Blocks W3 auth phase.**

---

## Explicit "Don't use" — retained from stack research

| Don't use | Phase it would break | Use instead |
|---|---|---|
| **Hailo-8L AI HAT v1** | W1 Pi benchmark | Pure NCNN CPU inference |
| **CayenneLPP encoding** | W2 LoRa codec | Custom 17-byte `struct.pack` layout |
| **ChirpStack v1** | W2 LoRa backend | TTN Community v3 webhook |
| **Edge runtime for DB routes** | W3 cloud live | Fluid Compute (default) |
| **`@neondatabase/serverless` WebSocket** | W3 cloud live | postgres.js + `attachDatabasePool` |
| **Docker on Pi** | W1 deployment | Bare systemd unit + venv |
| **`cv2.VideoCapture` with Pi Cam 3** | W1–W2 Pi benchmark | picamera2 + RGB888 |
| **TimescaleDB** | W3 cloud live | Plain Postgres + BRIN + materialized views |
| **TorchScript at inference** | W1–W2 Pi benchmark | NCNN |
| **Tailwind v4 / zod v4 mid-milestone** | any week | Stay on 3.4 / 3.23 |

---

## Confidence assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | **HIGH** | Vercel Functions, Neon, Drizzle, Next.js 16 docs verified; 2026 Pi benchmarks independent. Only MEDIUM on LoRa because hardware not on-hand. |
| Features | **HIGH** | Six competitor peers + ICO guidance. MEDIUM only on DPIA-interpretation (UCD ethics has final word). |
| Architecture | **HIGH** | Cloud patterns verified against Vercel/Neon/Next.js 16 docs. MEDIUM on LoRa (depends on TTN coverage + worst-case SF). |
| Pitfalls | **HIGH** | Verified against Raspberry Pi, TTN, Neon, Vercel 2026 docs. Four pitfalls sourced from existing `.planning/codebase/CONCERNS.md`. |

**Overall:** **HIGH** — research is decision-ready. Remaining uncertainty is procurement, not architecture.

### Gaps to address during planning

- **LoRa hardware on-hand** — blocks W2. Order RAK3172 + TTIG in W1.
- **TTN Dublin coverage survey** — blocks W2. Walk-test in W1.
- **Pi FPS number** — blocks W2 scope. 30-min in-enclosure benchmark in W1.
- **UCD Google Workspace OAuth app type** — blocks W3 auth. Start OAuth client creation W1.
- **DPIA template review by UCD ethics** — blocks W4 public deployment. Draft W3, submit early W4.
- **Dataset provenance (`custom_model_train/data.md`)** — does NOT block TRL-6; blocks paper. Document in M1 window.

---

*Research completed: 2026-04-23*
*Ready for roadmap: yes*
