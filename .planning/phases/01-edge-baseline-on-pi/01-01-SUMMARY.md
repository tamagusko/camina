---
phase: 01-edge-baseline-on-pi
plan: 01
plan_number: 1
type: summary
wave: 1
status: complete
requirements: [EDGE-01, EDGE-02]
tags: [edge, yolo, ncnn, picamera2, python, kalman, hungarian, tracker]
one_liner: "Production entry point that wires CAMINAv1 NCNN + custom Kalman+Hungarian tracker + picamera2 RGB888 into the SensorDaemon, with class-taxonomy guards and DI-friendly factories."
dependency_graph:
  requires: []
  provides:
    - "scripts/run_sensor.py — production CLI"
    - "src.camina.service.compose.compose — DI factory wiring camera + detector + daemon"
    - "src.camina.service.camera.picamera2_frame_source — RGB888 generator"
    - "src.camina.service.detect_track.make_detect_and_track — YOLO NCNN + Sort closure"
    - "src.utils.export_ncnn.main — idempotent NCNN export CLI"
    - "DaemonConfig.{ncnn_model_path,imgsz,conf_threshold} — new YAML fields"
  affects:
    - "src/camina/service/sensor_daemon.py::main (un-stubbed; delegates to compose)"
    - "configs/sensor.yaml (3 new fields)"
    - "docs/sensor_deployment.md §6 + §7 (NCNN export + daemon invocation)"
tech_stack:
  added:
    - "filterpy (runtime dep — was already imported by core/tracker.py and listed in requirements.txt; surfaced as missing in the local env during Task 2 and installed)"
  patterns:
    - "Dependency injection via ``camera_factory=`` / ``detect_factory=`` kwargs so CI never imports picamera2 or Ultralytics"
    - "Per-class tracker instances (one Sort per class) so integer track-ids stay class-scoped, then prefixed with class-name string in emitted track-id"
    - "Class-taxonomy guard at both export time AND closure-build time — wrong-model failures fail loudly before any frame is processed"
key_files:
  created:
    - "scripts/run_sensor.py"
    - "src/camina/service/camera.py"
    - "src/camina/service/detect_track.py"
    - "src/camina/service/compose.py"
    - "src/utils/__init__.py"
    - "tests/test_export_ncnn.py"
    - "tests/test_detect_track.py"
    - "tests/test_compose.py"
    - "tests/test_run_sensor.py"
  modified:
    - "src/utils/export_ncnn.py (full rewrite — was 16-line legacy print script)"
    - "src/camina/service/sensor_daemon.py (un-stub main + 3 new DaemonConfig fields)"
    - "configs/sensor.yaml (+3 NCNN fields)"
    - "docs/sensor_deployment.md (§6 NCNN export, §7 daemon invocation, Troubleshooting -> appendix)"
decisions:
  - "Use existing Sort class as the tracker; DO NOT introduce a new Tracker/Detection abstraction (deviation from plan-stated API)"
  - "One Sort instance per class, with track-ids prefixed by class-name to avoid cross-class id collisions in WindowedCounter"
  - "Add sys.path bootstrap in scripts/run_sensor.py so the documented ``uv run python scripts/...`` invocation works without PYTHONPATH dance"
  - "Move existing 'Troubleshooting' to unnumbered appendix so plans 01-02..04 can append §8-§11 without renumbering"
metrics:
  duration_minutes: ~75
  completed: 2026-05-10
  commits: 3
  files_created: 9
  files_modified: 4
  tests_added: 17
  tests_total: 77
---

# Phase 1 Plan 01: Edge Baseline on Pi — Production Entry Point Summary

Production entry point that wires the fine-tuned 9-class CAMINAv1 YOLO11
NCNN detector, the existing custom Kalman+Hungarian tracker
(`src.camina.core.tracker.Sort`), and the picamera2 RGB888 frame source
into the existing `SensorDaemon`, removing the `SystemExit` stub at
`src.camina.service.sensor_daemon.main`. Unlocks every downstream Phase 1
plan that depends on a runnable Pi 5 daemon.

