# Codebase Structure

**Analysis Date:** 2026-04-23

## Directory Layout

```
camina/
├── main.py                            # Legacy dev entry point (ModalShareCounterApp)
├── CLAUDE.md                          # Behavioral guidelines for Claude instances
├── DESIGN.md                          # Uber-inspired monochrome design system
├── TODO.md                            # Live status for Plan 01 + Plan 02
├── README.md                          # Project overview
├── LICENSE
├── environment.yml                    # Conda environment
├── requirements.txt                   # Pip requirements (edge agent)
├── requirements_calibration.txt       # Extra deps for calibration tooling
├── yolo11n.pt                         # Base YOLO11n weights (tracked at repo root — large)
├── yolo11n.torchscript                # TorchScript export of base model
│
├── .planning/                         # Planning / GSD outputs (codebase maps etc.)
│   └── codebase/
├── .claude/                           # Claude Code per-dev runtime state (gitignored)
├── .playwright-mcp/                   # Playwright MCP runtime state (gitignored)
├── .pytest_cache/                     # Pytest cache (gitignored)
│
├── configs/                           # YAML configuration for the Python side
│   ├── main_config.yaml               # Legacy app configuration
│   ├── sensor.yaml                    # Plan 01 edge-agent start-up config template
│   └── classes.yaml                   # Integer class ID → label registry
│
├── custom_model_train/                # Offline CAMINAv1 training workspace
│   ├── run_camina_pipeline.py         # End-to-end training pipeline entry
│   ├── pipeline_config.yaml
│   ├── run_tests.sh
│   ├── TESTING_GUIDE.md, PROMPT.md, data.md, README.md, README_bkp_cyclist.md
│   ├── scripts/                       # Labeling + training + comparison + deployment
│   ├── all_camina_classes/            # Class definitions for the full CAMINA taxonomy
│   ├── pipeline_results/
│   ├── test_images/
│   ├── test_video.mp4
│   ├── yolo11n.pt
│   └── SDL fine-tuned_v3-cyclist_cleaned.zip
│
├── dashboard/                         # Next.js 16 Vercel dashboard (Plan 02)
│   ├── package.json, pnpm-lock.yaml
│   ├── next.config.mjs, tsconfig.json, postcss.config.mjs, tailwind.config.ts
│   ├── proxy.ts                       # Next.js 16 network-boundary proxy (renamed middleware)
│   ├── vercel.ts                      # Typed Vercel config: headers, redirects, crons
│   ├── drizzle.config.ts, playwright.config.ts, vitest.config.ts
│   ├── next-env.d.ts, README.md
│   ├── .claude/
│   ├── drizzle/
│   │   ├── schema.ts                  # Drizzle ORM tables
│   │   └── migrations/0000_init.sql   # Raw SQL with PostGIS + indexes + views
│   ├── public/
│   │   └── tiles/                     # Carto Positron basemap (gitignored, ~60 MB)
│   ├── scripts/                       # Dashboard helper scripts (Node .mjs)
│   │   ├── download-dublin-tiles.mjs
│   │   ├── inspect-map.mjs
│   │   ├── open-preview.mjs
│   │   └── camina-preview.png
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   ├── components/                # UI components by concern
│   │   ├── lib/                       # Server-safe domain + data-access layer
│   │   └── styles/
│   │       └── globals.css
│   └── tests/
│       ├── e2e/
│       │   └── public-map.spec.ts
│       └── unit/
│           ├── privacy-regression.test.ts
│           └── schemas.test.ts
│
├── data/                              # Runtime + mock data (gitignored)
│   └── mock/
│       └── dublin/                    # JSON fixtures consumed by the mock repo
│
├── deploy/                            # Deployment artefacts
│   └── systemd/
│       └── camina-sensor.service      # RPi5 systemd unit for SensorDaemon
│
├── docs/                              # Protocol + deployment docs
│   ├── PROTOCOL.md                    # Wire protocol between sensor and dashboard
│   ├── RECONCILIATION.md              # Daily reconciliation policy
│   ├── sensor_deployment.md           # RPi5 bring-up runbook
│   ├── CALIBRATION_SETUP.md
│   ├── CODE_STYLE.md
│   ├── EQUIPMENTS.md
│   ├── MODELS.md
│   ├── BUGS.md
│   └── TODO.md                        # Scoped docs-only TODO
│
├── img/                               # Static image assets
│   └── wrong_label/                   # Misclassified examples kept for review
│
├── model/                             # Legacy checkpoint slot
├── models/                            # Shipped model artefacts
│   ├── 20250629_warmup_best.pt
│   ├── 20250629_warmup_best.torchscript
│   ├── 20250629_warmup_best_ncnn_model/      # CAMINAv1 NCNN (used on RPi5)
│   ├── yolo11n.pt
│   ├── yolo11n_ncnn_model/
│   └── yolov8n.pt
│
├── plan/                              # Canonical plan docs (read first)
│   ├── 01-windowed-counter-and-ingest.md
│   └── 02-dashboard-vercel.md
│
├── paper/                             # Paper drafts (empty directory; reserved)
│
├── runs/                              # YOLO training runs (gitignored content)
│
├── scripts/                           # Python helper scripts
│   ├── __init__.py
│   ├── calibrate_camera.py            # Manual camera calibration
│   ├── generate_mock_dublin.py        # Seeds dashboard mock fixtures
│   ├── data_processing/               # Dataset prep + label tooling
│   └── train/                         # YOLO fine-tuning scripts + YAMLs
│
├── src/                               # Python source tree
│   ├── camina/                        # Production package
│   ├── dev/                           # Throwaway dev scripts (not importable as a pkg)
│   ├── utils/                         # Standalone utilities (Pi display, NCNN export)
│   └── speed_estimation.py            # Speed estimation module
│
├── tests/                             # Pytest suites for the edge agent
│   ├── __init__.py
│   ├── test_config_poller.py
│   ├── test_daily_accumulator.py
│   ├── test_display.pi
│   ├── test_https_publisher.py
│   ├── test_offline_buffer.py
│   ├── test_sensor_daemon.py
│   ├── test_windowed_counter.py
│   └── test.mov
│
└── bkp/                               # Archived misc (gitignored content)
    └── presentation_ai_gen.pdf
```

