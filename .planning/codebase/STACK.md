# Technology Stack

**Analysis Date:** 2026-04-23

CAMINA is a dual-stack project:

1. **Edge sensor / ML pipeline** — Python 3.10, PyTorch, YOLO11 (Ultralytics), OpenCV, runs on Raspberry Pi 5 with e-paper / OLED / NCNN.
2. **Dashboard** — Next.js 16 (App Router) + React 19 + TypeScript 5, MapLibre GL, Drizzle ORM over Postgres, deployed on Vercel. Located at `dashboard/`.

The two halves communicate over HTTPS ingest endpoints exposed by the dashboard (`/api/ingest/sensors/{id}/…`) and consumed by the edge agent via an `httpx` client.

## Languages

**Primary:**
- **Python 3.10** — Edge agent, ML pipeline, calibration, mock-data generation. Pinned in `environment.yml` (`python=3.10`). Agent code lives in `src/camina/`, scripts in `scripts/`, custom model training in `custom_model_train/`.
- **TypeScript 5.6+** — Dashboard. `"target": "ES2022"`, `strict: true`, `noUncheckedIndexedAccess: true` in `dashboard/tsconfig.json`. React 19 + JSX. Path alias `@/* → ./src/*`.

**Secondary:**
- **SQL (PostgreSQL / PostGIS dialect)** — Raw DDL migration in `dashboard/drizzle/migrations/0000_init.sql`; Drizzle schema in `dashboard/drizzle/schema.ts`.
- **YAML** — Edge-agent config (`configs/main_config.yaml`, `configs/sensor.yaml`, `configs/classes.yaml`), training config (`scripts/train/train_param_warmup.yaml`, `scripts/train/train_param_finetune.yaml`), model pipeline (`custom_model_train/pipeline_config.yaml`).
- **JavaScript (ESM)** — Dashboard utility scripts in `dashboard/scripts/*.mjs` (e.g., `download-dublin-tiles.mjs`, `inspect-map.mjs`).

## Runtime

**Python runtime:**
- CPython 3.10 (conda env via `environment.yml`; name `camina`).
- Production hosts: Raspberry Pi 4/5 (`README.md` §Hardware Requirements). Dev also supports macOS/Linux.
- Edge daemon launched via systemd unit `deploy/systemd/camina-sensor.service` (`ExecStart=/opt/camina/venv/bin/python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml`).

**Node runtime (dashboard):**
- Node ≥ 20.11 (`dashboard/package.json` `engines.node`).
- Pinned to **Node 22.11.0** in `dashboard/.nvmrc`.
- Dev server runs Turbopack (`next dev --turbo` in `dashboard/package.json` scripts).

**Package managers:**
- **pip** / **conda** for Python (no `uv.lock`, no `pyproject.toml`; dependencies in `requirements.txt` and `requirements_calibration.txt`).
- **pnpm 9.12.0** for the dashboard (pinned in `dashboard/package.json` `"packageManager": "pnpm@9.12.0"`). Lockfile: `dashboard/pnpm-lock.yaml` (present).

## Frameworks

### Edge / ML (Python)

- **Ultralytics YOLO `8.3.123`** — Detection entry point (`from ultralytics import YOLO` in `src/camina/app.py`). Model weights: `models/20250629_warmup_best.pt`, `yolo11n.pt`, plus NCNN-exported `models/20250629_warmup_best_ncnn_model/` for Raspberry Pi.
- **PyTorch `2.7.1`** + **torchvision `0.22.0`** (`requirements.txt`).
- **OpenCV `4.11.0.86`** (`opencv-python`) — Video capture, drawing, `cv2.imshow` dev window (`src/camina/app.py`).
- **SORT tracker** — Custom implementation in `src/camina/core/tracker.py` built on **filterpy `1.4.5`** (Kalman filter) and **scipy `1.15.2`** (`linear_sum_assignment`).
- **Pydantic `>=2.5`** — Wire schemas in `src/camina/io/schemas.py` (`CountsPayload`, `DailyPayload`, `HeartbeatPayload`, `SensorConfig`, `IngestResponse`). Uses `ConfigDict(extra="forbid")` and `field_validator` decorators.
- **httpx `>=0.27`** — HTTPS client in `src/camina/io/http_client.py` (retries, Bearer auth, `Retry-After` handling).
- **PyYAML `6.0.2`** — Config loading (`src/camina/utils/config.py`, `src/camina/service/sensor_daemon.py`).
- **Depth-Anything-V2** (optional) — Depth-based calibration in `src/camina/utils/calibration.py` (lazy import; falls back if unavailable). Extra deps in `requirements_calibration.txt`: `scikit-image`, `transformers>=4.20`, `timm>=0.6`.
- **Pillow `11.2.1`** + **luma.oled** + **waveshare `epaper`** — Display drivers in `src/camina/utils/display.py` (optional imports guarded with try/except).
- **pandas `2.2.3`**, **numpy `2.2.5`**, **matplotlib `3.10.1`**, **seaborn `0.13.2`** — Analysis/plotting.
- **gopro2gpx** — GPS extraction utility.

