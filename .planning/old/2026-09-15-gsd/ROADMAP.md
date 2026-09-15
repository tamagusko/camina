# Roadmap: CAMINA

## Overview

Two milestones inside a single 5-week sprint to TRL-6 demo on a real Dublin street by **2026-05-31**. Milestone 1 (Edge-first + simulated fleet, by 2026-05-15) lands the Pi sensor pipeline, the transport-agnostic `Publisher` interface, a 5-sensor simulated Dublin fleet that lets the dashboard be demoed without any hardware, the LoRaWAN codec + publisher + TTN webhook, and the dashboard-side hot-fixes that unblock M2 (PPR Suspense wrappers and `attachDatabasePool`). Milestone 2 (Cloud + real-street, by 2026-05-31) lands Neon live mode, Google OAuth, the admin console, cron jobs, security hardening, observability, the DPIA and privacy artefacts, a production Vercel deploy with Rolling Releases, and the ≥7-day real-street soak. The roadmap follows the week-by-week plan from `.planning/research/SUMMARY.md`; the week that each phase targets is recorded as `Target week:` below.

## Milestones

- 🚧 **M1: Edge-first + simulated fleet** — Phases 1–4 (target 2026-05-15)
- 📋 **M2: Cloud + real-street TRL-6** — Phases 5–11 (target 2026-05-31)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, …): Planned milestone work
- Decimal phases (e.g. 4.1): Reserved for urgent insertions during execution

- [ ] **Phase 1: Edge baseline on Pi** — `run_sensor.py` wires fine-tuned 9-class YOLO11 (NCNN) + custom tracker + `SensorDaemon`, benchmarked in-enclosure
- [ ] **Phase 2: Publisher interface refactor + dashboard W1 fixes** — extract `Publisher` from `HttpsPublisher`; `attachDatabasePool`; `<Suspense>` + `cacheComponents`
- [ ] **Phase 3: Simulated sensor fleet (Dublin, 5 sensors)** — realistic time-series generator + CLI driver + k-anonymity edge case; demo-ready dashboard without any hardware
- [ ] **Phase 4: LoRaWAN transport (codec + publisher + TTN webhook)** — ≤24-char base64 codec, Python + TS parity, airtime gate, ingest decoder
- [ ] **Phase 5: Data layer live (Neon + Drizzle + PostGIS)** — migrations, `streets-live.ts`, k-anonymity floor, mock/live parity tests
- [ ] **Phase 6: Auth live (UCD Google OAuth + allowlist)** — Auth.js v5 Google, allowed_members DB lookup, fail-closed default, dev fallback removed
- [ ] **Phase 7: Admin console (CRUD + audit + fleet health)** — SensorForm, StreetDrawTool, members UI, audit log writer, config-version ack flow
- [ ] **Phase 8: Scheduled jobs (cron)** — refresh-aggregates, detect-silent, reconcile-daily, retention-enforce; idempotent
- [ ] **Phase 9: Security + observability + Vercel deploy** — BotID, CSP/HSTS, Upstash ratelimit, Sentry PII scrubber, Rolling Releases with health gates, runbook
- [ ] **Phase 10: Privacy artefacts (DPIA + statement + signage)** — runs in parallel with Phases 5–9; gates installation on a public street
- [ ] **Phase 11: TRL-6 demo soak on a real Dublin street** — 7-day continuous publish; cold-spare Pi; outage drill; INTERREG README

## Phase Details

### Phase 1: Edge baseline on Pi
**Target week:** W1 (2026-04-24 → 2026-05-01)
**Goal:** A Raspberry Pi 5 8GB runs the production sensor daemon end-to-end: camera → fine-tuned YOLO (NCNN) → custom tracker → `WindowedCounter` → `DailyAccumulator` → `HttpsPublisher` to the existing mock dashboard, with systemd supervision, USB-SSD durability, and a 30-minute in-enclosure benchmark on the shelf.
**Depends on:** Nothing (first phase) — P1 and P2 can run in parallel.
**Requirements:** EDGE-01, EDGE-02, EDGE-03, EDGE-04, EDGE-05, EDGE-06, EDGE-07, EDGE-08
**Success Criteria** (what must be TRUE):
  1. `python scripts/run_sensor.py --config configs/sensor.yaml` on a Pi 5 8GB detects and counts all 9 classes and POSTs a well-formed `/counts` payload to a Vercel preview mock endpoint every 15 minutes.
  2. 30-minute in-enclosure benchmark documented in `docs/sensor_deployment.md` with FPS, thermal envelope, RSS, and `vcgencmd get_throttled` transcript; FPS ≥ 5 at `imgsz=480`.
  3. systemd unit survives `kill -9` on the daemon via `WatchdogSec=300` + `sd_notify`; RSS flat over a 48-hour bench soak.
  4. Daemon refuses to start until NTP synced (server-side rejection moved to Phase 2).
  5. `state.db` on a USB SSD; boot-time `PRAGMA integrity_check` green.