## Directory Purposes

**`main.py`:**
- Purpose: the one-file launcher for the legacy dev app.
- Loads `configs/main_config.yaml`, constructs `ModalShareCounterApp`, calls `.run()`.

**`configs/`:**
- Purpose: YAML configuration for the Python side (both legacy and Plan 01 daemon).
- Contains: `main_config.yaml` (legacy app), `sensor.yaml` (daemon start-up), `classes.yaml` (shared class registry).

**`src/`:**
- Purpose: all Python source.
- Contains: `camina/` (production package), `dev/` (dev scripts), `utils/` (Pi-specific helpers), plus a top-level `speed_estimation.py`.

**`src/camina/`:**
- Purpose: the importable `camina` package.
- Key files:
  - `src/camina/app.py` — legacy `ModalShareCounterApp` + `VideoCapture` + `Detector` + `ObjectTracker` + `DataLogger` + `Display` + `CalibrationMonitor`.
  - `src/camina/core/counter.py` — `WindowedCounter`, `DailyAccumulator`, `WindowSnapshot`, `DailySnapshot` (323 lines).
  - `src/camina/core/tracker.py` — SORT tracker (242 lines).
  - `src/camina/io/http_client.py` — `HttpClient` (158 lines).
  - `src/camina/io/https_publisher.py` — `HttpsPublisher` (170 lines).
  - `src/camina/io/offline_buffer.py` — WAL-SQLite FIFO outbox (193 lines).
  - `src/camina/io/config_poller.py` — version-gated hot-reload (154 lines).
  - `src/camina/io/schemas.py` — dataclass payloads (141 lines).
  - `src/camina/service/sensor_daemon.py` — `DaemonConfig` + `SensorDaemon` orchestrator.
  - `src/camina/utils/config.py` — `load_config()`, `load_classes()`.
  - `src/camina/utils/display.py` — e-paper / OLED display factory.
  - `src/camina/utils/calibration.py` — `DepthCalibrator`.