### Dashboard (Next.js)

- **Next.js `^16.0.0`** (App Router) — `dashboard/next.config.mjs` (`typedRoutes: true`, `reactStrictMode: false`). Uses the v16 network-boundary proxy (`dashboard/proxy.ts`, renamed from `middleware.ts`).
- **React `^19.0.0`** + **react-dom `^19.0.0`**. Server Components by default; `'use client'` only where needed (documented in `dashboard/README.md` §Conventions).
- **Auth.js v5** (`next-auth@^5.0.0-beta.25`) — Google SSO only, configured in `dashboard/src/lib/auth.ts`. Handlers exported from `dashboard/src/app/api/auth/[...nextauth]/route.ts`.
- **Drizzle ORM `^0.36.4`** + **drizzle-kit `^0.29.1`** — Postgres schema/migrations (`dashboard/drizzle/schema.ts`, `dashboard/drizzle.config.ts`). Dialect: `postgresql`.
- **postgres `^3.4.5`** — Low-level Postgres driver used by Drizzle (`dashboard/src/lib/db.ts`: `postgres(url, { max: 5, prepare: false })`).
- **Zod `^3.23.8`** — Request validation (`dashboard/src/lib/schemas.ts`) — mirrors the Python Pydantic models for ingest payloads.
- **server-only `^0.0.1`** — Marks server-only modules (`data-source.ts`, `db.ts`, `auth.ts`, `mock-loader.ts`, `cron-auth.ts`, `ingest-auth.ts`, repo files).
- **Vercel config** (`@vercel/config@^0.2.1`) — Typed Vercel project config in `dashboard/vercel.ts` (replaces `vercel.json`) declaring framework, headers, redirects, and 3 cron jobs.

### Mapping & Visualisation

- **MapLibre GL JS `^4.7.1`** — `maplibre-gl` — Main map in `dashboard/src/components/map/StreetMap.tsx` (style v8, raster tile source, `NavigationControl`, GeoJSON source with `feature-state` paint expressions via `rampExpression` in `dashboard/src/lib/geo.ts`).
- **PMTiles `^3.2.0`** (`pmtiles`) — Declared for basemap via Protomaps (env var `PROTOMAPS_PMTILES_URL`); current implementation uses locally pre-downloaded Carto raster tiles served from `dashboard/public/tiles/{z}/{x}/{y}.png`.
- **Recharts `^2.15.0`** — Time-series charts in `dashboard/src/components/charts/StreetTimeSeries.tsx`.
- **Lucide React `^0.460.0`** — Icons (`X` icon used in `StreetSidePanel.tsx`).
- `react-leaflet` is **not** used.

### Testing

- **Vitest `^2.1.5`** (dashboard) — Unit tests. Config: `dashboard/vitest.config.ts` (`environment: "node"`, `include: ["tests/unit/**/*.test.ts"]`, alias `@ → src`). Suite includes `dashboard/tests/unit/privacy-regression.test.ts` and `schemas.test.ts`.
- **Playwright `^1.48.0`** (`@playwright/test`) — E2E. Config: `dashboard/playwright.config.ts` (projects: Desktop Chrome + Pixel 7 mobile; runs `pnpm dev` with `CAMINA_DATA_SOURCE=mock`).
- **pytest** (implicit from `.pytest_cache/` and `tests/test_*.py` files) — Python unit tests for counter, offline buffer, HTTPS publisher, config poller, sensor daemon. Test configs not in a pyproject; discovered via default pytest rules.

### Build / Dev Tooling (dashboard)

- **Tailwind CSS `^3.4.15`** — Config `dashboard/tailwind.config.ts` with design tokens (Uber-inspired greys, custom `font-display`/`font-body` stacks, `rounded-pill`/`rounded-card`/`rounded-feature`, custom spacing). Content globs: `./src/**/*.{ts,tsx}`.
- **PostCSS `^8.4.49`** + **Autoprefixer `^10.4.20`** (`dashboard/postcss.config.mjs`).
- **TypeScript compiler** — `tsc --noEmit` via `pnpm typecheck`.
- **Next lint** — `pnpm lint` (`next lint`).
- **tsx `^4.19.2`** — Used to run TypeScript seed scripts (`db:seed` → `tsx scripts/seed-from-mock.ts`).

