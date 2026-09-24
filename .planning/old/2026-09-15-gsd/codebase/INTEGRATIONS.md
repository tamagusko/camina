# External Integrations

**Analysis Date:** 2026-04-23

CAMINA has two integration surfaces:

1. **Dashboard (Next.js on Vercel)** — outbound to Google SSO, Neon Postgres, (optional) Sentry, Upstash Redis, Protomaps/Carto tile CDNs; inbound webhooks from Vercel Cron and from edge sensors.
2. **Edge sensor (Python on Raspberry Pi)** — outbound only, to the dashboard's `/api/ingest/…` endpoints over HTTPS with per-device Bearer tokens.

No AWS or GCP SDKs are imported anywhere in the repository.

## APIs & External Services

### Map / Geospatial

- **Carto Basemaps (raster tiles)** — `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png`, subdomains `a|b|c|d`.
  - Consumer: `dashboard/scripts/download-dublin-tiles.mjs` pre-downloads tiles for central Dublin (bbox `-6.31,53.32,-6.20,53.38`; zooms 12–18) into `dashboard/public/tiles/{z}/{x}/{y}.png`.
  - At runtime the map loads them **locally** from `/tiles/{z}/{x}/{y}.png` (see `StreetMap.tsx` line 94) — no runtime CDN call from the browser.
  - Attribution on the map: OpenStreetMap + CARTO (hard-coded in `dashboard/src/components/map/StreetMap.tsx`).
  - SDK: none; plain `fetch` in `dashboard/scripts/download-dublin-tiles.mjs` with `User-Agent: "CAMINA-tile-downloader/0.1 (research dev; tamagusko@gmail.com)"`.
- **Protomaps / PMTiles** — `pmtiles@^3.2.0` declared as a dependency and env var `PROTOMAPS_PMTILES_URL` documented in `dashboard/.env.example` (e.g. `https://cdn.../dublin.pmtiles`). **Not yet wired** in `StreetMap.tsx`; planned path per `dashboard/README.md` §Deployment.
- **OpenStreetMap (OSM)** — Source of street geometry (`osm_way_ids` array column in `streets` table at `dashboard/drizzle/schema.ts` and `dashboard/drizzle/migrations/0000_init.sql`). Mock data in `scripts/generate_mock_dublin.py` hand-codes real Dublin street geometries with their real OSM way IDs.
- **Vercel cache headers** for basemap directory: `routes.cacheControl("/basemap/(.*)", { public: true, maxAge: "1 week", immutable: true })` in `dashboard/vercel.ts`.

### Auth