**`src/dev/`:**
- Purpose: dev-only scripts that are not part of the importable package.
- Contains: `camera_position_check.py`, `lowlight_counter.py`, `motion_detector.py`, `plugged_counter.py`.

**`src/utils/`:**
- Purpose: standalone utilities at the Pi boundary.
- Contains: `epaper_display.py`, `export_ncnn.py`, `infer_image.py`, `oled_display.py`.

**`scripts/`:**
- Purpose: command-line entry points for training, data prep, calibration, mock generation.
- Top-level: `calibrate_camera.py`, `generate_mock_dublin.py`.
- `scripts/data_processing/`: `analyze_data.py`, `coco_to_cyclist.py`, `extract_cyclist_images.py`, `remove_class.py`, `rename_data.py`, `validate_yolo_labels.py`, `view_bbox.py`.
- `scripts/train/`: `fine_tune.py`, `train_param_warmup.yaml`, `train_param_finetune.yaml`.

**`custom_model_train/`:**
- Purpose: offline ML workspace for CAMINAv1 training + evaluation.
- Key scripts: `custom_model_train/scripts/train_yolo11n.py`, `custom_model_train/scripts/convert_sdl_to_yolo11.py`, `custom_model_train/scripts/dinov3_semi_auto_labeling.py`, `custom_model_train/scripts/sam2_clip_auto_labeling.py`, `custom_model_train/scripts/evaluation_logging_system.py`, `custom_model_train/scripts/model_comparison_framework.py`, `custom_model_train/scripts/rpi5_deployment_optimizer.py`.
- Top-level: `run_camina_pipeline.py` (pipeline runner), `pipeline_config.yaml`, `run_tests.sh`.

**`deploy/`:**
- Purpose: deployment artefacts (non-code).
- Contains: `deploy/systemd/camina-sensor.service` — runs `python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml` as the `camina` system user.

**`dashboard/`:**
- Purpose: Next.js 16 dashboard (Plan 02), independent `pnpm` workspace.
- Contains: App Router under `dashboard/src/app/`, UI components under `dashboard/src/components/`, data-access/auth/types under `dashboard/src/lib/`, Drizzle schema + SQL migration under `dashboard/drizzle/`, public assets (`dashboard/public/`), helper scripts (`dashboard/scripts/`), tests (`dashboard/tests/`).

**`dashboard/src/app/`:**
- Purpose: Next.js App Router.
- Sub-tree:
  - `page.tsx` — redirects `/` → `/dublin`.
  - `layout.tsx` — root layout with metadata + viewport.
  - `(auth)/sign-in/page.tsx`, `(auth)/sign-in/error/page.tsx` — auth route group.
  - `[city]/page.tsx`, `[city]/CityMapShell.tsx`, `[city]/street/[slug]/page.tsx` — public map + street detail.
  - `admin/layout.tsx` (gates via `requireAdmin()`), `admin/page.tsx`, `admin/sensors/page.tsx`, `admin/streets/page.tsx`, `admin/members/page.tsx`, `admin/events/page.tsx`, `admin/audit/page.tsx`.
  - `api/auth/[...nextauth]/route.ts` — Auth.js v5 handler.
  - `api/health/route.ts`, `api/metrics/route.ts`.
  - `api/streets/route.ts`, `api/streets/[id]/route.ts`, `api/streets/[id]/readings/route.ts`.
  - `api/ingest/sensors/[id]/{counts,daily,heartbeat,config}/route.ts`.
  - `api/admin/streets/[id]/info/route.ts`.
  - `api/cron/{refresh-aggregates,detect-silent,reconcile-daily}/route.ts`.