## Commits

| # | SHA | Subject |
|---|-----|---------|
| 1 | `7019c67` | feat(utils): NCNN export CLI with class-taxonomy guard (EDGE-01) |
| 2 | `8f265f4` | feat(service): camera + detect_track + compose factory (EDGE-01, EDGE-02) |
| 3 | `9dcf793` | feat(service): production entry point + un-stub sensor_daemon.main (EDGE-01) |

## Files

**Created (9):**
- `scripts/run_sensor.py` — argparse CLI (`--config`, `--dry-run`)
- `src/camina/service/camera.py` — `picamera2_frame_source(imgsz)` generator (RGB888 direct, no cv2.cvtColor)
- `src/camina/service/detect_track.py` — `make_detect_and_track(...)` closure factory; per-class `Sort` trackers; class-name prefixed track-ids
- `src/camina/service/compose.py` — `compose(cfg, ncnn_model_path, ..., *, camera_factory=, detect_factory=)` DI factory
- `src/utils/__init__.py` — package marker so `python -m src.utils.export_ncnn` resolves
- `tests/test_export_ncnn.py` (5 tests)
- `tests/test_detect_track.py` (4 tests)
- `tests/test_compose.py` (4 tests)
- `tests/test_run_sensor.py` (4 tests)

**Modified (4):**
- `src/utils/export_ncnn.py` — full rewrite (was a 16-line legacy print-based script that ran `model.export()` at import time as a side effect); now a proper argparse CLI with idempotency guard, class-taxonomy assertion, and stdlib `logging`
- `src/camina/service/sensor_daemon.py` — un-stub `main()` (removed `raise SystemExit("Instantiate SensorDaemon from the production entry point...")`) and added 3 optional `DaemonConfig` fields (`ncnn_model_path`, `imgsz`, `conf_threshold`) with `from_yaml` defaults
- `configs/sensor.yaml` — added `ncnn_model_path`, `imgsz`, `conf_threshold` (preserving all existing fields)
- `docs/sensor_deployment.md` — replaced TODO sketch with `§6 NCNN model export` (Task 1) and `§7 Running the daemon` (Task 3) including macOS dev-host notes; existing "Troubleshooting" moved to an unnumbered appendix to keep §8-§11 free for plans 01-02..04 per plan-checker ownership map

## Tests

`uv run pytest tests/ -x -q` -> **77 passed** (60 baseline + 17 new across this plan).

Per-task test coverage:
- Task 1 (`tests/test_export_ncnn.py`): module imports cleanly + exposes `main`, `--help` exits 0 listing all 5 flags, missing `--source` exits 2, idempotent skip when target dir exists, class-taxonomy mismatch raises `SystemExit`. YOLO is monkeypatched so no model export runs in CI.
- Task 2 (`tests/test_detect_track.py`): track-id-string format with `<class>-<id>` prefix, sub-confidence detections dropped, out-of-range class index raises `ValueError("Unknown class index 99, expected 0..8")`, build-time `model.names != classes` mismatch raises `ValueError`.
- Task 2 (`tests/test_compose.py`): daemon constructed with the 9-class counter, kwarg pass-through to `detect_factory`, factory `ValueError` propagates without swallowing, `DaemonConfig.from_yaml` reads the new NCNN fields.
- Task 3 (`tests/test_run_sensor.py`): `--help` exits 0 with both flags, `--dry-run` composes via `compose()` and skips `daemon.start()`, missing `--config` exits 2 with a logged error (not a traceback), full-run path invokes `daemon.start()` exactly once.

## EDGE-01 / EDGE-02 status

