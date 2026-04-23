# Architecture

**Analysis Date:** 2026-04-23

## Pattern Overview

**Overall:** Hybrid monorepo combining a Python ML/edge-agent codebase with a Next.js 16 Vercel-hosted dashboard.

The repository co-locates three sub-systems that share a single privacy contract (edge-only inference, no image/video upload, only aggregated counts and speeds leave the device):

1. **ML training pipeline** — offline YOLO11 fine-tuning for the custom `CAMINAv1` model (custom classes including `person`, `cyclist`, `car`, `e-scooter`, `SUV`, `motorcyclist`, `bus`, `delivery_van`, `truck`).
2. **Edge sensor agent** — Python daemon running on Raspberry Pi 5 that performs YOLO + SORT detection/tracking, aggregates counts in time windows, and publishes them over HTTPS with an offline WAL-backed outbox (Plan 01).
3. **Vercel dashboard** — Next.js 16 App-Router app (under `dashboard/`) that ingests sensor payloads, serves a public per-street MapLibre map, and exposes an admin console for sensor/street/member management (Plan 02).

**Key Characteristics:**
- Clean split between a research-grade legacy app (`src/camina/app.py` with OpenCV window + local logging) and a headless production daemon (`src/camina/service/sensor_daemon.py`).
- Repository interface pattern in the dashboard lets the same API routes and server components work against either a mock JSON dataset or live Postgres (`dashboard/src/lib/repo/`).
- Privacy boundary is enforced by the type system: `StreetSummary` is public, `StreetAdminInfo` is admin-only and lives behind `requireAdmin()` in live mode (`dashboard/src/lib/types.ts`, `dashboard/src/lib/auth.ts`).
- Edge↔cloud schema contract is mirrored between Python (`src/camina/io/schemas.py`) and TypeScript (`dashboard/src/lib/schemas.ts`), validated with `zod` on the ingest side.
- Status recorded in `TODO.md`: Plan 01 is "all 8 steps merged, 60 unit + integration tests passing"; Plan 02 is scaffolded end-to-end in mock mode, live half (Neon Postgres, Google OAuth, admin CRUD, crons, deploy) still pending.

## Layers

**ML training pipeline (offline):**
- Purpose: produce the `CAMINAv1` NCNN model used by the edge agent.
- Location: `custom_model_train/`, `scripts/train/`, `scripts/data_processing/`, `models/`.
- Contains: dataset prep (`scripts/data_processing/coco_to_cyclist.py`, `scripts/data_processing/extract_cyclist_images.py`), label management (`scripts/data_processing/remove_class.py`, `scripts/data_processing/validate_yolo_labels.py`), YOLO fine-tuning (`scripts/train/fine_tune.py`, `custom_model_train/scripts/train_yolo11n.py`), semi-auto labeling (`custom_model_train/scripts/dinov3_semi_auto_labeling.py`, `custom_model_train/scripts/sam2_clip_auto_labeling.py`), NCNN export for Pi deployment (`src/utils/export_ncnn.py`), model comparison (`custom_model_train/scripts/model_comparison_framework.py`), Pi5 deployment optimizer (`custom_model_train/scripts/rpi5_deployment_optimizer.py`).
- Depends on: Ultralytics, PyTorch, OpenCV.
- Used by: the edge agent, which loads a trained NCNN model at inference time.