**`dashboard/src/components/`:**
- Purpose: React components by concern.
- Sub-tree:
  - `map/` — `StreetMap.tsx` (MapLibre wrapper), `MetricToggle.tsx`, `ClassFilter.tsx`, `TimeWindowPicker.tsx`, `ColourLegend.tsx`, `useMapHash.ts`, `useMapQuery.ts`.
  - `panels/` — `StreetSidePanel.tsx` (click-to-drill side sheet with admin strip).
  - `charts/` — `StreetTimeSeries.tsx` (Recharts time-series for the street detail page).
  - `layout/` — `MockDataPill.tsx` (fixed pill indicating mock mode).
  - `ui/` — `pill.tsx` (shared pill primitive).

**`dashboard/src/lib/`:**
- Purpose: server-safe domain/data/utility layer (most files opt into `"server-only"`).
- Files:
  - `auth.ts` — Auth.js v5 config + `requireAdmin()` helper.
  - `cache-tags.ts` — shared cache-tag identifiers.
  - `cn.ts` — `clsx` + `tailwind-merge` wrapper.
  - `cron-auth.ts` — cron-route shared-secret verifier.
  - `data-source.ts` — `CAMINA_DATA_SOURCE` env gate (`isMock` / `isLive`).
  - `db.ts` — lazy `drizzle(postgres(...))` singleton.
  - `geo.ts` — colour ramps (`VIRIDIS_5`, `CIVIDIS_5`), `CITY_VIEWS`, `unionBbox`, `rampExpression`.
  - `ingest-auth.ts` — per-device Bearer verification for ingest routes.
  - `mock-loader.ts` — reads `data/mock/{city}/*.json` fixtures with per-process cache.
  - `repo/` — `index.ts` (selects impl), `types.ts` (`StreetsRepo` interface), `streets-mock.ts`, `streets-live.ts`.
  - `schemas.ts` — zod schemas for ingest payloads + query params (mirrors `src/camina/io/schemas.py`).
  - `types.ts` — `Metric`, `TimeWindow`, `RoadUserClass`, `StreetSummary`, `StreetReading`, `MetricValue`, `StreetAdminInfo`.

**`dashboard/drizzle/`:**
- Purpose: persistence schema.
- Files: `schema.ts` (Drizzle ORM) + `migrations/0000_init.sql` (raw SQL with PostGIS, BRIN indexes, materialized views, admin tables).

**`dashboard/public/`:**
- Purpose: static assets served as-is by Next.js.
- Contains: `tiles/` (Carto Positron PNG tileset, gitignored via `dashboard/public/tiles/`, populated on first run by `pnpm exec node scripts/download-dublin-tiles.mjs`).

**`dashboard/scripts/`:**
- Purpose: Node-side dev helpers. Not shipped in the build.
- Files: `download-dublin-tiles.mjs`, `inspect-map.mjs` (headless Playwright screenshot), `open-preview.mjs`, plus `camina-preview.png` (committed example screenshot).

**`dashboard/tests/`:**
- Purpose: dashboard test suites.
- `tests/unit/` — Vitest: `privacy-regression.test.ts`, `schemas.test.ts`.
- `tests/e2e/` — Playwright: `public-map.spec.ts`.

**`data/`:**
- Purpose: runtime-generated data + shared mock fixtures.
- `data/mock/dublin/` — JSON fixtures: `meta.json`, `sensors.json`, `streets.json`, `streets.geojson`, `sensor_street_coverage.json`, `sensor_readings.json`, `sensor_daily_totals.json`, `sensor_heartbeats.json`, `README.md`.
- Generated: on-device legacy logs (`data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log`) and reference frames (`data/img/reference_frame.jpg`) are written here at runtime.

