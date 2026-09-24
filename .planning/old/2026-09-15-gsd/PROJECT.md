# CAMINA

## What This Is

CAMINA is a privacy-first traffic-sensor network: a fine-tuned 9-class YOLO11 detector running on Raspberry Pi 5 8GB at street level, tracking road users with a custom Kalman + Hungarian-assignment tracker, accumulating windowed counts on-device, and publishing aggregates to a Next.js dashboard where streets are colour-coded by count or speed. Built for INTERREG-funded academic research at UCD Dublin as a TRL-6 demonstration of edge ML for urban mobility, with strict GDPR-aligned privacy guarantees (no exact sensor GPS ever exposed publicly).

## Core Value

**One Raspberry Pi on one real Dublin street, detecting and counting nine road-user classes and feeding a live public dashboard — demonstrably privacy-preserving, demonstrably lightweight, demonstrably reproducible.** Everything else is negotiable; this TRL-6 proof is not.

## Requirements

### Validated

<!-- Inferred from the codebase map (brownfield). These shipped in commits up to 9efbb7a. -->

- ✓ 9-class fine-tuned YOLO11 model (person, cyclist, e-scooter, car, SUV, motorcycle, bus, delivery van, truck) — trained, weights in `yolo11n.pt` / `yolo11n.torchscript`
- ✓ Custom Kalman + Hungarian-assignment tracker (`src/camina/core/tracker.py`) — own implementation, uses `filterpy` Kalman filter + `scipy` linear-sum assignment
- ✓ Plan 01 edge-agent abstractions (`src/camina/core/`, `src/camina/io/`, `src/camina/service/sensor_daemon.py`) — WindowedCounter, DailyAccumulator, OfflineBuffer (WAL SQLite FIFO), HttpClient, HttpsPublisher, ConfigPoller, SensorDaemon — **60 unit + integration tests passing**
- ✓ HTTPS ingest protocol (`docs/PROTOCOL.md`) + reconciliation spec (`docs/RECONCILIATION.md`) + deployment guide (`docs/sensor_deployment.md`)
- ✓ `configs/sensor.yaml` start-up template; `deploy/systemd/camina-sensor.service`
- ✓ Plan 02 dashboard scaffold (mock mode): Next.js 16 App Router + Tailwind + Drizzle + hand-rolled UI (`dashboard/`)
- ✓ Dublin public map with MapLibre + local Carto Positron tiles (60 MB, zooms 12–18, gitignored)
- ✓ Uber-inspired monochrome visual language (`DESIGN.md`)
- ✓ Street-click side panel (totals, avg speed, per-class breakdown) + dev-only admin strip (`NEXT_PUBLIC_CAMINA_DEV_ADMIN`)
- ✓ Ingest API stubs with Bearer auth + zod validation + mock responses (`/api/ingest/sensors/[id]/{counts,daily,heartbeat,config}`)
- ✓ Cron + admin route skeletons gated by `VERCEL_CRON_SECRET` / `requireAdmin()`
- ✓ Privacy regression test + schema tests (Vitest) + Playwright smoke

### Active

<!-- Hypotheses until shipped. Grouped by milestone. -->

**Milestone 1 — Edge-first (target: by 2026-05-15)**

- [ ] `scripts/run_sensor.py` — production entry point composing fine-tuned 9-class YOLO + the custom tracker + `SensorDaemon` on Pi 5 8GB over WiFi/HTTPS
- [ ] End-to-end Pi integration: camera → inference → tracker → windowed count → HTTPS POST to mock dashboard (local or Vercel preview)
- [ ] Inference benchmark on Pi 5 8GB (FPS, CPU/thermal, memory; document in `docs/sensor_deployment.md`)
- [ ] Systemd clean boot + service recovery tested on Pi hardware
- [ ] LoRa compact-codec design: ≤200-char payload carrying camera ID (`LNN`, e.g. `D01`), timestamp (`YYMMDDHHMM`), and nine class counts — encode with minimal wasted characters
- [ ] `LoRaPublisher` in `src/camina/io/` parallel to `HttpsPublisher`, plugged into `SensorDaemon` via a transport flag
- [ ] LoRaWAN → TTN webhook → `/api/ingest/lora/*` decoder endpoint on the dashboard
- [ ] Transport selection via `configs/sensor.yaml` (`https` | `lora` | `both`)
- [ ] **Simulated 5-sensor Dublin fleet** — deterministic time-series generator + CLI driver + k-anonymity edge case so the dashboard can be iterated/demoed end-to-end without any Pi, camera, or network

