Version: 2.1 — 2026-09-15 — decisions D1–D13 recorded; 2.0 superseded old/2026-09-15-gsd/PROJECT.md

# CAMINA

## What This Is

CAMINA is a privacy-first traffic-sensor network: a fine-tuned 9-class YOLO11n detector (the TRA 2026 model, currently on `origin/TRA2026`, brought to `main` in PLAN.md S1) designed to run on Raspberry Pi 5 8GB at street level, tracking road users with a custom Kalman + Hungarian-assignment tracker, accumulating windowed counts on-device, and publishing aggregates to a Next.js dashboard where streets are colour-coded by count or speed. Built for academic research at UCD Dublin, funded by REALLOCATE (EU grant 101103924), as a TRL-6 demonstration of edge ML for urban mobility, with strict GDPR-aligned privacy guarantees (no exact sensor GPS ever exposed publicly).

## Core Value

**One Raspberry Pi on one real Dublin street, detecting and counting nine road-user classes and feeding a live public dashboard — demonstrably privacy-preserving, demonstrably lightweight, demonstrably reproducible.** Everything else is negotiable; this TRL-6 proof is not.

## Requirements

The requirement lists that used to live here (Validated / Active / by milestone) are superseded by the staged plan:

- `.planning/PLAN.md` — the current staged plan (M1/M2, stages S1–S14, done-tests, REQ-ID crosswalk in Appendix A)
- `.planning/STATE.md` — what is verified working right now, in order, with evidence
- Old requirement lists (never trued up against the code) are archived at `old/2026-09-15-gsd/REQUIREMENTS.md`

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
- **Paper / benchmark artefacts** — captured in a follow-on milestone; must not block TRL-6 demo. *(Note 2026-09-15: Pi benchmarks and ground-truth counts are now M1 evidence, PLAN.md S6/S9; paper artefacts remain out of scope.)*
- **Industrial SLAs / commercial deployment** — research-grade reliability is the v1 bar.
- **Short-lived JWT auth for devices** — opaque Bearer token is sufficient for TRL-5/6; JWT is a TRL-7 concern.

## Context