- **Google SSO via Auth.js v5** (`next-auth@^5.0.0-beta.25` + `next-auth/providers/google`).
  - Config: `dashboard/src/lib/auth.ts` — single provider `Google`; custom sign-in page at `/sign-in`, error page at `/sign-in/error`.
  - Handler route: `dashboard/src/app/api/auth/[...nextauth]/route.ts` (`export const { GET, POST } = handlers`).
  - Env vars: `AUTH_SECRET`, `AUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
  - Allowlist: DB-backed via tables `allowed_members` + `allowed_domains` (`dashboard/drizzle/schema.ts`). Dev fallback uses comma-separated env vars `CAMINA_DEV_ALLOWED_EMAILS` and `CAMINA_DEV_ADMIN_EMAILS`.
  - Role model: the session callback sets `role: "admin" | "viewer"`; `requireAdmin()` helper checks it and is called in admin layout (`dashboard/src/app/admin/layout.tsx`) and admin API route (`dashboard/src/app/api/admin/streets/[id]/info/route.ts`).

### Observability

- **Sentry** — Env var `SENTRY_DSN` exists in `dashboard/.env.example` but no `@sentry/*` package is imported in `dashboard/package.json`. Not wired.
- **Vercel Analytics / Speed Insights** — Listed in `dashboard/README.md` §Deployment as a Step D14 follow-up. Not installed.
- **Logging** — Python uses module-level `logging.getLogger(__name__)` (standard library). Dashboard uses `console.info`/`console.warn`/`console.error` (grep reveals `[CAMINA]`-prefixed `console.info` in `StreetMap.tsx`).

### Rate Limiting

- **Upstash Redis** — Env vars `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` in `dashboard/.env.example`. No `@upstash/*` client imported yet. Planned but not implemented.

## Data Storage

### Dashboard (live mode)

- **Neon Postgres + PostGIS** — Default live database.
  - DDL: `dashboard/drizzle/migrations/0000_init.sql` — tables `sensors`, `streets` (with `GEOMETRY(MultiLineString, 4326)` + `GEOMETRY(Polygon, 4326)` bbox and GIST indexes), `sensor_street_coverage`, `sensor_readings`, `sensor_daily_totals`, `sensor_heartbeats`, `allowed_members`, `allowed_domains`, `audit_log`.
  - Materialized views: `street_readings_15m`, `street_readings_hourly` (unique indexes support `REFRESH MATERIALIZED VIEW CONCURRENTLY`).
  - Connection env vars: `DATABASE_URL` (pooled) and `DATABASE_URL_UNPOOLED` (for migrations, referenced in `dashboard/drizzle.config.ts`).
  - Client: `postgres@^3.4.5` singleton lazy-constructed in `dashboard/src/lib/db.ts` (`max: 5, prepare: false`).
  - ORM: Drizzle schema mirrors the SQL (`dashboard/drizzle/schema.ts`).
  - Live repo `dashboard/src/lib/repo/streets-live.ts` is currently a **stub** that throws `"Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock."` on every method.

### Dashboard (mock mode, default)

- **JSON fixtures** under `data/mock/dublin/` — `streets.json`, `sensors.json`, `sensor_street_coverage.json`, `sensor_readings.json`, `sensor_daily_totals.json`, `sensor_heartbeats.json`.
- Generator: `scripts/generate_mock_dublin.py` (seed `20260421`, 7 days of 15-min windows, 10 sensors on 10 real Dublin streets).
- Loader: `dashboard/src/lib/mock-loader.ts` reads via `process.cwd()/../data/mock/{mockCity}/…` with in-process memoisation.

### Edge sensor local state

- **SQLite** (stdlib `sqlite3`) — Two files:
  - `DailyAccumulator` in `src/camina/core/counter.py` — table `daily_totals` at `config.state_db_path` (configured `/var/lib/camina/state.db`).
  - `OfflineBuffer` in `src/camina/io/offline_buffer.py` — FIFO outbox table `outbox` at `<state_db>.outbox.db`, WAL mode, default cap `10_000` rows.
- **No image/video storage** — per `README.md`, "Fully edge-processed — no image/video storage or upload." Only aggregated counts cross the wire.

### File Storage

- No object storage (S3, GCS, Azure Blob, R2) integrations.
- **Local filesystem only** for models (`models/`, `yolo11n.pt` at repo root), calibration frames (`data/calibration/reference_frame.jpg`), mock fixtures (`data/mock/dublin/`), pre-downloaded map tiles (`dashboard/public/tiles/`), and sensor log files (`data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log` written by `DataLogger` in `src/camina/app.py`).

### Caching

- **Next.js cache tags** — Typed factory in `dashboard/src/lib/cache-tags.ts` (`tags.streetsList`, `tags.street`, `tags.streetReadings`, `tags.cityMetrics`). Used with `cacheTag()` / `revalidateTag()` (documented in `dashboard/README.md` §Conventions). `cacheComponents` is currently disabled in `dashboard/next.config.mjs` (commented) pending Suspense wrapping of uncached reads.
- **HTTP cache headers** on public routes — e.g. `"Cache-Control": "public, s-maxage=60, stale-while-revalidate=300"` on `/api/streets/[id]` (`dashboard/src/app/api/streets/[id]/route.ts`) and `s-maxage=30, stale-while-revalidate=120` on `/api/metrics`.

## Model Weights / External Artifacts

- **CAMINAv1 (custom-trained)** — primary production model.
  - `models/20250629_warmup_best.pt` — PyTorch checkpoint.
  - `models/20250629_warmup_best.torchscript` — TorchScript export.
  - `models/20250629_warmup_best_ncnn_model/` — NCNN directory (Tencent NCNN runtime; optimal on Raspberry Pi ARM).
  - Also committed at repo root for convenience: `yolo11n.pt` (5.6 MB) and `yolo11n.torchscript` (11 MB).
- **Ultralytics YOLO11n baseline** — `models/yolo11n.pt`, `models/yolo11n_ncnn_model/`. Download URL (referenced in `README.md`): `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`.
- **Ultralytics YOLOv8n** — `models/yolov8n.pt` (comparison baseline for `custom_model_train/scripts/model_comparison_framework.py`).
- **Depth-Anything-V2** (optional runtime download) — Expected at `models/depth_anything_v2_vits.pth` (see `src/camina/utils/calibration.py` line ~55). Install URL noted in code: `https://github.com/DepthAnything/Depth-Anything-V2`. Pip extra `git+https://github.com/DepthAnything/Depth-Anything-V2.git` is commented in `requirements_calibration.txt`.
- **Training pipeline** — `custom_model_train/run_camina_pipeline.py` with config `custom_model_train/pipeline_config.yaml`. Scripts include DINOv3-assisted semi-auto labeling (`custom_model_train/scripts/dinov3_semi_auto_labeling.py`) and SAM2+CLIP auto-labeling (`custom_model_train/scripts/sam2_clip_auto_labeling.py`).

## Cloud Services

- **No AWS, GCP, or Azure SDKs** in use. `grep` of `src/` and `dashboard/src/` shows no `@aws-sdk`, `boto3`, `@google-cloud`, or `azure-*` imports.
- **Vercel** — sole cloud platform for the dashboard; see next section.

## Vercel Platform Integrations

- **Project config**: typed via `@vercel/config@^0.2.1` in `dashboard/vercel.ts` (replaces `vercel.json`).
  - `framework: "nextjs"`, `buildCommand: "pnpm build"`.
  - Security headers on `/(.*)`: HSTS (`max-age=63072000; includeSubDomains; preload`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
  - Cache headers for `/basemap/(.*)`: `public, max-age=1 week, immutable`.
  - Redirect: `/` → `/dublin` (non-permanent).
- **Vercel Cron jobs** (`crons` array in `dashboard/vercel.ts`):
  - `*/5 * * * *` → `/api/cron/refresh-aggregates` — refreshes `street_readings_15m` / `_hourly` materialized views (handler: `dashboard/src/app/api/cron/refresh-aggregates/route.ts`; currently stubs 501 in live mode).
  - `*/15 * * * *` → `/api/cron/detect-silent` — flags sensors with no recent heartbeat.
  - `0 1 * * *` → `/api/cron/reconcile-daily` — reconciles `sensor_daily_totals` vs summed windows.
  - All cron routes guard with `verifyCron(request)` from `dashboard/src/lib/cron-auth.ts` which checks `Authorization: Bearer ${VERCEL_CRON_SECRET}`. When `VERCEL_CRON_SECRET` is unset (dev), the guard no-ops.
- **Vercel Marketplace (Neon)** — documented setup path in `dashboard/README.md` §Deployment.
- **Vercel env add** — documented flow for provisioning each `.env.example` key.
- **Fluid Compute** — route handlers run on it per `dashboard/README.md` architecture diagram.
- **Rolling Releases + Speed Insights + Analytics** — listed as enable-after-deploy items, not yet integrated.

## Dashboard Data Source Modes

Driven by `CAMINA_DATA_SOURCE` env var (see `dashboard/src/lib/data-source.ts`):

| Value | Behavior | Repo implementation |
|---|---|---|
| `mock` (default) | Reads JSON fixtures from `data/mock/<city>/` via `mock-loader.ts` | `dashboard/src/lib/repo/streets-mock.ts` |
| `live` | Would query Neon Postgres via Drizzle | `dashboard/src/lib/repo/streets-live.ts` (stub; throws on every method) |

The repository factory `dashboard/src/lib/repo/index.ts` selects at import time: `export const streetsRepo: StreetsRepo = isMock ? mockStreetsRepo : liveStreetsRepo;`

The `StreetsRepo` interface (`dashboard/src/lib/repo/types.ts`) defines: `list(city)`, `get(streetId)`, `readings(opts)`, `latestMetrics(opts)`, **`adminInfo(streetId)`**. The `adminInfo` method is the admin-only path returning `StreetAdminInfo` (sensor IDs + GPS + install date + heartbeat + firmware/config versions) — callers MUST gate on admin session.

## Dev-Only Endpoints / Admin Flags

- **`NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`** (`dashboard/.env.example`) — Exposes the admin section in the street-click side panel (`dashboard/src/components/panels/StreetSidePanel.tsx` line ~14) without requiring Google sign-in. In `live` mode the same data is gated by `requireAdmin()`.
- **Admin API bypass in mock mode** — `dashboard/src/app/api/admin/streets/[id]/info/route.ts` skips `requireAdmin()` when `isMock` is true so devs can preview the admin panel without OAuth.
- **Dev ingest token** — `CAMINA_DEV_INGEST_TOKEN` env var; if matched against `Authorization: Bearer …` the ingest route returns ok without a DB lookup (`dashboard/src/lib/ingest-auth.ts`). Live mode's hashed-token lookup is a TODO.
- **Dev auth allowlist** — When `CAMINA_DEV_ALLOWED_EMAILS` is empty in dev, any Google sign-in is accepted (`dashboard/src/lib/auth.ts` line ~32: "If no allowlist configured in dev, accept any sign-in"). Production MUST set the env var or run live mode.
- **Privacy regression test** — `dashboard/tests/unit/privacy-regression.test.ts` asserts that no public repo method leaks `sensor_id`, `sensorId`, `latitude`, or `longitude`. New public routes must be added to this test.
- **`MockDataPill` UI chip** — `dashboard/src/components/layout/MockDataPill.tsx` visually confirms fixture mode.

## Webhooks & Callbacks

### Incoming to the dashboard

- **Edge-sensor ingest (Bearer-authed)** — Device-facing POST routes under `dashboard/src/app/api/ingest/sensors/[id]/`:
  - `POST /api/ingest/sensors/[id]/counts` — 15-min window counts (payload validated by `countsPayloadSchema` in `dashboard/src/lib/schemas.ts`, mirrors `CountsPayload` in `src/camina/io/schemas.py`).
  - `POST /api/ingest/sensors/[id]/daily` — daily cumulative totals (`dailyPayloadSchema` ↔ `DailyPayload`).
  - `POST /api/ingest/sensors/[id]/heartbeat` — status telemetry (`heartbeatPayloadSchema` ↔ `HeartbeatPayload`).
  - `GET /api/ingest/sensors/[id]/config` — returns fresh `SensorConfig` for hot-reload (dev returns a hard-coded `MOCK_CONFIG` in `dashboard/src/app/api/ingest/sensors/[id]/config/route.ts`).
  - All routes call `verifyIngestToken(request, sensorId)` from `dashboard/src/lib/ingest-auth.ts` (Bearer-token check).
  - Responses include `latest_config_version` so the device can trigger a config refresh.
- **Vercel Cron callbacks** — three endpoints listed above, authed by `VERCEL_CRON_SECRET`.
- **Auth.js OAuth callback** — `/api/auth/callback/google` served by the catch-all `[...nextauth]/route.ts`.

### Outgoing from the edge agent

- **To the dashboard ingest API** — `src/camina/io/https_publisher.py` drives three POSTs (`counts`, `daily`, `heartbeat`) and one GET (`config`) through the shared `HttpClient` in `src/camina/io/http_client.py`:
  - Auth: `Authorization: Bearer <api_token>` (per-device) set once on the `httpx.Client`.
  - Idempotency: `Idempotency-Key: <uuid4>` per request (or `outbox-<id>` for outbox drains).
  - Retries: custom `RetryPolicy` (default `max_attempts=5`, exponential backoff with jitter, max 60 s) honours `Retry-After` on 429.
  - Retriable status set: `{408, 425, 429, 500, 502, 503, 504}`.
  - Base URL: `configs/sensor.yaml` → `api_base_url: https://camina.ucd.ie/api/ingest`.
  - User-Agent: `camina-sensor/0.2`.
- **Offline-first delivery** — On network failure, the payload is serialized into the SQLite outbox (`src/camina/io/offline_buffer.py`). Subsequent `_send()` calls drain up to 10 items before the fresh POST.
- **No outgoing email, SMS, push, or message-queue integrations** — `email_sender`/`email_password`/`email_recipient` fields exist in `configs/main_config.yaml` as placeholders for a camera-alignment alert feature, but no SMTP client is imported.
- **No LoRaWAN code** in the current tree despite the README mentioning Dragino RS485-LN as optional hardware. Only HTTPS is wired.

### No other messaging systems

- No Kafka, RabbitMQ, Pub/Sub, SNS/SQS, or WebSocket servers.
- No GraphQL endpoint.

---

*Integration audit: 2026-04-23*