**Milestone 2 — Cloud + real-street deployment (target: by 2026-05-31)**

- [ ] Neon Postgres + PostGIS provisioned via Vercel Marketplace
- [ ] Drizzle migration `0000_init.sql` applied; `dashboard/src/lib/repo/streets-live.ts` implemented (currently throws)
- [ ] Google OAuth wired (`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`); `allowed_members` table populated; dev-allowlist env fallback removed from `dashboard/src/lib/auth.ts`
- [ ] Admin CRUD: `<SensorForm>` (create/edit, GPS), `<StreetDrawTool>` (click OSM way → save coverage), `/admin/members`, `PATCH /api/admin/sensors/[id]` with audit row
- [ ] Cron implementations: 15-min materialized-view refresh, silent-sensor detection, daily reconciliation per `docs/RECONCILIATION.md`
- [ ] Security hardening: BotID on `/sign-in` + admin mutations, CSP + HSTS via `vercel.ts`, Upstash rate limits on `/api/admin/*` and `/api/ingest/*`, Sentry (client + server) with PII scrubber, Speed Insights
- [ ] Vercel production deployment with Rolling Releases (10 % → 50 % → 100 % with health gates) + auto-rollback + uptime monitor on `/api/health`
- [ ] `dashboard/docs/RUNBOOK.md`
- [ ] **One Pi on one real Dublin street publishing live for ≥1 week — TRL-6 demo**

### Out of Scope

- **Multi-city support** — Dublin only for v1; data model already keyed by city so v2 extension is cheap.
- **Anonymous admin access** — allow-listed Google OAuth required; documented privacy model.
- **Public access gating** — the public street map remains viewable anonymously (no sign-in to see counts/speed). Only sensor-level data is admin-gated.
- **Exact sensor GPS in public UI** — hard privacy boundary; enforced by test.
- **ML predictions / forecasting** — separate project.
- **Re-identification / cross-camera tracking** — explicit privacy non-goal.
- **Over-the-air model updates** — deferred to TRL-7+.
- **Mobile native app** — responsive web only.
- **Internationalisation beyond English** — Portuguese deferred to v1.1.
- **Paper / benchmark artefacts** — captured in a follow-on milestone; must not block TRL-6 demo.
- **Industrial SLAs / commercial deployment** — research-grade reliability is the v1 bar.
- **Short-lived JWT auth for devices** — opaque Bearer token is sufficient for TRL-5/6; JWT is a TRL-7 concern.

## Context

- **Funding / audience**: INTERREG-funded academic research at UCD Dublin; primary audience is researchers and municipal collaborators, not the general public or industry.
- **Solo developer**: one researcher (Tiago Tamagusko) driving implementation. Planning pace and review depth must accommodate solo cognitive load.
- **Hardware on hand**: Raspberry Pi 5 8GB + camera available today. **LoRa module and region/frequency not yet confirmed** — procurement during M1.
- **LoRaWAN network**: Assumes The Things Network coverage in Dublin or a self-hosted gateway near the deployment site. Needs verification before the LoRa phase starts.
- **Existing infrastructure**: 60-test edge-agent suite (pytest); Vitest + Playwright on the dashboard; extensive design documentation in `DESIGN.md`, `plan/01-*`, `plan/02-*`; committed model weights (5.6 MB + 11 MB) — known bloat, revisit during tech-debt phase.
- **Known-fragile areas** (per `.planning/codebase/CONCERNS.md`): MapLibre canvas sizing race (React Strict Mode disabled as safety net; re-enable when guarded), `NEXT_PUBLIC_CAMINA_DEV_ADMIN` prod-leak risk (HIGH), triplicated YOLO weights, `env.local` secret-rotation discipline.
- **Prior decisions locked in the code**: HTTPS-only device transport (MQTT was considered and rejected), Fluid Compute runtime on Vercel, Neon via Marketplace (not self-hosted Postgres), Protomaps PMTiles planned for production basemap (local Carto tiles for dev).

