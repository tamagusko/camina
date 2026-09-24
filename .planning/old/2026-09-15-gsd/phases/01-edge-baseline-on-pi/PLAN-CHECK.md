# Phase 1 Plan Check — Edge Baseline on Pi (Second Pass)

**Verifier:** gsd-plan-checker (goal-backward, FORCE stance)
**Date:** 2026-05-09
**Plans reviewed:** 01-01, 01-02, 01-03, 01-04 (post-revision)
**Phase goal (post-amendment):** Pi 5 8GB runs full sensor daemon end-to-end with systemd supervision, USB-SSD durability, 30-min benchmark, 48-h soak; NTP gate on edge (server-side skew rejection moved to Phase 2 SC#5).
**Pass 1 verdict:** REVISE-BLOCKERS (3 blockers + several flags).
**Pass 2 verdict:** PASS (with 2 minor warnings — non-blocking).

---

## Per-plan verdicts

| Plan | Verdict | One-line reason |
|------|---------|-----------------|
| 01-01 | PASS | Untouched since first pass; spot-check confirms NCNN + picamera2 + tracker + daemon wiring still goal-aligned. |
| 01-02 | PASS | Task 4 added (real-publisher 15-min smoke vs Vercel preview, schema-validated). `replace_publisher` introduced. FPS measurement pinned to wrapping `detect_and_track`. Tests always pass `--video` with explicit macOS skip. T-01-02-06/07 added. §9b owned cleanly. |
| 01-03 | PASS | `depends_on` relaxed to `["01-01"]` (wave 3 retained for shared-file ownership). `notify_ready()` is first executable line; Test 8 enforces ≤1 s. `_integrity_check_or_quarantine` extracted to `src/camina/utils/sqlite_integrity.py`; `core/` no longer imports from `io/`. systemd `ExecStart` unchanged; only `Type=simple→notify` + `WatchdogSec=300`. Verify uses `! grep -q "^Type=simple"`. New `test_dry_run_skips_ntp_gate`. `DaemonConfig.from_yaml` coerces `state_db_path` and `ncnn_model_path` to `Path`. |
| 01-04 | PASS | Kill -9 drill BEFORE 48-h heartbeat window (separate `kill9-drill-<YYYYMMDD>.log`). `--expected-sensor-id` flag + first/last drift check. `heartbeatPayloadSchema.strict()` mirrors Pydantic `extra="forbid"`. `assert isinstance(state_db_path, Path)` defensive guard added. |

---

## Goal achievement: 5 SC × 4 plans matrix

| SC# | Criterion (post-amendment) | Status | Where covered |
|-----|----------------------------|--------|---------------|
| 1 | Real `/counts` POST every 15 min on Pi to Vercel preview, HTTP 2xx, validates `countsPayloadSchema` | **COVERED** | 01-02 Task 4 (15-min Pi run, ≥1 successful POST, schema-validated via `countsPayloadSchema.safeParse`, transcript in §9b). Closes Pass-1 Blocker 2. |
| 2 | 30-min benchmark, FPS ≥ 5 at imgsz=480, no throttle | COVERED | 01-02 Task 1 (driver) + Task 3 (human-verify gate). |
| 3 | systemd survives `kill -9`; RSS flat 48 h | COVERED | 01-03 Tasks 1+3 (watchdog + Type=notify). 01-04 Task 3 (kill -9 drill BEFORE soak; clean 48-h window evaluates `no_restarts` against post-drill state). Closes Pass-1 Blocker 3. |
| 4 | Daemon refuses start until NTP synced (edge half ONLY) | COVERED | 01-03 Task 1 (`wait_for_ntp_sync` + `--dry-run` bypass tested). ROADMAP amended 2026-04-28 to remove server half from this SC. Closes Pass-1 Blocker 1. |
| 5 | `state.db` on USB SSD; `PRAGMA integrity_check` green | COVERED | 01-03 Task 2 (integrity_check + quarantine via `utils/sqlite_integrity.py`) + Task 3 (USB SSD docs §10 + recovery drill). |

**All 5 SC COVERED.** No GAPs, no PARTIALs.

---

## Findings

| Plan | Severity | Location | Issue | Suggested fix |
|------|----------|----------|-------|---------------|
| 01-03 | WARNING | New `src/camina/utils/` package | No import-linter / lint rule prevents future regressions where a contributor adds `from src.camina.core import …` or `from src.camina.io import …` to `utils/sqlite_integrity.py`. The current Test 5 (`test_helper_lives_in_utils`) confirms binding identity but does not enforce the no-upward-import rule. | Future-debt: add an `import-linter` config or a one-line CI grep `! grep -E "from src\.camina\.(io\|core)" src/camina/utils/*.py`. Non-blocking — current single-helper module is unlikely to grow upward imports in Phase 1 timeframe. |
| 01-04 | WARNING | `dashboard/src/lib/schemas.ts::heartbeatPayloadSchema.strict()` | `.strict()` mirrors Python `extra="forbid"` correctly for Phase 1, but Phase 3 (Simulated fleet) may emit synthetic heartbeats with debug-only fields. If the simulator rides the same schema, `.strict()` will reject. Coupling risk: a Phase 3 task could be tempted to relax `.strict()` rather than build a dedicated simulator schema. | Future-debt: when Phase 3 lands, simulator MUST emit only canonical `HeartbeatPayload` fields OR use a separate looser schema (e.g. `heartbeatPayloadSchema.passthrough()` for simulator-only ingestion). Flag for Phase 3 plan-checker. Non-blocking for Phase 1. |
| 01-03 | INFO | 01-03 Task 1 sensor_daemon.py module entry point | Plan still references both `scripts/run_sensor.py` (NTP gate inline) AND `python -m src.camina.service.sensor_daemon` (rollback path) running the same NTP gate. Plan says "if module entry point shares a function — confirm one or the other". Executor must verify module entry point's `main()` either delegates to `scripts.run_sensor.main` OR duplicates the NTP-gate block. Mild ambiguity — relies on executor reading existing code. | Acceptable as-is; executor is competent. Worth a one-line note in 01-03-SUMMARY.md confirming which path was chosen. |
| All  | INFO | Threat models | All STRIDE blocks updated; T-01-02-06/07 (§9b transcript redaction + payload-validation tampering) and T-01-04-07 (Blocker-3 self-contradiction historic risk) added. Privacy non-negotiables not violated. | None. |

**No BLOCKERs.** 2 WARNINGs (both future-debt for later phases). 2 INFOs.

---

## Requirements coverage matrix

| Requirement | Covering plan(s) | Status |
|-------------|-----------------|--------|
| EDGE-01 | 01-01 + 01-02 Task 4 (real-publisher smoke) | COVERED |
| EDGE-02 | 01-01 (RGB888 grep-enforced; no `cv2.cvtColor` in production camera path) | COVERED |
| EDGE-03 | 01-02 (driver + human-verify) | COVERED |
| EDGE-04 | 01-02 §9 docs + 01-04 (heartbeat throttle field) | COVERED |
| EDGE-05 | 01-03 Task 2 (SQLite integrity) + Task 3 (USB SSD docs §10) | COVERED |
| EDGE-06 | 01-03 (watchdog) + 01-04 Task 3 (kill -9 drill log) | COVERED |
| EDGE-07 | 01-03 (edge half — NTP gate) | COVERED (server half scoped to Phase 2 SC#5 per ROADMAP amendment) |
| EDGE-08 | 01-04 (heartbeat enrichment + soak monitor) | COVERED |

8/8 requirements COVERED for Phase 1's scope. EDGE-07 server-half is now ROADMAP Phase 2 SC#5 (legitimately deferred, not silently dropped).

---

## Solo-dev scope assessment

W1 budget: 2026-04-24 → 2026-05-01 (one calendar week, solo dev + 2 interns).

| Plan | Tasks | Files | Realistic wall-clock |
|------|-------|-------|----------------------|
| 01-01 | 3 (all auto) | ~10 | 2-3 days code |
| 01-02 | 4 (2 auto + 2 human-verify) | ~5 + transcripts | 1-2 days code + 30-min Pi run + 15-min smoke run |
| 01-03 | 3 (all auto) | ~14 | 2-3 days code (highest single-plan code volume; bordering on split) |
| 01-04 | 3 (2 auto + 1 human-verify) | ~11 + transcripts | 1 day code + 30-min kill -9 drill + **48-h wall-clock soak** |

**Total elapsed minimum:** 30-min bench + 15-min smoke + 30-min drill + 48-h soak = ~50 hours of Pi-bound wall-clock + ~5 working days of code (with 2 interns parallelizing on 01-01 and 01-03 in W1 then handing off to 01-02 and 01-04).

**Verdict:** Within W1 budget IF the soak starts no later than Tuesday EOD W1. 01-03's 14-file count is high but split is unwarranted because all changes are tightly coupled around the systemd/NTP/SQLite hardening axis. Within solo-dev cognitive load.

---

## Privacy non-negotiables

- k_min=5: not in Phase 1 scope (Phase 5/10).
- No exact-GPS publicly: not in Phase 1 scope.
- ON DELETE CASCADE: not in Phase 1 scope (Phase 5).
- No PII logging: confirmed (T-01-01-04 forbids bbox/frame logging; T-01-01-06 confirms `run_sensor.py` logs only `sensor_id`; T-01-02-01/06 require redacted transcripts; T-01-03-03 confirms `CountsPayload` is token-free).
- API token leak vectors: T-01-01-01 inherits placeholder; T-01-02-06 mandates Bearer redaction in §9b transcripts.

PASS.

---

## Tech-stack accuracy

- Custom Kalman + Hungarian (NOT SORT): confirmed 01-01 reuses `src/camina/core/tracker.py`.
- Ultralytics YOLO11 NCNN export: confirmed 01-01 Task 1 + class-mismatch guard.
- picamera2 RGB888 direct (no `cv2.cvtColor` in production camera path): grep-enforced 01-01.
- `filterpy + scipy` tracker: inherited from existing `core/tracker.py` (untouched).
- Pydantic for edge schemas (`extra="forbid"`): preserved in 01-04 Task 1.
- zod on dashboard (`.strict()` for parity): added in 01-04 Task 1.
- `Type=notify` + `WatchdogSec=300` + `Requires=time-sync.target`: confirmed 01-03 Task 3.
- USB-SSD with `PRAGMA integrity_check`: confirmed 01-03 Tasks 2+3.
- `bench_sensor.py` uses `cv2.VideoCapture` for `--video` fallback only (bench-only, not production); appropriately commented.

PASS.

---

## File-conflict avoidance

`docs/sensor_deployment.md` ownership across waves:
- 01-01 owns §6, §7 (NCNN export, daemon invocation)
- 01-02 owns §8, §9, §9b (benchmark, cooler, real-publisher smoke)
- 01-03 owns §10 (USB SSD)
- 01-04 owns §11 (48-h soak with kill -9 drill BEFORE)

No section overlap. 01-04 §11 explicitly notes "Append AFTER §10. Do not modify §1-§10." 01-02 Task 4 explicitly inserts §9b "between §9 and any future §10".

`configs/sensor.yaml`: 01-01 adds NCNN fields; 01-03 adds `ntp_timeout_s` + comment on `state_db_path`. No overlap.

`src/camina/service/sensor_daemon.py`: touched by 01-01 (un-stub main + DaemonConfig fields), 01-02 (adds `replace_publisher`), 01-03 (notify_ready + notify_watchdog + Path coercion in `from_yaml`), 01-04 (heartbeat enrichment + Path assert). Four plans, four distinct sections. Wave order is serial (W1→W2→W3→W4), so no merge conflict risk. Plan 01-02 explicitly says "Do NOT change anything else in `sensor_daemon.py` — Plan 01-03 owns the watchdog/notify_ready edits there; Plan 01-04 owns the heartbeat enrichment edits there."

PASS.

---

## Reproducibility

- Configs: `configs/sensor.yaml` carries every tunable (NCNN model path, imgsz, conf_threshold, ntp_timeout_s).
- Seeds: not relevant for inference-only Pi pipeline.
- Env recording: 01-02 benchmark records `vcgencmd get_throttled`, RSS, temp at start/mid/end; 01-04 soak records uptime, RSS, throttled per heartbeat.
- Transcripts: 01-02 commits `bench-*.{md,json}` + §9b smoke transcript; 01-04 commits separate `kill9-drill-*.log` + `soak-*.md` (Blocker-3 fix).

PASS.

---

## New-risk findings (3 items raised by user)

### Risk 1: `Type=notify` boot timeout (notify_ready before any blocking work)

01-03 Task 1 mandates `notify_ready()` as the FIRST executable statement of `SensorDaemon.start()` — explicitly BEFORE `logger.info`, BEFORE thread setup, BEFORE any IO. Test 8 enforces this with a recorder pattern (`events[0] == "notify_ready"`) and a `time.monotonic()` delta assertion (<1 s on dev hosts).

**Smuggled import-time work check:** `src/camina/service/watchdog.py` imports only `os`, `socket`, `logging` — all stdlib, no heavy modules. `from src.camina.service.watchdog import notify_ready, notify_watchdog` at module top of `sensor_daemon.py` does not trigger any sd_notify call (the call only happens when `notify_ready()` is invoked). NTP gate runs in `scripts/run_sensor.py` BEFORE `compose()` returns the daemon, so `start()` is never reached if NTP fails. The integrity check (01-03 Task 2) runs inside `OfflineBuffer.__init__`, which executes during `compose(...)` (BEFORE `start()`), so corrupt-SSD cost is paid before `notify_ready()` is needed.

**Verdict:** Risk mitigated by the explicit ordering rule + the fact that all heavy-cost paths (compose, integrity check, NTP gate) execute outside `start()`. **No blocker.**

### Risk 2: No import-linter on `src/camina/utils/`

Confirmed — no automated guard prevents `utils/sqlite_integrity.py` from gaining an upward import. Test 5 (`test_helper_lives_in_utils`) confirms `_integrity_check_or_quarantine` is bound to the same function object across `io.offline_buffer`, `core.counter`, and `utils.sqlite_integrity`, but does not assert the absence of upward imports inside `utils/`.

**Verdict:** WARNING (future-debt, see Findings table). For Phase 1 scope, the `utils/` package contains exactly one file with stdlib-only dependencies. Risk is theoretical until Phase 2+ adds more utils. **Non-blocking.**

### Risk 3: `.strict()` in `heartbeatPayloadSchema` vs Phase 3 simulator

Confirmed — Phase 3 (Simulated sensor fleet) is the next consumer of dashboard schemas. If the simulator emits heartbeats with debug-only fields (e.g. `simulator_seed`, `synthetic_marker`), `.strict()` will reject. The simulator could either (a) emit only canonical fields, or (b) ride a dedicated simulator schema, or (c) Phase 3 could relax `.strict()`.

**Verdict:** WARNING (Phase-3 coupling, see Findings table). Phase 1's `.strict()` decision is correct for the production Python ↔ TypeScript parity goal. The Phase 3 plan-checker should explicitly evaluate this when it sees plans for `simulate-fleet.mjs`. **Non-blocking for Phase 1.**

---

## Wave + file ownership

Confirmed structure unchanged from Pass 1:
- W1: 01-01 (sole plan; foundational)
- W2: 01-02 (depends_on 01-01; 30-min human-verify gate)
- W3: 01-03 (depends_on 01-01; wave 3 retained for shared-file ownership of `sensor_daemon.py` + `docs/sensor_deployment.md`)
- W4: 01-04 (depends_on 01-01, 01-02, 01-03; 48-h human-verify gate)

01-03's `depends_on` was correctly relaxed from `["01-01", "01-02"]` to `["01-01"]` (per Pass-1 wave-deps flag). This means a 01-02 *failure* no longer blocks 01-03 logically; the wave-3 placement is purely about avoiding merge conflicts with 01-02's same-file edits.

PASS.

---

## Top blockers

**None.** All three Pass-1 blockers resolved:

1. **SC#4 server-side rejection** → ROADMAP amended 2026-04-28 to scope server-half to Phase 2 SC#5; Phase 1 SC#4 now covers ONLY the edge NTP gate, which 01-03 implements.
2. **No real `/counts` POST verification** → 01-02 Task 4 added (15-min Pi run, ≥1 successful 2xx POST to Vercel preview, schema-validated via `countsPayloadSchema.safeParse`, transcript committed to §9b).
3. **01-04 kill -9 vs `no_restarts` self-contradiction** → Fix A applied: kill -9 drill runs BEFORE the 48-h heartbeat window in a separate transcript file (`kill9-drill-<YYYYMMDD>.log`); the clean 48-h window evaluates `no_restarts` against a post-drill restart-free state.

Plus all five high-value flags from Pass 1 addressed:
- 01-02 dev-host import path → tests always pass `--video`; macOS skip documented (Test 4 docstring).
- 01-03 `notify_ready()` placement → enforced as first executable statement (Test 8).
- 01-03 core/io coupling → `_integrity_check_or_quarantine` extracted to `src/camina/utils/sqlite_integrity.py` (Test 5 confirms identity).
- 01-03 wave-3 deps → relaxed to `["01-01"]`.
- 01-04 zod parity with Python `extra="forbid"` → `.strict()` added; Test 8 confirms unknown-key rejection.

---

## Overall verdict

**PASS** — plans cleared for execution.

Two minor warnings (future-debt for Phase 2+ and Phase 3 respectively) are documented but non-blocking. No scope reduction detected. No locked decisions contradicted. No deferred ideas leaked. Architectural responsibility map respected (`core/` I/O-purity preserved via `utils/` shim; edge ↔ dashboard contract symmetric via `.strict()`). Privacy non-negotiables intact. Tech-stack accuracy verified end-to-end. Solo-dev scope realistic within W1 budget assuming soak starts by Tuesday EOD.

Plan set is TRL-6-grade. Cleared to run `/gsd-execute-phase 1`.
