# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-23)

**Core value:** One Raspberry Pi on one real Dublin street, detecting and counting nine road-user classes and feeding a live public dashboard — demonstrably privacy-preserving, lightweight, and reproducible.
**Current focus:** Phase 1 (Edge baseline on Pi) — ready to plan

## Current Position

Phase: 1 of 11 (Edge baseline on Pi)
Plan: 0 of 4 executed (4 of 4 planned + checked)
Status: Ready to execute
Last activity: 2026-05-09 — Phase 1 plans 01-02/01-03/01-04 revised after PLAN-CHECK pass-1 flagged 3 blockers + 11 issues. ROADMAP amended (SC#4 split: edge-only NTP gate in Phase 1; server-side 60s rejection moved to Phase 2 SC#5 alongside Publisher refactor + attachDatabasePool). Pass-2 PLAN-CHECK = PASS (0 blockers, 2 future-debt warnings).

Progress: [░░░░░░░░░░] 0% (0 of ~31 plans executed)

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

- **Future-debt (post-Phase-1):** Add import-linter rule preventing `src/camina/utils/` from importing `core/` or `io/` (currently no enforcement; new `utils/sqlite_integrity.py` is stdlib-only, so risk theoretical until Phase 2+).
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

Last session: 2026-05-09 — Phase 1 plans drafted, plan-checked (pass-1 REVISE-BLOCKERS), revised, plan-checked (pass-2 PASS). ROADMAP scope-split confirmed by user.
Stopped at: Ready to commit revision artifacts (ROADMAP.md + 01-02/01-03/01-04 revised + PLAN-CHECK.md + REVISION-NOTES.md + this STATE.md sync) then `/gsd-execute-phase 1`.
Resume file: `.planning/phases/01-edge-baseline-on-pi/PLAN-CHECK.md`.

---
*STATE.md initialised 2026-04-23. Synced 2026-05-09.*