**Plans:** 4 plans

Plans:
- [ ] 01-01: `run_sensor.py` + NCNN export pipeline + picamera2 camera loop
- [ ] 01-02: 30-minute in-enclosure benchmark + active-cooler documentation
- [ ] 01-03: systemd watchdog + NTP gate + USB-SSD durability wiring
- [ ] 01-04: 48-hour bench soak + heartbeat enrichment (temp, throttle, RSS)

---

### Phase 2: Publisher interface refactor + dashboard W1 fixes
**Target week:** W1 (2026-04-24 → 2026-05-01)
**Goal:** Three low-risk refactors done in parallel with Phase 1. Extract a transport-agnostic `Publisher` interface (unblocks LoRa and the simulator). Install `@vercel/functions` + call `attachDatabasePool(client)` in `dashboard/src/lib/db.ts` (prevents Neon pool exhaustion). Wrap every uncached read on `/[city]` and `/[city]/street/[slug]` in `<Suspense>` and re-enable `cacheComponents: true`. Also lands the server-side 60-second skew rejection on `/api/ingest/sensors/[id]/counts` (split out of Phase 1 SC#4).
**Depends on:** Nothing — runs in parallel with Phase 1.
**Requirements:** EDGE-09, DATA-08, EDGE-07 (server half), (partial) TECH-02 from v2
**Success Criteria** (what must be TRUE):
  1. `HttpsPublisher` implements a `Publisher` Protocol with `publish(endpoint, payload) -> PublishResult`; `SensorDaemon` and `OfflineBuffer` call through the interface only; existing 60-test suite remains green (zero behavioural change).
  2. `dashboard/src/lib/db.ts` wires `attachDatabasePool(client)` immediately after constructing the `postgres()` client; verified on a Vercel preview.
  3. `cacheComponents: true` re-enabled in `dashboard/next.config.mjs`; `/[city]/page.tsx` and `/[city]/street/[slug]/page.tsx` wrap all dynamic reads in `<Suspense>`; preview deploy passes build with the flag on.
  4. No new user-facing behaviour; all dashboard E2E tests (Playwright smoke) still pass.
  5. Server rejects payloads with `abs(produced_at - server_now) > 60s` in `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts`; regression test covers both reject (>60s skew) and accept (≤60s skew) paths. (Migrated from Phase 1 SC#4 — edge half stays in Phase 1.)
**Plans:** TBD (3 plans expected)

Plans:
- [ ] 02-01: Extract `Publisher` Protocol from `HttpsPublisher`; migrate `SensorDaemon` + `OfflineBuffer`
- [ ] 02-02: `@vercel/functions` + `attachDatabasePool` in `dashboard/src/lib/db.ts`
- [ ] 02-03: `<Suspense>` wrappers + re-enable `cacheComponents` in Next.js config

---

### Phase 3: Simulated sensor fleet (Dublin, 5 sensors)
**Target week:** W1–W2 (2026-04-24 → 2026-05-08)
**Goal:** A realistic simulated fleet of 5 CAMINA sensors placed on real Dublin streets populates the dashboard with believable 15-minute windowed counts and per-class speeds, so the UI can be iterated and demoed end-to-end without any Pi, camera, or network. Works against the existing mock repo (zero infrastructure) and, once Neon lands (Phase 5), against the live DB too.
**Depends on:** Phase 2 (wants the Suspense / cacheComponents wrappers so streaming data renders correctly). Does NOT depend on Phase 4 (LoRa) or Phase 5 (Data layer live).
**Requirements:** SIM-01, SIM-02, SIM-03, SIM-04, SIM-05, SIM-06, SIM-07
**Success Criteria** (what must be TRUE):
  1. `pnpm exec node dashboard/scripts/simulate-fleet.mjs --backfill 168 --seed 42` fills the mock repo (or Neon if `CAMINA_DATA_SOURCE=live`) with seven days of realistic history for all 5 Dublin sensors; the same seed reproduces identical output.
  2. `--live` mode appends one new 15-minute window per sensor on a real-wall-clock cadence; `--tick 5` speeds this up to 5 s/window for demos.
  3. Rush-hour peaks (07:00–10:00, 16:00–19:00), weekday-vs-weekend profiles, and class-specific hourly patterns are visibly distinct on the dashboard time-series chart; numbers pass a visual plausibility check.
  4. Per-class speeds fall within realistic bands (pedestrians 3–6, cyclists 12–25, cars 20–50, buses 15–35, trucks 15–40 km/h) and drive the colour ramp end-to-end.
  5. One simulated sensor deliberately crosses `k_min = 5` during quiet hours (e.g. a low-traffic residential street), so the dashboard visibly collapses that street's counts to `null` / "< 5" (proves the privacy floor works against live-looking data).
  6. `docs/SIMULATION.md` documents the CLI, the seed semantics, and the expected dashboard screenshots.
**Plans:** TBD (3 plans expected)

Plans:
- [ ] 03-01: Fleet fixture (5 sensors on real Dublin streets) + `data/mock/dublin/simulated-fleet.json`
- [ ] 03-02: Deterministic time-series + speed-distribution generator; unit tests for pattern shapes
- [ ] 03-03: `simulate-fleet.mjs` CLI (backfill / live / tick / seed) + mock + live-DB adapters + `docs/SIMULATION.md`

---

### Phase 4: LoRaWAN transport — codec + publisher + TTN webhook
**Target week:** W2 (2026-05-02 → 2026-05-08)
**Goal:** A sensor configured `transport=lora` in `sensor.yaml` encodes windowed counts as a 17-byte binary payload (≤ 24 base64 chars on the wire), transmits via a RAK3172 over LoRaWAN EU868 to TTN Community, which webhooks into the dashboard's `/api/ingest/lora/uplink` endpoint where the payload is decoded and persisted to the same canonical tables as the HTTPS path. Counts-only, uplink-only, 15-minute cadence.
**Depends on:** Phase 2 (requires the `Publisher` interface). Runs in parallel with Phase 3.
**Pre-phase blockers (must resolve in W1):**
  - TTN Dublin coverage confirmed at the target deployment street (walk-test) OR TTIG EU868 indoor gateway procured for UCD.
  - Cars-count encoding decision: `uint8` vs `uint16` per 15-minute window.
  - RAK3172 breakout module on hand.
**Requirements:** LORA-01, LORA-02, LORA-03, LORA-04, LORA-05, LORA-06, LORA-07, LORA-08
**Success Criteria** (what must be TRUE):
  1. `hypothesis` property tests in Python and `fast-check` property tests in TypeScript round-trip the same shared-vector fixtures without divergence; mismatch fails CI.
  2. `LoRaPublisher` emits a valid 17-byte payload for every canonical `counts` event; `OfflineBuffer` remains transport-agnostic.
  3. Airtime budget for SF7–SF12 is computed and documented next to the codec; the publisher hard-gates transmission if the projected daily airtime would exceed 30 s/device, with a one-line fallback to HTTPS.
  4. A real RAK3172 dev device (not the deployment Pi) publishes an uplink that reaches `/api/ingest/lora/uplink` via a live TTN Community application; the endpoint decodes and persists to `sensor_readings`; HMAC webhook signature verified.
  5. Idempotency: replaying the same uplink does not duplicate a row (`sensor_id`, `window_start` primary key).
**Plans:** TBD (4 plans expected)

Plans:
- [ ] 04-01: `lora_codec.py` + `lora-codec.ts` with shared fixtures; property-based tests both sides
- [ ] 04-02: `LoRaPublisher` + airtime budget gate + config-flag wiring in `SensorDaemon`
- [ ] 04-03: TTN Community application + HMAC webhook + `/api/ingest/lora/uplink` decoder
- [ ] 04-04: End-to-end test with a real RAK3172 dev device through TTN to a Vercel preview

---

### Phase 5: Data layer live (Neon + Drizzle + PostGIS)
**Target week:** W3 (2026-05-09 → 2026-05-15)
**Goal:** The `CAMINA_DATA_SOURCE=live` code path works end-to-end. Neon Postgres + PostGIS provisioned via Vercel Marketplace; Drizzle migration `0000_init.sql` applied; `streets-live.ts` implements every `StreetsRepository` method; k-anonymity floor (`k_min = 5`) enforced in both mock and live adapters; right-to-erasure via `ON DELETE CASCADE` from `sensors`.
**Depends on:** Phase 2 (`attachDatabasePool` is a prerequisite for stable pooled connections under Rolling Releases).
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-09
**Success Criteria** (what must be TRUE):
  1. `pnpm drizzle-kit migrate` against Neon creates all tables + MV; `0000_init.sql` applied cleanly from scratch.
  2. Mock/live parity tests: every `StreetsRepository` method returns structurally identical shapes for the same input across mock and Dockerized PG+PostGIS.
  3. Public response to `/api/streets/*` collapses any per-street-per-window count below `k_min = 5` to `null` or `"< 5"`; regression test covers this (reuses the Phase-3 simulator edge case as a live-mode fixture).
  4. `DELETE FROM sensors WHERE id = ?` cascades to `sensor_readings`, `heartbeats`, `street_coverage`, `daily_totals`, `config_history` in a single statement; aggregates in `street_readings_15m` remain (no `sensor_id` by construction).
  5. CI grep confirms `DATABASE_URL_UNPOOLED` appears only in migration/CLI code, never in `dashboard/src/app/api/**`.
**Plans:** TBD (3 plans expected)

Plans:
- [ ] 05-01: Neon provisioning + Drizzle migration + schema verification
- [ ] 05-02: `streets-live.ts` implementation + mock/live parity tests
- [ ] 05-03: k-anonymity floor + CASCADE wiring + pooled-URL CI enforcement

---

### Phase 6: Auth live (UCD Google OAuth + allowlist)
**Target week:** W3 (2026-05-09 → 2026-05-15)
**Goal:** Admin access is gated by Google OAuth against UCD Google Workspace, checked against the `allowed_members` DB table. Dev-only env-var allowlist is removed. Fail-closed default protects against misconfiguration.
**Depends on:** Phase 5 (needs the live DB for `allowed_members`)
**Pre-phase blockers (must resolve in W1):**
  - UCD Google Workspace OAuth client provisioned as an "internal" app type (skips external-app verification).
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06
**Success Criteria** (what must be TRUE):
  1. Signing in with a `@ucd.ie` address on the allowlist succeeds and lands the user in `/admin`; signing in with an address not on the allowlist returns 401.
  2. `CAMINA_DEV_ALLOWED_EMAILS` is removed from `dashboard/src/lib/auth.ts`; a module-init assertion refuses to boot when `NODE_ENV=production` or `VERCEL_ENV` is set without a live `allowed_members` table.
  3. Every `requireAdmin()`-gated route returns 401 without a session; privacy regression test extended to cover this.
  4. `/admin/members` lists current allowlist entries with role.
**Plans:** TBD (2 plans expected)

Plans:
- [ ] 06-01: Auth.js v5 Google provider wired against UCD Workspace; live DB lookup for allowlist
- [ ] 06-02: Remove dev fallback + fail-closed assertion + privacy regression extension

---

### Phase 7: Admin console (CRUD + audit + fleet health)
**Target week:** W3 (2026-05-09 → 2026-05-15)
**Goal:** Admins can create and edit sensors (with GPS), draw street coverage visually, invite/revoke members, update a sensor's config, and see every admin mutation in a searchable audit log and each sensor's latest heartbeat.
**Depends on:** Phase 6 (auth must be live before admin mutations ship)
**Requirements:** ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06, ADMIN-07, ADMIN-08
**Success Criteria** (what must be TRUE):
  1. Admin creates a sensor via `<SensorForm>`, draws its street coverage via `<StreetDrawTool>`, and a cascade deletes both when the sensor is removed.
  2. `PATCH /api/admin/sensors/[id]` updates config, bumps `config_version`, writes an `audit_log` row; UI shows "awaiting device ack" → "✓ applied" on the next heartbeat.
  3. `/admin/events` lists silent-sensor and reconciliation events with acknowledge / dismiss buttons.
  4. `/admin/audit` is searchable by actor, route, and time range.
  5. Build-time guard in `vercel.ts` fails the build when `VERCEL_ENV ∈ {preview, production}` and `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` — verified via a deliberate misconfiguration of a PR preview.
**Plans:** TBD (3 plans expected)

Plans:
- [ ] 07-01: `<SensorForm>` + `<StreetDrawTool>` + admin CRUD API handlers
- [ ] 07-02: Audit-log writer wrapper + `/admin/audit` list view + `/admin/members` UI
- [ ] 07-03: Config-version ack flow + fleet-health panel + build-time `NEXT_PUBLIC_CAMINA_DEV_ADMIN` guard

---

### Phase 8: Scheduled jobs (cron)
**Target week:** W3 (2026-05-09 → 2026-05-15)
**Goal:** Four idempotent cron handlers wired through `vercel.ts`: refresh the 15-minute materialized view, detect silent sensors, reconcile daily totals, and enforce the 13-month raw-data retention policy.
**Depends on:** Phase 5 (all crons touch the live DB)
**Requirements:** CRON-01, CRON-02, CRON-03, CRON-04, CRON-05
**Success Criteria** (what must be TRUE):
  1. `refresh-aggregates` runs every 15 min, holds a Postgres advisory lock for the duration, calls `REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m`, and completes within budget with no overlap artefacts.
  2. `detect-silent` inserts an `events` row for any sensor whose last heartbeat is older than 15 min (HTTPS) or whose last LoRa uplink is older than 30 min; UI surfaces these on `/admin/events`.
  3. `reconcile-daily` runs at 01:00 UTC, compares per-sensor daily totals against aggregated windowed counts, emits mismatch events per `docs/RECONCILIATION.md`.
  4. `retention-enforce` deletes raw rows older than 13 months; aggregates in `street_readings_15m` remain.
  5. Every cron handler is idempotent: overlapping invocations caused by a Rolling Release do not double-process; verified by a synthetic replay test.
  6. Cron-auth fails-closed when `VERCEL_CRON_SECRET` is unset (refuses to run).
**Plans:** TBD (2 plans expected)

Plans:
- [ ] 08-01: `refresh-aggregates` + `detect-silent` with advisory-lock idempotency
- [ ] 08-02: `reconcile-daily` + `retention-enforce` + replay-safety tests + fail-closed cron auth

---

### Phase 9: Security + observability + Vercel production deploy
**Target week:** W4 (2026-05-16 → 2026-05-22)
**Goal:** Public production deploy with Rolling Releases + health gates + auto-rollback. Bot protection, transport security headers, per-device and per-IP rate limits, Sentry with a PII scrubber that strips any key matching `sensor_id` / `latitude` / `longitude` / `/_gps$/i`, Speed Insights + Analytics, a `/api/health` endpoint wired into an uptime monitor, and a `RUNBOOK.md` covering rollback / swap / rotate / migrate.
**Depends on:** Phases 5, 6, 7, 8 (everything prod-worthy lands here)
**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):
  1. First production deploy goes to 10 % → 50 % → 100 % under Vercel Rolling Releases; a synthetic 5xx spike triggers auto-rollback in a preview rehearsal.
  2. A deliberate Sentry test event containing `latitude: 53.3...` in the body shows `[Filtered]` in the Sentry dashboard (PII scrubber verified).
  3. Bots cannot reach `/sign-in` or any admin mutation: Vercel BotID challenge fires on headless scripted access.
  4. Upstash rate limits fire on 11 consecutive POSTs from the same sensor within 15 min; `/api/admin/*` limits fire on 31 req/min from one IP; `/sign-in` limits fire on 6 req/min from one IP.
  5. All 501 stubs removed from `/api/ingest/*`; edge-agent boot-time guard refuses to run in live mode if any ingest route returns 501 against the preview URL.
  6. Uptime monitor pings `/api/health` every 5 min; simulated outage pages on 3 consecutive failures.
  7. `dashboard/docs/RUNBOOK.md` documents rollback, sensor swap, AUTH_SECRET rotation, Neon migration rollback, cron debugging, DPIA updates.
**Plans:** TBD (3 plans expected)

Plans:
- [ ] 09-01: BotID + CSP/HSTS + Upstash rate limits + 501 audit + Bearer rotation docs
- [ ] 09-02: Sentry with PII scrubber + Speed Insights + Analytics + uniform log wrapper + `/api/health` + fleet-health endpoint
- [ ] 09-03: Rolling Releases config + auto-rollback rehearsal + uptime monitor + RUNBOOK.md

---

### Phase 10: Privacy artefacts (DPIA + public statement + physical signage)
**Target week:** W3–W4 (parallel to Phases 5–9)
**Goal:** The three regulatory artefacts that the FEATURES research surfaced as missing from PROJECT.md. Without them, UCD ethics cannot sign off on a public-street installation.
**Depends on:** Nothing (docs-only; runs in parallel)
**Pre-phase blockers:**
  - UCD ethics contact confirmed; DPO/contact name for signage and the dashboard footer confirmed.
**Requirements:** PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05
**Success Criteria** (what must be TRUE):
  1. `docs/PRIVACY/DPIA.md` covers data collected, retention (13 months raw, aggregates anonymised), recipients, lawful basis, k-anonymity floor, physical access controls, right-to-erasure cascade, DPO contact. Reviewed and signed off by UCD ethics.
  2. `/about` on the dashboard links to the DPIA and publishes a plain-language summary of what's collected and what isn't (no faces, no plates, no video stored).
  3. A printed sign is ready to install alongside the Pi: "CAMINA research sensor — aggregate counts only, no video recorded, contact [DPO] — ref [sensor-id]."
  4. Privacy regression test extended to the live adapter: raw `sensor_id`, exact GPS, and raw camera frames never appear in any `/api/streets/*` or `/api/public/*` response.
  5. `/api/public/aggregates.csv` serves k-anonymity-respecting open data (optional but recommended).
**Plans:** TBD (2 plans expected)

Plans:
- [ ] 10-01: DPIA draft + `/about` page + UCD ethics submission + signage design
- [ ] 10-02: Privacy regression test on the live adapter + CSV public export

---

### Phase 11: TRL-6 demo soak on a real Dublin street
**Target week:** W5 (2026-05-23 → 2026-05-31)
**Goal:** One Pi on one real Dublin street, publishing to production Vercel → live Neon → public map for ≥7 days. Cold-spare Pi ready to swap. Simulated outage recovers without data loss or duplicates. INTERREG deliverable README ready.
**Depends on:** Phases 1–10.
**Requirements:** DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05, DEMO-06
**Success Criteria** (what must be TRUE):
  1. The Pi is physically installed at a real Dublin street with signage; transport is `https`, `lora`, or `both` depending on the W1 TTN coverage outcome.
  2. The production dashboard shows continuous 15-minute windowed counts for that street for ≥7 consecutive days (OfflineBuffer gap-fills count as continuous).
  3. A cold-spare Pi is bench-tested and swap-ready at the lab.
  4. A deliberate 30-minute WiFi outage on the deployment Pi recovers via OfflineBuffer drain without data loss or duplicate rows.
  5. Daily reconciliation mismatches are investigated and documented.
  6. INTERREG deliverable README is ready: link to live dashboard, screenshot, 30-second demo video.
**Plans:** TBD (2 plans expected)

Plans:
- [ ] 11-01: Real-street deployment (install, signage, baseline heartbeat) + cold-spare provisioning
- [ ] 11-02: 7-day soak supervision + outage drill + reconciliation audit + INTERREG README

## Progress

**Execution Order:**
Phases execute in numeric order with parallelism opportunities noted in Depends-on:
1 ∥ 2  →  3 ∥ 4  →  5  →  6  →  7  →  8  →  9  →  11
(10 runs in parallel with 5–9; 3 and 4 both depend only on 2 and can run in parallel.)

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 1. Edge baseline on Pi | 0/4 | Not started | — |
| 2. Publisher refactor + dashboard W1 fixes | 0/3 | Not started | — |
| 3. Simulated sensor fleet | 0/3 | Not started | — |
| 4. LoRaWAN transport | 0/4 | Not started | — |
| 5. Data layer live | 0/3 | Not started | — |
| 6. Auth live | 0/2 | Not started | — |
| 7. Admin console | 0/3 | Not started | — |
| 8. Scheduled jobs (cron) | 0/2 | Not started | — |
| 9. Security + observability + deploy | 0/3 | Not started | — |
| 10. Privacy artefacts | 0/2 | Not started | — |
| 11. TRL-6 demo soak | 0/2 | Not started | — |

**Totals:** 11 phases, ~31 plans, 70 v1 requirements mapped.

---
*Roadmap created: 2026-04-23*
*Last updated: 2026-04-28 — Phase 1 SC#4 split: edge half (NTP gate) stays in Phase 1; server half (60s skew rejection) moved to Phase 2 SC#5 per PLAN-CHECK Blocker 1.*