- **EDGE-01** (Pi runs fine-tuned 9-class CAMINAv1 NCNN model, all 9 classes flow through tracker + counter): code COMPLETE; runtime smoke pending plan 01-02 30-min Pi benchmark.
- **EDGE-02** (picamera2 RGB888 direct capture, no cv2.VideoCapture): code COMPLETE; grep-enforced (`grep -cE "cv2\.VideoCapture|cv2\.cvtColor" src/camina/service/camera.py` returns 0).

## Deviations from plan

### 1. [Rule 1 - Bug] Tracker class is `Sort`, not `Tracker`

**Found during:** Task 2.

**Issue:** The plan's `<interfaces>` block (lines 139-144 of 01-01-PLAN.md) sketched a hypothetical
```
class Tracker:
    def update(self, detections: list[Detection]) -> list[TrackedObject]: ...
```
but `src/camina/core/tracker.py` actually exports `Sort` (242 lines, custom Kalman + Hungarian via filterpy + scipy) which takes `np.ndarray of shape (N, 5)` and returns `np.ndarray of shape (M, 5)` rows of `[x1, y1, x2, y2, id]`. There is no `Tracker` class and no `Detection` dataclass.

**Fix:** Wired the existing `Sort` directly per the plan's "reuse, do not reimplement" directive. Kept track-ids class-scoped by instantiating one `Sort` per class (9 trackers in a `dict[int, Sort]`) and prefixing the emitted track-id string with the class name (`"car-7"`) so `WindowedCounter`'s set-based dedupe never collides cross-class.

**Files modified:** `src/camina/service/detect_track.py` (Task 2 commit `8f265f4`).

### 2. [Rule 3 - Blocking] `filterpy` not installed in the dev env

**Found during:** Task 2 (first run of `tests/test_compose.py` failed with `ModuleNotFoundError: No module named 'filterpy'`).

**Issue:** `filterpy==1.4.5` is listed in `requirements.txt` but was not present in the local Python environment. Without it, `from src.camina.core.tracker import Sort` (and therefore the new `detect_track.py`) cannot import.

**Fix:** Installed via `pip install filterpy`. Added a note here so the next contributor knows: if pytest fails on `filterpy` after a fresh clone, run `pip install -r requirements.txt` (or `uv pip install filterpy` once a `pyproject.toml` lands).

**No code change.** No deviation from plan content.

### 3. [Rule 3 - Blocking] `src/utils/__init__.py` missing

**Found during:** Task 1 — the plan's verify line `uv run python -m src.utils.export_ncnn --help` requires `src.utils` to be a discoverable package.

**Issue:** `src/utils/` had no `__init__.py`. While Python 3.10's implicit namespace packages would normally work, having an explicit marker is more reliable across invocation modes and makes the documented `__all__` exports unambiguous.

**Fix:** Added `src/utils/__init__.py` with a module docstring explaining the boundary between `src/utils/` (Pi-edge tools) and `src/camina/utils/` (daemon runtime helpers).

**Files added:** `src/utils/__init__.py` (Task 1 commit `7019c67`).

### 4. [Plan ambiguity] `docs/sensor_deployment.md` Troubleshooting section moved to unnumbered appendix

**Found during:** Task 3.

**Issue:** Plan 01-01 owns §6 (NCNN export) and §7 (daemon invocation). The original `docs/sensor_deployment.md` had `## 7. Troubleshooting` — moving daemon invocation into §7 would push Troubleshooting to §8, which the plan-checker (`PLAN-CHECK.md` lines 113-116) explicitly assigns to plan 01-02 (benchmark §8/§9/§9b).

**Fix:** Renamed `## 7. Troubleshooting` to `## Troubleshooting (appendix)` (unnumbered, sits at the end of the doc). Plans 01-02 / 01-03 / 01-04 can now append §8 / §9 / §9b / §10 / §11 without renumbering. Added two new troubleshooting rows for the macOS dev-host case and the class-mismatch case discovered during Task 3 smoke.

**Files modified:** `docs/sensor_deployment.md` (Task 3 commit `9dcf793`).

### 5. [Pre-existing data issue, NOT a code blocker] On-disk NCNN model is the wrong taxonomy