## Constraints

- **Timeline**: TRL-6 demo by **2026-05-31** (≈5 weeks from 2026-04-23). Aggressive for solo work; paper/benchmarks explicitly deferred.
- **Tech stack (edge)**: Python 3.x + PyTorch / Ultralytics YOLO + custom Kalman-based tracker (`filterpy`, `scipy`); runs on Pi 5 8GB ARM64. `uv` preferred for Python deps.
- **Tech stack (cloud)**: Next.js 16 App Router + Tailwind + Drizzle + Neon Postgres + Vercel Fluid Compute. `pnpm` in `dashboard/`.
- **Performance — edge**: inference + tracking + windowed-count loop must sustain the target camera FPS on Pi 5 8GB within thermal limits (benchmark in M1).
- **Performance — LoRa codec**: payload ≤ 200 characters, including camera ID (`LNN`), compact timestamp (`YYMMDDHHMM`), and nine class counts. Every character has to earn its place.
- **Privacy / GDPR**: public UI never exposes exact sensor GPS. Public surface speaks only in terms of streets. Enforced by regression test.
- **Security**: Bearer token per device (opaque, rotated manually via SSH). Google OAuth + explicit allow-list for admin. BotID on auth + admin mutations. Dev-admin flag must not ship to production.
- **Compatibility**: LoRaWAN class A uplinks only (no downlink control plane in v1).
- **Budget**: Vercel Hobby / research tier + Neon free tier + TTN community network. No paid tiers required for v1.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| HTTPS-only device transport (Plan 01) | ≤500 devices at 15-min cadence doesn't justify a broker; Vercel is serverless. | ✓ Good — 60 tests pass |
| Two transports: WiFi/HTTPS primary, LoRaWAN secondary | Most deployments have WiFi; LoRa covers network-poor sites. User chose P1 ordering. | — Pending (LoRa in M1) |
| LoRaWAN → TTN webhook → `/api/ingest/lora/*` | Lowest infra overhead; avoids running a self-hosted gateway for v1. | — Pending (needs TTN coverage confirmation) |
| Two milestones: Edge-first, then Cloud | Lets edge-side progress early while Plan 02 live half matures. | — Pending |
| Dublin-only in v1 | Focus over breadth; data model already city-keyed. | — Pending |
| Public map anonymous; admin allow-listed | Matches DESIGN.md / Plan 02 scaffold and INTERREG outreach goals. | — Pending |
| Privacy-by-design is load-bearing | GDPR + research ethics + public trust. Non-negotiable. | ✓ Good — enforced by tests |
| TRL-6 deadline: 2026-05-31 | Aggressive but anchored on INTERREG/academic rhythm. | ⚠️ Revisit if M1 slips by >1 week |
| Fine-tuned 9-class YOLO11 (not generic COCO) | Domain match matters (e-scooter, delivery van, SUV absent from COCO). | ✓ Good — model already trained |
| Pi 5 8GB as deployment target | On hand; 8GB headroom for future ML tasks (pose, re-id) without re-platforming. | — Pending (benchmark in M1) |
| Fluid Compute + Neon + Marketplace integrations | Vercel-native path; no VPS, no broker, no separate ingestor. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-23 after initialization*
