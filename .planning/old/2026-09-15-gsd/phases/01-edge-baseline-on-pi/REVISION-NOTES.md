# Phase 1 Plan Revision Notes

**Date:** 2026-04-28
**Trigger:** PLAN-CHECK.md verdict `REVISE-BLOCKERS` (3 blockers + 11 high-value flags)
**Plans revised:** 01-02, 01-03, 01-04 (in place). 01-01 NOT touched (PASS).

---

## Blocker resolutions

### Blocker 1 — ROADMAP SC#4 server-side rejection scope

**File:** `.planning/ROADMAP.md`
**Sections:** Phase 1 SC#4 (line 41); Phase 2 Goal (line 55), Requirements (line 57), SC#5 added (line 62); footer "Last updated".

- Phase 1 SC#4 rewritten to: *"Daemon refuses to start until NTP synced (server-side rejection moved to Phase 2)."*
- Phase 2 Goal sentence appended: *"Also lands the server-side 60-second skew rejection on `/api/ingest/sensors/[id]/counts` (split out of Phase 1 SC#4)."*
- Phase 2 Requirements line: added `EDGE-07 (server half)`.
- Phase 2 SC#5 added: *"Server rejects payloads with `abs(produced_at - server_now) > 60s` in `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts`; regression test covers both reject (>60s skew) and accept (≤60s skew) paths. (Migrated from Phase 1 SC#4 — edge half stays in Phase 1.)"*
- Plan 01-03 objective + threat model T-01-03-02 reworded to acknowledge the scope split.

> **ROADMAP amended — user must confirm scope split before execution.**

### Blocker 2 — SC#1 real `/counts` POST verification

**File:** `01-02-PLAN.md`
**Sections:** new Task 4 (`<task type="checkpoint:human-verify">` after Task 3); `must_haves.truths`; `<success_criteria>`; threat model T-01-02-06 / T-01-02-07.

- New Task 4 *"Real-publisher smoke run against Vercel preview"* added after Task 3.
- Acceptance: 15-min Pi run with `transport=https` + `publish_url` pointing at a Vercel preview; ≥1 successful 2xx POST to `/api/ingest/sensors/<id>/counts`; payload validated by `dashboard/src/lib/schemas.ts::countsPayloadSchema.safeParse`; transcript appended to `docs/sensor_deployment.md` §9b.
- Owner solo-dev (human-verify); intern shadow allowed.
- Wave 2 retained (human-verify only — no code change in this task).

### Blocker 3 — 01-04 kill -9 drill vs `no_restarts` gate

**File:** `01-04-PLAN.md`
**Sections:** Task 2 §11 doc template; Task 3 procedure (renumbered steps 2-3); `must_haves.truths`; threat model T-01-04-07.

- Applied **Fix A**: kill -9 drill sequenced BEFORE the 48-h heartbeat window. Drill evidence committed to a SEPARATE file `docs/benchmarks/kill9-drill-<YYYYMMDD>.log`, not into the soak transcript.
- §11 procedure now reads: (1) baseline daemon, (2) kill -9 drill + log, (3) clean restart, (4) 48-h heartbeat collection, (5) monitor.
- Failure response section explicitly forbids the "annotate restart as intentional" anti-pattern that previously made the gate self-contradictory.

---

## High-value flags fixed in same pass

| Plan | Flag | Resolution |
|------|------|------------|
| 01-02 Task 1 | dev-host import safety | Tests ALWAYS pass `--video <fixture>`; skip cleanly if fixture absent. |
| 01-02 Task 1 | FPS measurement | Pinned to wrapped `detect_and_track` closure; counter delta forbidden. |
| 01-02 Task 1 | publisher access | Added `SensorDaemon.replace_publisher(publisher)` public method; bench uses it instead of `_publisher = ...`. |
| 01-03 frontmatter | wave deps | `depends_on` reduced to `["01-01"]`; wave kept at 3 because of shared file ownership (sensor_daemon.py, sensor_deployment.md). |
| 01-03 Task 1 | notify_ready ordering | Made FIRST executable line of `start()`; Test 8 enforces ordering + <1 s timing. |
| 01-03 Task 2 | core/io coupling | Helper moved to NEW `src/camina/utils/sqlite_integrity.py`; both io and core import from utils. |
| 01-03 Task 3 | systemd ExecStart | UNCHANGED from Plan 01-01 (module entry preserved as rollback). Only `Type=notify` + `WatchdogSec` + hardening added. |
| 01-03 Task 1 | dry-run NTP skip | New `tests/test_run_sensor.py::test_dry_run_skips_ntp_gate` + `test_real_run_calls_ntp_gate`. |
| 01-03 Task 3 | verify-line nit | Fixed: `! grep -q "^Type=simple"` (negation form, not pipe-to-grep-empty). |
| 01-04 Task 1 | state_db_path Path | `assert isinstance(self._config.state_db_path, Path)` defensive guard in `_send_heartbeat`; `DaemonConfig.from_yaml` coerces in 01-03 Task 1 (single source of truth). |
| 01-04 Task 2 | monitor sanity | New `--expected-sensor-id` flag + `check_sensor_id_consistency` (per-mismatch warnings + first/last drift check); `sensor_id_mismatch_count` row in transcript. |
| 01-04 Task 1 | zod parity | `dashboard/src/lib/schemas.ts::heartbeatPayloadSchema.strict()` mirrors Pydantic `extra="forbid"`; new test confirms unknown-key rejection. |

---

## New risks introduced

1. **ROADMAP scope split is user-pending.** Phase 2 now carries one extra SC (server-side 60s rejection). User must confirm the split before Phase 1 transition; otherwise EDGE-07 risks falling through the cracks.
2. **`Type=notify` boot timeout.** If `notify_ready()` ever regresses out of the top of `start()`, systemd will hard-kill the daemon on TimeoutStartSec. Test 8 catches dev-time regressions; production needs a 1-time `journalctl` confirmation on first deploy.
3. **`utils/sqlite_integrity.py` is a new module.** Imports cycle-checked manually; CI would benefit from an `import-linter` rule. Tracked as low-priority test hygiene.
4. **`.strict()` on `heartbeatPayloadSchema` is breaking** for any old client that posts unknown keys. Mitigated by the schema being internal (Pi → dashboard), but if the simulator (Phase 3) injects extra fields, those need to be in the schema.

No privacy non-negotiables violated. STRIDE registers updated for all three plans.

---

## Ready for plan-checker re-run

**YES.**

The three blockers and all high-value flags are resolved with concrete file/line edits. ROADMAP amended. No 01-01 changes. Wave structure (1 → 2 → 3 → 4) preserved.

**User confirmation needed before execution:** Phase 2 SC scope expansion (Blocker 1 split).