**`docs/`:**
- Purpose: protocol + deployment + reconciliation + code style docs.
- Files: `PROTOCOL.md`, `RECONCILIATION.md`, `sensor_deployment.md`, `CALIBRATION_SETUP.md`, `CODE_STYLE.md`, `EQUIPMENTS.md`, `MODELS.md`, `BUGS.md`, `TODO.md`.

**`plan/`:**
- Purpose: the two canonical implementation plans.
- Files: `plan/01-windowed-counter-and-ingest.md` (edge agent), `plan/02-dashboard-vercel.md` (dashboard).

**`tests/`:**
- Purpose: pytest suites for the edge agent.
- Files: `test_config_poller.py`, `test_daily_accumulator.py`, `test_https_publisher.py`, `test_offline_buffer.py`, `test_sensor_daemon.py`, `test_windowed_counter.py`, `test_display.pi` (Pi-specific, note the `.pi` extension), `test.mov` (fixture video).

**`models/`:**
- Purpose: shipped model artefacts.
- Key files: `models/20250629_warmup_best.pt` (CAMINAv1 PyTorch), `models/20250629_warmup_best.torchscript`, `models/20250629_warmup_best_ncnn_model/` (production NCNN), `models/yolo11n.pt`, `models/yolo11n_ncnn_model/`, `models/yolov8n.pt`.

**`model/`:**
- Purpose: legacy single-model checkpoint slot. Mostly superseded by `models/`.

**`runs/`:**
- Purpose: YOLO training run outputs (content is gitignored).

**`img/`:**
- Purpose: static image assets.
- Contains: `img/wrong_label/` (misclassified examples retained for review).

**`paper/`:**
- Purpose: reserved for paper drafts (currently empty).

**`bkp/`:**
- Purpose: archived misc (content gitignored). Currently contains `presentation_ai_gen.pdf`.

## Key File Locations

**Entry Points:**
- `main.py`: legacy dev app launcher.
- `src/camina/service/sensor_daemon.py::main`: production edge-agent CLI entry (systemd-invoked).
- `dashboard/src/app/page.tsx`: dashboard root (redirects to `/dublin`).
- `dashboard/src/app/[city]/page.tsx`: public map page.
- `dashboard/src/app/admin/layout.tsx`: admin console root layout + auth gate.

**Configuration:**
- `configs/main_config.yaml`: legacy app.
- `configs/sensor.yaml`: edge-agent daemon.
- `configs/classes.yaml`: shared class registry.
- `dashboard/next.config.mjs`, `dashboard/tailwind.config.ts`, `dashboard/postcss.config.mjs`, `dashboard/tsconfig.json`.
- `dashboard/vercel.ts`: headers, redirects, crons.
- `dashboard/proxy.ts`: edge-level security headers.
- `dashboard/drizzle.config.ts`: Drizzle CLI config.
- `dashboard/playwright.config.ts`, `dashboard/vitest.config.ts`: test configs.

**Core Logic:**
- `src/camina/core/counter.py`: counting + daily aggregation.
- `src/camina/io/offline_buffer.py`: durable outbox.
- `src/camina/service/sensor_daemon.py`: orchestrator.
- `dashboard/src/lib/repo/streets-mock.ts`: reference implementation of the repo contract.
- `dashboard/src/lib/geo.ts`: colour ramp + MapLibre paint expression.

**Testing:**
- `tests/`: edge-agent pytest.
- `dashboard/tests/unit/`: Vitest.
- `dashboard/tests/e2e/`: Playwright.

**Authoritative reference docs (read first):**
- `plan/01-windowed-counter-and-ingest.md`, `plan/02-dashboard-vercel.md`.
- `DESIGN.md`, `TODO.md`, `README.md`, `CLAUDE.md`.
- `docs/PROTOCOL.md`, `docs/RECONCILIATION.md`, `docs/sensor_deployment.md`, `docs/CODE_STYLE.md`.