## Key Dependencies

**Critical (edge):**
- `ultralytics==8.3.123`, `torch==2.7.1`, `opencv-python==4.11.0.86` — core detector loop.
- `httpx`, `pydantic` — HTTPS ingest path.
- `filterpy`, `scipy` — SORT Kalman tracker.

**Critical (dashboard):**
- `next@^16`, `react@^19` — framework baseline.
- `maplibre-gl@^4.7.1` — map rendering.
- `drizzle-orm@^0.36.4` + `postgres@^3.4.5` — live DB path.
- `next-auth@^5.0.0-beta.25` — Google SSO auth.
- `zod@^3.23.8` — ingest payload validation.

**Infrastructure:**
- `server-only` — enforces Node-only bundle for DB/auth/mock-loader modules.
- `clsx` + `tailwind-merge` — conditional class composition.
- `@vercel/config` — typed deployment config.

## Configuration

**Python edge agent:**
- Static start-up config: `configs/sensor.yaml` (per-device `sensor_id`, `api_base_url`, `api_token`, `state_db_path`, class list, default publish/heartbeat intervals).
- Dev/legacy config: `configs/main_config.yaml` (camera, model path, speed thresholds, calibration, email alerts).
- Class map: `configs/classes.yaml` (numeric id → class name). CAMINAv1 production classes (9) are defined inside `configs/sensor.yaml` and `dashboard/src/lib/types.ts` (`ROAD_USER_CLASSES`).
- Dynamic runtime config: fetched from backend via `GET /v1/sensors/{id}/config` and applied hot through `src/camina/io/config_poller.py` (`SensorConfig` pydantic model).
- Loader: `src/camina/utils/config.py` walks up to find the `configs/` directory.

**Dashboard environment:**
- `dashboard/.env.example` documents all required vars; `.env.local` is gitignored.
- Key vars: `CAMINA_DATA_SOURCE` (`mock`|`live`), `CAMINA_MOCK_CITY`, `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `AUTH_SECRET`, `AUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PROTOMAPS_PMTILES_URL`, `SENTRY_DSN`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `VERCEL_CRON_SECRET`, `CAMINA_DEV_INGEST_TOKEN`, `CAMINA_DEV_ALLOWED_EMAILS`, `CAMINA_DEV_ADMIN_EMAILS`, `NEXT_PUBLIC_CAMINA_DEV_ADMIN`.

**Build config files:**
- `dashboard/next.config.mjs` — Next.js runtime flags (`reactStrictMode: false`, `typedRoutes: true`, empty `images.remotePatterns`).
- `dashboard/tsconfig.json` — TS strict mode, `moduleResolution: "bundler"`, `paths: { "@/*": ["./src/*"] }`.
- `dashboard/tailwind.config.ts` — design tokens.
- `dashboard/drizzle.config.ts` — pointed at `./drizzle/schema.ts`, output `./drizzle/migrations`, dialect `postgresql`.
- `dashboard/vercel.ts` — framework, cache headers for `/basemap/*`, security headers, `/` → `/dublin` redirect, three cron schedules.
- `dashboard/proxy.ts` — security headers at the edge (runs on every request per matcher).

## Platform Requirements

**Development:**
- Python 3.10 via conda (`conda env create -f environment.yml`) or pip (`pip install -r requirements.txt`).
- Node ≥ 20.11 (recommended 22.11) + pnpm 9.12 (`cd dashboard && pnpm install`).
- For dashboard-only mock dev: no database required (`CAMINA_DATA_SOURCE=mock` default).

**Production (edge):**
- Raspberry Pi 4/5 with Pi Camera Module 3 (NoIR recommended for low-light).
- Optional: e-paper (`epd2in13_V4`), OLED (`ssd1306` via luma.oled over I²C), IR floodlight, Dragino RS485-LN for LoRaWAN, solar power.
- NCNN-exported model for ARM inference (`models/20250629_warmup_best_ncnn_model/`).
- systemd user `camina`, state dir `/var/lib/camina`.

**Production (dashboard):**
- Vercel (framework `nextjs`, build `pnpm build`) — `dashboard/vercel.ts` is the deploy manifest.
- Neon Postgres with PostGIS extension (`CREATE EXTENSION IF NOT EXISTS postgis;` in `dashboard/drizzle/migrations/0000_init.sql`). TimescaleDB is explicitly **not** required.
- Vercel Cron for materialized-view refresh, silent-sensor detection, and daily reconciliation.

---

*Stack analysis: 2026-04-23*
