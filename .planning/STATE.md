# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-23)

**Core value:** One Raspberry Pi on one real Dublin street, detecting and counting nine road-user classes and feeding a live public dashboard — demonstrably privacy-preserving, lightweight, and reproducible.
**Current focus:** Phase 1 (Edge baseline on Pi) — ready to plan

## Current Position

Phase: 1 of 11 (Edge baseline on Pi) — but see 2026-07-10 note: a full audit-and-harden pass (outside GSD, user-directed) implemented much of Phases 2/5/6/7/9 scope directly.
Plan: 0 of 4 executed (4 of 4 planned + checked)
Status: GSD plans stale — re-baseline against the 2026-07-10 audit outcomes before executing Phase 1 plans.
Last activity: 2026-07-10 — Full audit + hardening executed directly (user opted out of GSD for this work): edge publish pipeline hardened (worker-thread publish, jitter, sd_notify watchdog, SQLite self-healing, HTTPS enforcement), live ingest persistence (idempotent upserts, per-sensor SHA-256 tokens, attachDatabasePool, skew rejection, rate limiting), fail-closed production gates, k_min=5 suppression + staleness surface, 90-day retention + bounded MVs + Hobby-safe cron topology, LoRa schema-v2 codec + TTN webhook, class taxonomy reconciled (canonical 9-class locked; retrain blocked only on v2-class relabel), dataset converted + held-out set frozen. Tests: 144 pytest, 89 vitest, 6 e2e, tsc clean, pnpm build green. See docs/production_readiness.md + TODO.md.

Progress: [░░░░░░░░░░] 0% of GSD plans (0 of ~31) — substantial equivalent scope delivered outside GSD 2026-07-10; ROADMAP/plans need re-baselining

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|---|---|---|---|
| — | — | — | — |

**Recent Trend:**
- Last 5 plans: —
- Trend: — (no data yet)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Most load-bearing for current work:

- HTTPS-primary + LoRaWAN-secondary transport (LoRa P1 = after WiFi works)
- Two milestones: M1 Edge-first (by 2026-05-15), M2 Cloud+real-street (by 2026-05-31)
- Dublin-only in v1; multi-city explicitly out of scope
- Privacy-by-design is load-bearing (k_min=5, no exact GPS publicly, CASCADE erasure)
- `attachDatabasePool` from `@vercel/functions` is mandatory before M2 cloud work (per research)

### Pending Todos

- **Future-debt (post-Phase-1):** Add import-linter rule preventing `src/camina/utils/` from importing `core/` or `io/` (currently no enforcement; the planned `utils/sqlite_integrity.py` — not yet implemented as of 2026-07-10 — will be stdlib-only, so risk theoretical until Phase 2+).
- **Phase-3 coupling watch:** `dashboard/src/lib/schemas.ts::heartbeatPayloadSchema.strict()` will reject unknown keys. Phase 3 simulator must NOT ride heartbeat schema for debug fields. Flag for Phase-3 plan-checker.
- **CONTRIBUTING.md "Getting help" placeholders** still need stand-up time + async chat URL before interns start.

### Blockers / Concerns

Research-surfaced pre-phase blockers (must resolve in W1 before the relevant phase):

- **TTN Dublin coverage at the target street** (blocks Phase 4 LoRa) — walk-test required, TTIG gateway (~€90) as fallback.
- **Pi FPS on the fine-tuned CAMINAv1 NCNN model** (blocks Phase 1 readiness) — 30-min in-enclosure benchmark at ≥25 °C ambient.
- **Cars-count codec width** `uint8` vs `uint16` (blocks Phase 4 codec freeze).
- **UCD Google Workspace OAuth app type** (blocks Phase 6 Auth) — confirm "internal" app type to skip external-app verification.
- **RAK3172 + TTIG procurement** (blocks Phase 4) — order in W1.
- **UCD ethics DPO contact** (blocks Phase 10 signage + privacy statement).

### Known code-level concerns

From `.planning/codebase/CONCERNS.md` — carry into the phases that touch them:

- `NEXT_PUBLIC_CAMINA_DEV_ADMIN` prod-leak risk → Phase 7 (build-time guard)
- Dev auth allowlist fail-open default → Phase 6 (fail-closed assertion)
- `AUTH_SECRET` rotated 2026-04-23 after it was observed by a subagent during mapping
- MapLibre canvas race workarounds (ResizeObserver, inline absolute-inset, StrictMode off) — tech-debt; post-demo (v2 TECH-01..03)
- 501 stubs in `/api/ingest/*` must be removed before live-mode flip → Phase 9 (SEC-05)

## Deferred Items

| Category | Item | Status | Deferred At |
|---|---|---|---|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-10 — audit-and-harden pass, all findings implemented and pushed (see Last activity above). Remaining non-code work: human relabel of e-scooter/SUV/delivery_van (only retrain blocker), TTN walk-test + RAK3172, pre-live-flip ops steps (docs/operations.md).
Stopped at: All audit work committed + pushed to origin/main. Next GSD action: re-baseline ROADMAP/Phase-1 plans against the delivered scope before `/gsd-execute-phase 1`.
Resume file: `docs/production_readiness.md` + `TODO.md` (audit state); `.planning/phases/01-edge-baseline-on-pi/PLAN-CHECK.md` (stale GSD plans).

---
*STATE.md initialised 2026-04-23. Synced 2026-05-09.*