## Naming Conventions

**Python files:**
- `snake_case.py` everywhere (`sensor_daemon.py`, `offline_buffer.py`, `config_poller.py`).
- Pytest modules: `test_<module>.py` (`test_windowed_counter.py`).
- One Pi-specific test uses an unusual `.pi` extension: `tests/test_display.pi` (not a regular pytest file).

**Python classes / functions:**
- `PascalCase` for classes (`WindowedCounter`, `HttpsPublisher`, `SensorDaemon`, `DaemonConfig`, `ModalShareCounterApp`).
- `snake_case` for functions and methods (`load_config`, `load_classes`, `_read_cpu_temp`, `_on_window_snapshot`).
- Leading underscore for internal methods (`_main_loop`, `_catch_up_daily`, `_send_heartbeat`).
- Constants: `UPPER_SNAKE_CASE` when module-level.

**TypeScript files:**
- `camelCase.ts` for modules (`auth.ts`, `data-source.ts`, `mock-loader.ts`, `ingest-auth.ts`, `cron-auth.ts`, `cache-tags.ts`).
- `PascalCase.tsx` for React component files (`StreetMap.tsx`, `StreetSidePanel.tsx`, `CityMapShell.tsx`, `MetricToggle.tsx`, `ClassFilter.tsx`, `TimeWindowPicker.tsx`, `ColourLegend.tsx`, `MockDataPill.tsx`, `StreetTimeSeries.tsx`).
- Hook files: camelCase with `use` prefix (`useMapHash.ts`, `useMapQuery.ts`).
- `route.ts` for API endpoints (App Router convention); `page.tsx` / `layout.tsx` for routes.
- Lowercase primitives where they are intended to be used like a function (`cn.ts`, `pill.tsx`).
- Kebab-case route segments (`detect-silent`, `refresh-aggregates`, `reconcile-daily`, `sign-in`).

**TypeScript types / values:**
- `PascalCase` for types and interfaces (`StreetsRepo`, `StreetSummary`, `MetricValue`, `StreetAdminInfo`, `DataSource`).
- `camelCase` for functions and exports (`streetsRepo`, `mockStreetsRepo`, `liveStreetsRepo`, `requireAdmin`, `verifyIngestToken`).
- `UPPER_SNAKE_CASE` for module-level constants (`ROAD_USER_CLASSES`, `VIRIDIS_5`, `CIVIDIS_5`, `CITY_VIEWS`).
- Env vars prefixed `CAMINA_` or `NEXT_PUBLIC_CAMINA_`.

**Directories:**
- Python: `snake_case` (`data_processing`, `custom_model_train`, `sensor_street_coverage`).
- Next.js routes: kebab-case (`sign-in`, `detect-silent`, `reconcile-daily`, `refresh-aggregates`).
- Next.js special folders: `[param]`, `[...catchall]`, `(group)` per App Router convention.
- Next.js component directories: lowercase by concern (`map`, `panels`, `charts`, `layout`, `ui`).

## Where to Add New Code

**New Python module (edge agent):**
- Primary code: `src/camina/<layer>/<name>.py` where `<layer>` is `core` (pure logic), `io` (anything that does network/disk I/O), `service` (orchestrators), or `utils` (small helpers).
- Export via the `__init__.py` of the layer if other layers should import it.
- Tests: `tests/test_<name>.py` mirroring pytest style of existing suites.

**New legacy-app feature:**
- Extend `src/camina/app.py` or factor into `src/camina/utils/` or `src/camina/core/`.
- Keep the legacy app separate from the Plan 01 daemon — they intentionally do not share a runtime.

**New training / data script:**
- Offline experimentation: `custom_model_train/scripts/<name>.py`.
- Repeatable CLI utility: `scripts/train/<name>.py` or `scripts/data_processing/<name>.py` with an entry in the matching YAML.