- **Funding:** REALLOCATE (EU grant 101103924), as credited in the TRA 2026 paper and slides; confirmed by the PI on 2026-09-15 (D11). Earlier project docs said INTERREG and were corrected. Audience: researchers and municipal collaborators, not the general public or industry.
- **Solo developer**: one researcher (Tiago Tamagusko) driving implementation. Planning pace and review depth must accommodate solo cognitive load.
- **Hardware on hand** (as recorded 2026-04-23; re-confirm for S6): Raspberry Pi 5 8GB + camera. No Pi run has been recorded yet (AUDIT.md §1, "Field / soak evidence — MISSING"). LoRa module and region/frequency not yet confirmed — see D1.
- **LoRaWAN network**: Assumes The Things Network coverage in Dublin or a self-hosted gateway near the deployment site; needs verification if D1 keeps LoRa.
- **Existing infrastructure**: edge-agent suite now 144 pytest / dashboard 89 vitest (AUDIT.md §0 correction 6, AUDIT.md §8 runs #4/#8), up from the 60-test figure this file previously recorded; Vitest + Playwright on the dashboard; committed model weights are 6-class only on `main` — the paper's 9-class model lives on `origin/TRA2026` (AUDIT.md G-i).
- **Known-fragile areas**: MapLibre canvas sizing race (React Strict Mode disabled as safety net; re-enable when guarded; still open per `codebase/CONVENTIONS.md`), live read path is a stub (`streets-live.ts`, AUDIT.md G-a), no sensor/token provisioning exists (AUDIT.md G-c), remote config loop is dead (AUDIT.md G-b).
- **Prior decisions locked in the code**: HTTPS-only device transport (MQTT was considered and rejected), Fluid Compute runtime on Vercel, Neon via Marketplace (not self-hosted Postgres), Protomaps PMTiles planned for production basemap (local Carto tiles for dev).
- **Definition of "fully functional"**: the TRA 2026 paper and slides (`bkp/TRA_2026_paper_896_adjusted_final.pdf`, `bkp/TRA_2026_896.pdf` — gitignored, local-only, not in git history) are the external bar this plan is measured against; see `PLAN.md` header and `audit-2026-09-15/AUDIT.md` Appendix (claims table) for what they promise versus what the code does.

## Constraints

- **Timeline**: TRL-6 demo by **2026-05-31** (≈5 weeks from 2026-04-23). Aggressive for solo work; paper/benchmarks explicitly deferred. (Missed — see Key Decisions below and `PLAN.md` D12.)
- **Tech stack (edge)**: Python 3.x + PyTorch / Ultralytics YOLO + custom Kalman-based tracker (`filterpy`, `scipy`); runs on Pi 5 8GB ARM64. `uv` preferred for Python deps.
- **Tech stack (cloud)**: Next.js 16 App Router + Tailwind + Drizzle + Neon Postgres + Vercel Fluid Compute. `pnpm` in `dashboard/`.
- **Performance — edge**: inference + tracking + windowed-count loop must sustain the target camera FPS on Pi 5 8GB within thermal limits (benchmark in M1).
- **Performance — LoRa codec**: payload ≤ 200 characters, including camera ID (`LNN`), compact timestamp (`YYMMDDHHMM`), and nine class counts. Every character has to earn its place. *(Superseded in code 2026-07-10 by the 20-byte binary schema-v2, `docs/lora.md`; relevant only if D1 keeps LoRa.)*
- **Privacy / GDPR**: public UI never exposes exact sensor GPS. Public surface speaks only in terms of streets. Enforced by regression test.
- **Security**: Bearer token per device (opaque, rotated manually via SSH). Google OAuth + explicit allow-list for admin. BotID on auth + admin mutations (never implemented; closed 2026-09-15, PLAN.md §4). Google OAuth is required before the first live deploy (D6). Dev-admin flag must not ship to production.
- **Compatibility**: LoRaWAN class A uplinks only (no downlink control plane in v1).
- **Budget**: Vercel Hobby / research tier + Neon free tier + TTN community network. No paid tiers required for v1.

## Key Decisions

Dated status added 2026-09-15 from the code audit (`audit-2026-09-15/AUDIT.md`) and its independent gate (same file, §0 and §7). "D#" cross-references `PLAN.md` §3; decisions D1–D13 were taken by the PI on 2026-09-15.

| Decision | Rationale | Outcome (2026-04-23) | Status (2026-09-15) |
|---|---|---|---|
| HTTPS-only device transport (Plan 01) | ≤500 devices at 15-min cadence doesn't justify a broker; Vercel is serverless. | ✓ Good — 60 tests pass | decided; implemented — HTTPS publisher WORKS end to end in mock mode (AUDIT.md §1 "Publisher + OfflineBuffer + HttpClient"); edge suite now 144 pytest, not 60 |
| Two transports: WiFi/HTTPS primary, LoRaWAN secondary | Most deployments have WiFi; LoRa covers network-poor sites. User chose P1 ordering. | — Pending (LoRa in M1) | decided 2026-09-15 (D1): LoRa is M2-optional, not M1 — the paper never promises it (AUDIT.md G-g) |
| LoRaWAN → TTN webhook → `/api/ingest/lora/*` | Lowest infra overhead; avoids running a self-hosted gateway for v1. | — Pending (needs TTN coverage confirmation) | implemented as code (20-byte v2 codec + webhook, AUDIT.md §1 "LoRa codec / TS decoder / TTN webhook — PARTIAL"); not wired into the daemon, no radio, sensor-id format conflict (`cam-dub-NN` vs the frame's 3-byte id) — M2-optional per D1 |
| Two milestones: Edge-first, then Cloud | Lets edge-side progress early while Plan 02 live half matures. | — Pending | superseded — `PLAN.md` redefines M1/M2 around "one fully-functional unit" vs "deployment-ready fleet", not an edge/cloud split |
| Dublin-only in v1 | Focus over breadth; data model already city-keyed. | — Pending | decided; unchanged (D8 keeps Dublin-only) |
| Public map anonymous; admin allow-listed | Matches DESIGN.md / Plan 02 scaffold and project outreach goals. | — Pending | decided; implemented in mock mode (fail-closed auth guards, 13 tests — AUDIT.md §1 "Auth (Auth.js Google) — PARTIAL/UNVERIFIED"); live OAuth app not yet created — required before the first deploy (D6, S5); full admin console in S11 (D5) |
| Privacy-by-design is load-bearing | GDPR + research ethics + public trust. Non-negotiable. | ✓ Good — enforced by tests | decided; implemented 2026-07-10 for the mock adapter — k_min=5 and fail-closed guards pass 12+13 tests (AUDIT.md §1); the live adapter has no privacy enforcement because it does not exist yet (AUDIT.md G-a); DPIA, privacy statement and signage are still open (PRIV-01..03) — DPIA-lite + statement + signage in S8 (D9) |
| TRL-6 deadline: 2026-05-31 | Aggressive but anchored on funder/academic rhythm. | ⚠️ Revisit if M1 slips by >1 week | **missed** — no field unit, benchmark, soak or field-run evidence exists anywhere in the repo (AUDIT.md §8 run #2; §5 deployment gaps). M1 re-baselined to 2026-12-31 (D12, decided 2026-09-15) |
| Fine-tuned 9-class YOLO11 (not generic COCO) | Domain match matters (e-scooter, delivery van, SUV absent from COCO). | ✓ Good — model already trained | **revised** — the fine-tuned weights on `main` are 6-class only, missing e-scooter/SUV/delivery_van (AUDIT.md §1 "Model / weights / dataset (main) — MISSING (9-class)"); the paper's 9-class NCNN model exists on `origin/TRA2026` (AUDIT.md G-i) and is brought to `main` by S1, not retrained |
| Pi 5 8GB as deployment target | On hand; 8GB headroom for future ML tasks (pose, re-id) without re-platforming. | — Pending (benchmark in M1) | decided; unchanged. No Pi benchmark has been run (AUDIT.md §1 "Pi 5 8 GB, CPU-only NCNN node — NOT VERIFIED on hardware") — S6 |
| Fluid Compute + Neon + Marketplace integrations | Vercel-native path; no VPS, no broker, no separate ingestor. | — Pending | decided; implemented in config (`vercel.ts`, Fluid Compute, Neon Marketplace path); not deployed — "Not deployed yet" (AUDIT.md §1 "Vercel deploy — NOT DEPLOYED") — S5 |

## Evolution

This document is updated at plan revisions and milestone boundaries: when a decision's status changes, when the core value or constraints drift, or when out-of-scope items are revisited. There is no GSD phase-transition or milestone-completion command driving this anymore — updates happen by direct edit, cross-referenced against `PLAN.md` and `STATE.md`.

---
*Rewritten 2026-09-15 from the 2026-04-23 original (archived at `old/2026-09-15-gsd/PROJECT.md`).*
