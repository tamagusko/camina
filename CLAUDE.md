# CLAUDE.md

CAMINA is a privacy-first traffic sensor. A Raspberry Pi 5 counts nine road-user classes with a
YOLO11n NCNN model and publishes only counts, in 15-minute windows, to a Next.js map of Dublin
streets. Research prototype, UCD Spatial Dynamics Lab; not funded; no unit on a street yet.

## Status and plan

- `.planning/STATE.md` — current stage, blockers, next action. Trust it over chat; offer to update it.
- `.planning/PLAN.md` — stages S1–S14. A stage is done only when its done-test has passed and the
  evidence is committed (measurements in `docs/benchmarks/`).
- `.planning/old/` and `.planning/audit-2026-09-15/` — history. Read, don't edit.

## Commands

```bash
# Edge (Python 3.10+)
uv venv && uv pip install -r requirements.txt          # dev: tests, training, export, viewer
.venv/bin/python -m pytest                              # all edge tests
.venv/bin/ruff check . && .venv/bin/ruff format .      # PEP 8 (config in pyproject.toml)
.venv/bin/python -m camina --config configs/sensor.yaml --dry-run   # the sensor entry point
scripts/view_detections.py --video videos/test.mov --out /tmp/o.mp4 --screenline 0.65 0.15 0.65 0.72

# Pi runtime profile — what the device installs (docs/raspberry_pi_5.md)
pip install --no-deps -r requirements-pi.txt

# Dashboard (Node 20.11+, pnpm)
scripts/run_dashboard.sh                                # mock mode → http://localhost:3000/dublin
cd dashboard && pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

`pnpm test` needs the mock fixtures (`python3 scripts/generate_mock_dublin.py`; the run script
makes them) and `CAMINA_DATA_SOURCE` unset — a test checks the production fail-closed default.

## Layout

| Path | What |
|---|---|
| `camina/core/` | `tracker.py` (SORT, one tracker for all classes, majority-vote class), `counting.py` (count gate: screenline or movement), `counter.py` (15-min windows, daily totals) |
| `camina/io/` | HTTPS publisher, offline buffer (SQLite outbox), config poller, payload schemas |
| `camina/service/` | Daemon (`sensor_daemon.py`), `compose.py`, `detect_track.py`, `ncnn_detector.py`; entry point `camina/__main__.py` |
| `training/` | Dataset, training, NCNN export (`python -m training.<tool>`); may import Ultralytics/PyTorch |
| `models/` | CAMINAv1 NCNN, FP32 and FP16; `PROVENANCE.md` in each folder |
| `configs/` | `classes.yaml` (class IDs), `class_mapping.yaml` (label aliases), `sensor.yaml` (per device) |
| `videos/` | Test videos for `scripts/view_detections.py` |
| `dashboard/` | Next.js 16, MapLibre 6, Drizzle + Neon, Auth.js |
| `deploy/systemd/` | Sensor service unit |

## Rules that must hold

- **Privacy:** counts only, never frames. Public UI and API never expose sensor locations. Counts
  and speeds below 5 are suppressed (k_min = 5). Keep `dashboard/tests/unit/privacy-regression.test.ts` green.
- **Class IDs are a wire contract.** Never reorder `configs/classes.yaml`. The model's own class
  order is mapped by name through `configs/class_mapping.yaml`.
- **The daemon must not import PyTorch or Ultralytics** (`tests/test_pi_runtime.py`).
- **`imgsz` is 640** and must equal the NCNN export's `metadata.yaml`; a mismatch gives garbage boxes.
- **`NEXT_PUBLIC_CAMINA_DEV_ADMIN` never ships to production** (guard in `dashboard/next.config.mjs`).
- **Free tiers only** (Vercel Hobby, Neon free). Dublin only.

## Gotchas

- Ultralytics recognises an NCNN model only by a `_ncnn_model` directory suffix.
- NCNN export: only pnnx **20250924** is validated. The pnnx Ultralytics bundles builds models that
  segfault; every export runs the model once and fails if it crashes.
- `ncnn.Mat(array)` does not own the buffer — keep the NumPy array alive through the forward pass.
- MapLibre 6 cannot find its worker once bundled: `dashboard/scripts/copy-maplibre-worker.mjs`
  runs before `dev` and `build`. Don't remove it.
- Basemap is OpenFreeMap (no key). Carto watermarks keyless tiles — don't reintroduce it.
- React Strict Mode is off on purpose (MapLibre canvas sizing race).
- `next dev` generates `dashboard/AGENTS.md` and `dashboard/CLAUDE.md`; don't hand-edit them.

## Git

- Conventional Commits; merge commits, no squash; merged branches auto-delete.
- `main` stable (PRs from `dev` or `hotfix/*` only) · `dev` integration (branch from it, PR into
  it) · `TRA2026` frozen paper snapshot. `dev_expanded_dataset` holds unaudited data: never merge
  it until it is audited. Details in `CONTRIBUTING.md`.

## Code

- Python: type hints, `logger = logging.getLogger(__name__)` (no `print`), tests first.
- TypeScript: strict; zod at API boundaries; Drizzle for the database.
- Never commit `.env*`, tokens or keys. `AUTH_SECRET` was rotated in April 2026 — never reuse the old one.
- Licence: code MIT; models AGPL-3.0 (trained with Ultralytics).