**New Next.js public route:**
- Page: `dashboard/src/app/<segment>/page.tsx` (server component by default; add `"use client"` only when needed).
- Keep interactive pieces in `dashboard/src/components/<concern>/<Name>.tsx` and have the page import them (mirrors the `page.tsx` → `CityMapShell` → `StreetMap`/`StreetSidePanel` structure).

**New API route:**
- File: `dashboard/src/app/api/<segment>/route.ts` exporting named `GET`/`POST`/`PATCH`/`DELETE` handlers.
- Ingest endpoints must call `verifyIngestToken(request, sensorId)` from `@/lib/ingest-auth` and validate with a zod schema from `@/lib/schemas`.
- Admin endpoints must call `requireAdmin()` from `@/lib/auth` when not in mock mode.
- Cron endpoints must call the verifier in `@/lib/cron-auth` and be registered in `dashboard/vercel.ts::crons`.

**New data-access method:**
- Extend the `StreetsRepo` interface in `dashboard/src/lib/repo/types.ts` first.
- Implement in both `dashboard/src/lib/repo/streets-mock.ts` and `dashboard/src/lib/repo/streets-live.ts` (even if live throws for now).
- Consume via `import { streetsRepo } from "@/lib/repo"` — never reach directly into `mock-loader.ts` or `db.ts` from a route/component.

**New component:**
- Map-related: `dashboard/src/components/map/`.
- Side panel / sheet: `dashboard/src/components/panels/`.
- Chart: `dashboard/src/components/charts/`.
- Layout chrome: `dashboard/src/components/layout/`.
- Generic primitive: `dashboard/src/components/ui/`.

**New schema column / table:**
- Edit `dashboard/drizzle/schema.ts` (Drizzle ORM) and — when PostGIS/indexes/materialized-views are involved — also edit `dashboard/drizzle/migrations/0000_init.sql` (or add a new migration file alongside it).
- Keep the `sensors.latitude/longitude` and `sensor_id` fields behind the admin-only boundary (`StreetAdminInfo`), never surface them in a public API route.

**New mock fixture:**
- Drop JSON into `data/mock/dublin/<name>.json` (or a new city directory) and add a `load<Name>()` helper in `dashboard/src/lib/mock-loader.ts`.
- Regenerate with `python scripts/generate_mock_dublin.py`.

## Special Directories

**`dashboard/public/tiles/`:**
- Purpose: Carto Positron basemap tileset (~60 MB).
- Generated: Yes — by `dashboard/scripts/download-dublin-tiles.mjs`.
- Committed: No — ignored via `dashboard/public/tiles/` in `.gitignore`.
- Must be populated once on fresh clone before `pnpm dev` renders the map.

**`data/`:**
- Purpose: runtime data (edge-agent logs, reference frames) and mock fixtures.
- Generated: partially — `data/mock/dublin/*.json` is generated by `scripts/generate_mock_dublin.py`; runtime logs written by `DataLogger`.
- Committed: No — `data/` is fully gitignored. The mock fixtures are regenerated locally and re-committed only when the generator changes.

**`runs/`, `bkp/`, `custom_model_train/datasets/`:**
- Purpose: model training outputs, archives, training datasets.
- Committed: No — all gitignored.

**`dashboard/node_modules/`, `dashboard/.next/`, `dashboard/.env.local`:**
- Purpose: pnpm dependency tree, Next.js build artefacts, local dashboard env file.
- Committed: No — gitignored.

**`.claude/`, `.playwright-mcp/`:**
- Purpose: Claude Code / Playwright MCP per-developer runtime state.
- Committed: No — gitignored.

**`.pytest_cache/`, `__pycache__/`, `*.pyc`:**
- Purpose: Python test / bytecode caches.
- Committed: No — gitignored.

---

*Structure analysis: 2026-04-23*