**Found during:** Task 3 end-to-end smoke (`uv run python scripts/run_sensor.py --config /tmp/sensor_local.yaml --dry-run`).

**Issue:** Both `models/20250629_warmup_best.pt` and `models/20250629_warmup_best_ncnn_model/` ship the 6-class COCO-style taxonomy `['bus', 'car', 'cyclist', 'motorcycle', 'person', 'truck']`, not the 9-class CAMINAv1 taxonomy in `configs/sensor.yaml` (`['person', 'cyclist', 'car', 'e-scooter', 'SUV', 'motorcyclist', 'bus', 'delivery_van', 'truck']`).

**Why this is NOT a Plan 01-01 blocker:** The plan's must_haves are about *code* wiring, and the class-name guard from Task 2 caught the mismatch loudly via `ValueError` — exactly the failure mode it was designed for. All 17 plan tests pass with mocked YOLO, so CI does not depend on the on-disk artefact. Re-training / re-exporting CAMINAv1 with the proper 9-class taxonomy is operational scope owned by `custom_model_train/`, not edge-agent scope.

**What needs to happen before plan 01-02's 30-min Pi benchmark can run:** A re-trained `20250629_warmup_best.pt` with the 9-class taxonomy must be produced (or a different `.pt` pointed at via `configs/sensor.yaml::ncnn_model_path`), then `src/utils/export_ncnn.py` re-run with `--force` to regenerate the NCNN directory.

**No code change in this plan.** Logged here so plan 01-02's executor sees it.

## Authentication gates

None encountered. The daemon's HttpClient uses a Bearer token from the YAML config and never prompts interactively.

## Mac vs Pi dev path

- **Mac dev host:** `picamera2` is unavailable (libcamera is Pi-only). Use `--dry-run` to verify wiring without capturing frames; for inference smoke against a video file, inject a custom `camera_factory` via `compose(...)` (plan 01-02 lands this pattern in `bench_sensor.py`). All 17 new tests use mocked YOLO + in-memory frame generators, so CI runs without picamera2 or Ultralytics inference.
- **Pi production:** systemd unit at `deploy/systemd/camina-sensor.service` invokes `python -m src.camina.service.sensor_daemon` (unchanged); the un-stubbed `main()` now delegates to the same `compose()` factory so behaviour is identical to `scripts/run_sensor.py`.

## Carry-forwards into plan 01-02

1. **Re-export CAMINAv1 NCNN model** with the proper 9-class taxonomy before any 30-min benchmark. `models/20250629_warmup_best{.pt,_ncnn_model}` currently ship a stale 6-class artefact (see Deviation 5).
2. **`bench_sensor.py`** should use `compose(..., camera_factory=video_file_source)` for Mac development and `compose(..., camera_factory=picamera2_frame_source)` (default) on Pi.
3. **`filterpy`** must be installed in the bench env (already in `requirements.txt`).
4. **No production code touches the heavy import surface at module load time** — both `picamera2` and `ultralytics` are imported only inside the camera/detect closures, so plan 01-02 can keep importing `compose` without paying the YOLO cost when it's not exercising real models.

## Self-Check: PASSED

Verified all 9 created files exist on disk:
- `scripts/run_sensor.py` -> FOUND
- `src/camina/service/camera.py` -> FOUND
- `src/camina/service/detect_track.py` -> FOUND
- `src/camina/service/compose.py` -> FOUND
- `src/utils/__init__.py` -> FOUND
- `tests/test_export_ncnn.py` -> FOUND
- `tests/test_detect_track.py` -> FOUND
- `tests/test_compose.py` -> FOUND
- `tests/test_run_sensor.py` -> FOUND

Verified all 3 commits exist in `git log`:
- `7019c67` -> FOUND
- `8f265f4` -> FOUND
- `9dcf793` -> FOUND

All 5 must_have truths from the plan: PASS (with Deviation 5 noted as data-issue, not code-issue).