**Edge agent — legacy / dev (`src/camina/app.py`):**
- Purpose: desktop-friendly counter with OpenCV window, local log files, on-device e-paper/OLED display. Used for dev ergonomics and field testing.
- Location: `src/camina/app.py`, `src/camina/utils/*`, `src/dev/*`, `src/speed_estimation.py`.
- Contains: `ModalShareCounterApp`, `VideoCapture`, `Detector`, `ObjectTracker`, `DataLogger`, `Display`, `CalibrationMonitor`.
- Depends on: Ultralytics YOLO, OpenCV, the SORT tracker at `src/camina/core/tracker.py`, `src/camina/utils/calibration.py`, `src/camina/utils/display.py`.
- Used by: `main.py` (the repo's CLI entry point).

**Edge agent — production daemon (Plan 01):**
- Purpose: headless RPi5 daemon that never opens a window and never writes local media — it only emits count/speed windows + daily totals + heartbeats over HTTPS.
- Location: `src/camina/service/sensor_daemon.py`, plus the core/I/O it composes.
- Internal sub-layers:
  - `core/`: `src/camina/core/counter.py` (`WindowedCounter`, `DailyAccumulator`, `WindowSnapshot`, `DailySnapshot`), `src/camina/core/tracker.py` (SORT).
  - `io/`: `src/camina/io/http_client.py` (`HttpClient`), `src/camina/io/https_publisher.py` (`HttpsPublisher`), `src/camina/io/offline_buffer.py` (WAL-SQLite FIFO outbox), `src/camina/io/config_poller.py` (version-gated hot-reload), `src/camina/io/schemas.py` (payload dataclasses including `HeartbeatPayload`, `SensorConfig`).
  - `service/`: `SensorDaemon` orchestrator wiring it all together.
- Depends on: `yaml`, `httpx`/`requests` (via `HttpClient`), `sqlite3` (for outbox + state DB), signal handling.
- Used by: `deploy/systemd/camina-sensor.service` which invokes `python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml`.

**Dashboard — presentation (Next.js App Router, RSC):**
- Purpose: serve per-street map and per-street detail page; render admin UI shell.
- Location: `dashboard/src/app/`, `dashboard/src/components/`.
- Contains: public routes (`/`, `/[city]`, `/[city]/street/[slug]`), auth routes (`/(auth)/sign-in`, `/(auth)/sign-in/error`), admin routes (`/admin`, `/admin/sensors`, `/admin/streets`, `/admin/members`, `/admin/events`, `/admin/audit`), components by concern (`components/map/`, `components/panels/`, `components/charts/`, `components/layout/`, `components/ui/`).
- Pattern: server components do data-fetching and auth gating (e.g. `dashboard/src/app/admin/layout.tsx` calls `requireAdmin()` and redirects); client components wrap MapLibre and local UI state (`CityMapShell.tsx`, `StreetMap.tsx`, `StreetSidePanel.tsx`).
- Depends on: the repo layer (`@/lib/repo`), auth (`@/lib/auth`), geo helpers (`@/lib/geo`), types (`@/lib/types`).

**Dashboard — domain / data-access (repository pattern):**
- Purpose: abstract "mock" and "live" data sources behind a single interface, making API routes and server components identical in both modes.
- Location: `dashboard/src/lib/repo/`.
- Key file: `dashboard/src/lib/repo/index.ts` picks `mockStreetsRepo` or `liveStreetsRepo` based on `isMock` from `dashboard/src/lib/data-source.ts` (driven by `CAMINA_DATA_SOURCE` env var).
- Contract: `StreetsRepo` in `dashboard/src/lib/repo/types.ts` with `list`, `get`, `readings`, `latestMetrics`, `adminInfo` methods. Mock impl (`streets-mock.ts`) reads JSON fixtures; live impl (`streets-live.ts`) throws until Neon is wired up.
- Depends on: mock loader (`dashboard/src/lib/mock-loader.ts`) → `../data/mock/{city}/*.json` fixtures, or Drizzle client (`dashboard/src/lib/db.ts`) → Postgres.

**Dashboard — API / ingest / cron:**
- Purpose: HTTP ingest endpoints for the edge agent, public read API for the map, admin-only endpoints, and scheduled cron jobs.
- Location: `dashboard/src/app/api/`.
- Routes:
  - Public read: `api/streets/route.ts`, `api/streets/[id]/route.ts`, `api/streets/[id]/readings/route.ts`, `api/metrics/route.ts`, `api/health/route.ts`.
  - Ingest (per-sensor Bearer, validated by `dashboard/src/lib/ingest-auth.ts` and `dashboard/src/lib/schemas.ts`): `api/ingest/sensors/[id]/counts/route.ts`, `api/ingest/sensors/[id]/daily/route.ts`, `api/ingest/sensors/[id]/heartbeat/route.ts`, `api/ingest/sensors/[id]/config/route.ts`.
  - Admin (gated by `requireAdmin()` from `dashboard/src/lib/auth.ts` in live mode): `api/admin/streets/[id]/info/route.ts`.
  - Auth: `api/auth/[...nextauth]/route.ts` (Auth.js v5, Google SSO only).
  - Cron (gated by `CAMINA_DEV_CRON_SECRET`/`VERCEL_CRON_SECRET` via `dashboard/src/lib/cron-auth.ts`): `api/cron/refresh-aggregates/route.ts` (*/5 min), `api/cron/detect-silent/route.ts` (*/15 min), `api/cron/reconcile-daily/route.ts` (01:00 daily). Schedules declared in `dashboard/vercel.ts`.

**Dashboard — persistence (live, partially wired):**
- Purpose: Neon Postgres + PostGIS for streets (PostGIS multilinestring), sensors, sensor_readings (BRIN-indexed time-series), daily totals, heartbeats, allowlist, audit log.
- Location: `dashboard/drizzle/schema.ts` (Drizzle ORM) + `dashboard/drizzle/migrations/0000_init.sql` (raw SQL for PostGIS + materialized views + partitioning).
- Client: `dashboard/src/lib/db.ts` (lazy singleton `drizzle(postgres(...))`, only constructed when live mode is selected).
- Status: schema committed; `liveStreetsRepo` methods currently throw. DB connection, OAuth, and admin CRUD are the main Plan 02 live-mode gaps (see `TODO.md`).

## Data Flow

**Primary flow — sensor → dashboard:**

1. On a RPi5, `deploy/systemd/camina-sensor.service` launches the daemon with `configs/sensor.yaml` (sensor ID, API base URL, Bearer token, classes, default intervals).
2. `SensorDaemon._main_loop` pulls frames from an injected `frame_source`, runs YOLO + SORT via an injected `detect_and_track`, and feeds (track_id, class_name) pairs to `WindowedCounter.add()`.
3. At window boundaries (default 15 min from `publish_interval_seconds`), `WindowedCounter.maybe_rollover()` returns a `WindowSnapshot` (per-class counts + avg speeds).
4. `SensorDaemon._on_window_snapshot` forwards the snapshot to `DailyAccumulator.add_window()` (SQLite persistence) and to `HttpsPublisher.post_counts()`.
5. `HttpsPublisher` either posts successfully (returning `latest_config_version` which is fed to the `ConfigPoller`) or on failure enqueues the payload into `OfflineBuffer` (WAL-SQLite FIFO outbox, capped by `outbox_max_rows` with drop-oldest).
6. A separate heartbeat thread (`_heartbeat_loop`) posts `HeartbeatPayload` every `heartbeat_interval_seconds` with uptime, CPU temp (best-effort read of `/sys/class/thermal/thermal_zone0/temp`), and current config version.
7. `ConfigPoller` compares versions observed in response headers with the local one; when they differ it GETs the fresh `SensorConfig`, calls `apply(config)` (which re-creates `WindowedCounter` with the new window size), and persists the version.
8. Dashboard receives payloads at `dashboard/src/app/api/ingest/sensors/[id]/{counts,daily,heartbeat,config}/route.ts`. Each verifies Bearer via `verifyIngestToken` and validates with zod; in mock mode it accepts but does not persist; in live mode it would write via Drizzle.
9. On the read side, `/[city]/page.tsx` (server component) calls `streetsRepo.list(city)` and `streetsRepo.latestMetrics({...})` via `Promise.all`, then passes the result to the `CityMapShell` client component.
10. `CityMapShell` renders `StreetMap` (dynamic import, `ssr: false`) and the `StreetSidePanel`. `StreetMap` re-fetches from `/api/metrics` whenever metric/class/window state changes and paints streets with `rampExpression()` (viridis for counts, cividis for speed).
11. When a street is clicked, the `StreetSidePanel` shows totals/per-class breakdown and — if `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` — fetches admin info via `/api/admin/streets/[id]/info/route.ts`.
12. Scheduled crons (`dashboard/vercel.ts`) eventually refresh materialized views (`street_readings_15m`), detect silent sensors (`last_heartbeat < NOW() - 15min`), and run daily reconciliation per `docs/RECONCILIATION.md`.

**State Management:**
- Server: data-source selection (`CAMINA_DATA_SOURCE`) at module init time; Drizzle client as a lazy singleton.
- Dashboard client UI: `useState` for metric/class/window selection inside `StreetMap`, `useMapQuery` hook (`dashboard/src/components/map/useMapQuery.ts`) for `?zoom=&lat=&lon=` URL query state, `useMapHash` (`dashboard/src/components/map/useMapHash.ts`) for shareable deep-links.
- Edge agent: `WindowedCounter` and `DailyAccumulator` keep in-memory aggregates; `OfflineBuffer` and `DailyAccumulator` persist to SQLite at `state_db_path` and `state.outbox.db`.

## Key Abstractions

**`ModalShareCounterApp` (legacy dev app):**
- Purpose: end-to-end on-device counter with UI.
- File: `src/camina/app.py`.
- Pattern: composes `VideoCapture`, `Detector`, `ObjectTracker`, `DataLogger`, `Display`, `CalibrationMonitor`.

**`SensorDaemon` (production edge agent):**
- Purpose: headless orchestrator for Plan 01.
- File: `src/camina/service/sensor_daemon.py`.
- Pattern: injects `frame_source` + `detect_and_track` callables so the module stays importable in CI without heavy OpenCV/Ultralytics deps. Production wiring lives outside the daemon (see `docs/sensor_deployment.md §6` — a `scripts/run_sensor.py` entry point is still on the TODO).

**`WindowedCounter` / `DailyAccumulator` / `OfflineBuffer`:**
- Purpose: pure-logic aggregation + durable outbox.
- Files: `src/camina/core/counter.py`, `src/camina/io/offline_buffer.py`.
- Pattern: dataclasses (`WindowSnapshot`, `DailySnapshot`) crossing I/O boundaries; SQLite WAL mode for crash-safe persistence.

**`StreetsRepo` interface (mock vs live):**
- Purpose: shield API routes and RSCs from the data source.
- Files: `dashboard/src/lib/repo/types.ts`, `dashboard/src/lib/repo/index.ts`, `dashboard/src/lib/repo/streets-mock.ts`, `dashboard/src/lib/repo/streets-live.ts`.
- Pattern: one interface, two implementations; selection driven by `CAMINA_DATA_SOURCE` env at import time.

**`CityMapShell`:**
- Purpose: client-side host that co-locates the map with the side panel and mediates the "selected street" state.
- File: `dashboard/src/app/[city]/CityMapShell.tsx`.
- Pattern: lifted state (`selected: string | null`), memoized lookups, dynamic `ssr: false` import of `StreetMap` to avoid SSR+MapLibre interactions.

**`StreetMap` (MapLibre wrapper):**
- Purpose: render OSM-based Carto Positron basemap, paint streets with metric ramps, emit click events.
- File: `dashboard/src/components/map/StreetMap.tsx`.
- Pattern: `useRef` for the map instance, inline `position: absolute; inset: 0` + ResizeObserver for canvas sizing, `rampExpression()` with `coalesce` guard so null `feature-state` does not crash MapLibre paint.

**`StreetSidePanel`:**
- Purpose: total count, avg speed, per-class breakdown, and (dev-only) admin strip.
- File: `dashboard/src/components/panels/StreetSidePanel.tsx`.
- Pattern: fetches `/api/admin/streets/[id]/info` conditionally gated by `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`; responsive between right-side docked sheet on desktop and bottom sheet on mobile.

**Admin info API:**
- Purpose: reveal sensor identifiers + GPS only to admins (or to anyone in mock mode, since the fixtures have no real PII).
- File: `dashboard/src/app/api/admin/streets/[id]/info/route.ts`.
- Pattern: `if (!isMock) requireAdmin()` — the type `StreetAdminInfo` is deliberately the only place sensor GPS leaves the server.

## Entry Points

**`main.py`:**
- Location: `main.py`.
- Triggers: `python main.py`.
- Responsibilities: load YAML config via `src.camina.utils.config.load_config()`, construct `ModalShareCounterApp`, call `app.run()`. Dev/PC entry to the legacy pipeline.

**`python -m src.camina.service.sensor_daemon --config <path>`:**
- Location: `src/camina/service/sensor_daemon.py::main`.
- Triggers: `deploy/systemd/camina-sensor.service`.
- Responsibilities: parse CLI args, load `DaemonConfig` from YAML. NOTE: the current `main()` deliberately raises `SystemExit` pointing at `docs/sensor_deployment.md §6` because the YOLO+OpenCV wiring that injects `frame_source`/`detect_and_track` has not yet been committed — this is tracked in `TODO.md` as "⬜ Production entry point that composes `SensorDaemon` with the existing YOLO + SORT pipeline → `scripts/run_sensor.py`".

**Training scripts:**
- `scripts/train/fine_tune.py`, `custom_model_train/scripts/train_yolo11n.py`, `custom_model_train/run_camina_pipeline.py` — offline training and evaluation.
- `scripts/calibrate_camera.py` — on-device calibration helper invoked by `CalibrationMonitor`.
- `scripts/generate_mock_dublin.py` — seeds `data/mock/dublin/*.json` fixtures consumed by the dashboard in mock mode.

**Dashboard routes (Next.js App Router):**
- Root: `dashboard/src/app/page.tsx` — redirects to `/dublin`.
- City: `dashboard/src/app/[city]/page.tsx` — loads streets + initial metrics, renders `CityMapShell`.
- Street detail: `dashboard/src/app/[city]/street/[slug]/page.tsx`.
- Sign-in: `dashboard/src/app/(auth)/sign-in/page.tsx`, `dashboard/src/app/(auth)/sign-in/error/page.tsx`.
- Admin: `dashboard/src/app/admin/layout.tsx` (calls `requireAdmin()`, redirects anon → `/sign-in`, non-admin → `/dublin`) + nested pages (`admin/{sensors,streets,members,events,audit,page.tsx}`).

**Dashboard scripts:**
- `dashboard/scripts/download-dublin-tiles.mjs` — pulls the ~60 MB Carto Positron tileset into `dashboard/public/tiles/` (gitignored).
- `dashboard/scripts/inspect-map.mjs`, `dashboard/scripts/open-preview.mjs` — headless screenshot + preview helpers used during dev.

## Error Handling

**Strategy:**
- Edge agent: `OfflineBuffer` is the single point of truth for resilience — any network/HTTP failure enqueues the payload and retries on the next publish. Daily rows that failed to publish are replayed at startup via `SensorDaemon._catch_up_daily`. Dropping oldest is chosen over backpressure (the sensor never stalls counting).
- Dashboard ingest routes: return structured JSON `{ error, issues? }` with 400 for bad schema, 401 for missing/invalid token, 403 for missing admin, 404 for not-found, 501 when live-mode is unimplemented (`api/ingest/sensors/[id]/counts/route.ts`).
- Map rendering: `rampExpression()` wraps `feature-state` lookups in `coalesce(...)` so freshly-added features with null state do not throw (`dashboard/src/lib/geo.ts`).
- Legacy app: `CalibrationMonitor` prompts the operator on camera-position drift; SORT max-age and IOU thresholds tuned in `configs/main_config.yaml`.

**Patterns:**
- Python: `try/except OSError` in `_read_cpu_temp` to degrade gracefully on non-Linux hosts (returns `None`); explicit `Event`-driven shutdown on SIGINT/SIGTERM.
- TypeScript: `.safeParse()` from zod, `cache: "no-store"` on admin fetches, defensive `Number.isFinite` checks in formatters (`StreetSidePanel`), cancellation flags on effect-scoped fetches.

## Cross-Cutting Concerns

**Logging:**
- Python: module-level `logging.getLogger(__name__)`; daemon configures root with `%(asctime)s %(levelname)s %(name)s: %(message)s` (`src/camina/service/sensor_daemon.py::main`).
- Legacy app: plain-text logs at `data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log` via `DataLogger` (`src/camina/app.py`).
- Dashboard: plain `console.*` today; a uniform route-handler logging wrapper is a TODO (per `TODO.md` §6 — Security / observability).

**Validation:**
- Edge side: dataclasses in `src/camina/io/schemas.py`.
- Cloud side: zod schemas in `dashboard/src/lib/schemas.ts` — schema versions (`schema_version`) are part of the wire format for forward compatibility.

**Authentication:**
- Ingest: per-device Bearer token — currently a shared dev token via `CAMINA_DEV_INGEST_TOKEN`; production plan is bcrypt-compare against `sensors.api_token_hash` (Drizzle lookup) and eventually short-lived JWT for TRL 6+ (per `TODO.md`).
- Admin UI: Auth.js v5 with Google SSO only (`dashboard/src/lib/auth.ts`); dev allowlist via `CAMINA_DEV_ALLOWED_EMAILS` / `CAMINA_DEV_ADMIN_EMAILS`; live allowlist via `allowed_members` / `allowed_domains` tables.
- Cron: shared-secret header verified by `dashboard/src/lib/cron-auth.ts` (`VERCEL_CRON_SECRET` or `CAMINA_DEV_CRON_SECRET`).

**Security headers / edge rewrites:**
- `dashboard/proxy.ts` (Next.js 16 renamed `middleware.ts`) — adds `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` on every response.
- `dashboard/vercel.ts` — declares HSTS, cache-control for `/basemap/*`, root redirect to `/dublin`, and cron schedules.

## Configuration Composition

**Edge agent start-up YAML (`configs/sensor.yaml`):**
- Only start-up values live in YAML (`sensor_id`, `api_base_url`, `api_token`, `state_db_path`, `classes`, `fw_version`, defaults for `publish_interval_seconds`/`heartbeat_interval_seconds`/`outbox_max_rows`). Runtime parameters (intervals, detection zone) are owned by the backend and applied via `ConfigPoller` after the first successful contact.

**Legacy app YAML (`configs/main_config.yaml`):**
- Full legacy configuration — model path, camera source, logging, display, SORT, speed thresholds per class, calibration, motion/low-light, alignment email hooks.

**Class registry (`configs/classes.yaml`):**
- Loaded by `src.camina.utils.config.load_classes()`; maps integer class IDs to string labels shared by detector, logger, and display.

**Dashboard env (`dashboard/.env.example` + Vercel env):**
- `CAMINA_DATA_SOURCE` (mock | live), `CAMINA_MOCK_CITY`, `CAMINA_DEV_INGEST_TOKEN`, `CAMINA_DEV_ALLOWED_EMAILS`, `CAMINA_DEV_ADMIN_EMAILS`, `CAMINA_DEV_CRON_SECRET`, `VERCEL_CRON_SECRET`, `DATABASE_URL` (live only), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXTAUTH_SECRET`, `NEXT_PUBLIC_CAMINA_DEV_ADMIN` (dev-only boolean that flips the admin strip on the side panel).

**Next.js config (`dashboard/next.config.mjs`):**
- `reactStrictMode: false` (temporarily off to avoid MapLibre double-mount races — tracked in `TODO.md` house-keeping).
- `cacheComponents: true` is commented out until `/[city]` and `/[city]/street/[slug]` wrap their uncached reads in `<Suspense>` boundaries.
- `typedRoutes: true`.

**Vercel config (`dashboard/vercel.ts`, typed via `@vercel/config/v1`):**
- Builds with `pnpm build`, declares redirects (`/` → `/dublin`), security headers, and three cron schedules.

## Recent Architectural Decisions

Visible in `DESIGN.md`, `TODO.md`, and `plan/`:

- **Plan 01 (`plan/01-windowed-counter-and-ingest.md`)** — closed: edge agent replaces ad-hoc logging with windowed counting + HTTPS ingest + offline WAL outbox + version-gated remote config. Proven by the 60-test suite in `tests/`.
- **Plan 02 (`plan/02-dashboard-vercel.md`)** — in-flight: Next.js 16 + Tailwind + Drizzle dashboard hosted on Vercel, with Neon Postgres + PostGIS for live data. Key decisions: Timescale was evaluated and rejected in favour of materialized views refreshed by Vercel Cron (see SQL migration header comment at `dashboard/drizzle/migrations/0000_init.sql`); MapLibre + local Carto Positron tiles instead of a hosted provider to keep the deployment self-contained; mock/live data-source split to unblock dev before the DB is provisioned.
- **Design language (`DESIGN.md`)** — Uber-style monochrome aesthetic (pure black + pure white + pill buttons at 999px radius + whisper-soft shadows) encoded into `dashboard/tailwind.config.ts` and `dashboard/src/styles/globals.css` (semantic classes like `chip`, `hover-light`, `body-gray`, `rounded-feature`).
- **Privacy-first contract** — enforced both by hardware behavior (no image/video upload, edge-only inference) and by the type system (`StreetSummary` public vs `StreetAdminInfo` admin-only, plus `sensors.latitude/longitude` never surfaces in public routes).
- **Strict Mode + cache components deferred** — `reactStrictMode` and `cacheComponents` both intentionally disabled pending map-init hardening; explicitly called out in `TODO.md` house-keeping so future work re-enables them together with `<Suspense>` wrappers.

---

*Architecture analysis: 2026-04-23*
