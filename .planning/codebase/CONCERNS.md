# Codebase Concerns

**Analysis Date:** 2026-04-23

CAMINA is a mixed research+engineering codebase: a Python ML/edge pipeline (YOLO11 + SORT + a new HTTPS sensor daemon from Plan 01) plus a Next.js 16 dashboard on Vercel (Plan 02). The recent merge `9efbb7a` (2026-04-21) shipped both plans in scaffolded form, with aggressive debugging of MapLibre canvas sizing and hydration. This document catalogs concerns surfaced by reading `TODO.md`, `DESIGN.md`, `plan/02-*`, the dashboard source, the edge-agent source, config files, and a repo-wide grep. Severities are calibrated to the current research stage (pre-deployment, pre-live-DB).

---

## 1. Known Issues & Recent Fragile Areas

### MapLibre canvas sizing race — React Strict Mode disabled as workaround

- Location: `dashboard/next.config.mjs:6` (`reactStrictMode: false`); `dashboard/src/components/map/StreetMap.tsx:63-213` (map init effect); `TODO.md:146-148` ("Re-enable reactStrictMode once MapLibre init is fully guarded")
- Severity: **medium**
- Description: Strict Mode's dev-only double-mount was racing with MapLibre's canvas sizing (mount → cleanup → remount). The fix shipped includes an inline-style fallback, a `ResizeObserver`, and a forced `map.resize()` on load, but Strict Mode is still off as a safety net. This masks any future `useEffect` cleanup bugs in dev.
- Remediation: Re-enable `reactStrictMode: true` and verify the map survives a simulated double-mount (store `isMounted` guard around the MapLibre `new Map(...)` call if any residual races appear).

### ResizeObserver workaround added for canvas auto-resize

- Location: `dashboard/src/components/map/StreetMap.tsx:193-201`
- Severity: **low**
- Description: A `ResizeObserver` is attached to the map container so the canvas stays in sync with DevTools docking, window resize, and Strict Mode edge cases. This is defensive but correct; the concern is that the observer logs every resize (`console.info("[CAMINA] container resize → canvas: ...")`), which is noisy once the page is stable.
- Remediation: Keep the `ResizeObserver` but gate the log behind `process.env.NODE_ENV !== "production"` or remove it per `TODO.md:152-153`.

### Inline style fallback for map container sizing

- Location: `dashboard/src/components/map/StreetMap.tsx:242-259`
- Severity: **low**
- Description: The outer container uses both Tailwind classes (`h-screen w-screen`) and inline styles (`{ height: "100dvh", width: "100vw" }`), and the inner MapLibre container uses inline `position: absolute; inset: 0` to override `.maplibregl-map`. Works, but is a second source of truth vs. the stylesheet that could silently drift.
- Remediation: Move the inline overrides into `src/styles/globals.css` targeting `.maplibregl-map` explicitly, then delete the inline `style={…}` object.

### Local tile serving gaps (404s outside downloaded Dublin coverage)

- Location: `dashboard/public/tiles/` (8 063 PNGs, 77 MB, zooms 12–18, BBOX `-6.31…-6.20 × 53.32…53.38`); `dashboard/scripts/download-dublin-tiles.mjs:13-20`; `dashboard/src/components/map/StreetMap.tsx:94-107`
- Severity: **medium**
- Description: The MapLibre source hardcodes `minzoom: 12, maxzoom: 18` and `tiles: ["/tiles/{z}/{x}/{y}.png"]`. Any pan outside the narrow central-Dublin bbox (or any zoom < 12 / > 18) produces 404s and blank tiles. No fallback basemap. The dashboard is also silently unusable on a fresh clone until a 77 MB download is run (`TODO.md:155-156`).
- Remediation: Either (a) add a remote CARTO / Protomaps PMTiles fallback URL and keep local tiles as the primary; or (b) constrain `maxBounds` on the MapLibre map so panning outside coverage is physically impossible, plus a visible "tiles missing — run download-dublin-tiles.mjs" banner in dev.

### Live repository stub (`adminInfo` and every other method throw)

- Location: `dashboard/src/lib/repo/streets-live.ts:1-23` — every method throws `"Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock."`; selected at boot by `dashboard/src/lib/repo/index.ts:7`
- Severity: **high** (tech debt; blocks production)
- Description: The live Postgres-backed repository is a pure stub. Setting `CAMINA_DATA_SOURCE=live` in any environment will crash every `/api/streets/*`, `/api/metrics`, `/api/admin/streets/*` request on first call. `TODO.md §Plan 02 §1` captures this as "Neon Postgres connection — not yet implemented".
- Remediation: Implement `liveStreetsRepo` against `drizzle/schema.ts` (mirror `streets-mock.ts` aggregation semantics) before `CAMINA_DATA_SOURCE=live` is ever used outside a throwaway preview. Add a boot-time guard that refuses to start in `live` mode until each method is non-throwing.

### SSR disabled for StreetMap (hydration workaround)

- Location: `dashboard/src/app/[city]/CityMapShell.tsx:10-23` (`dynamic(..., { ssr: false })`)
- Severity: **low**
- Description: MapLibre touches `window` during init, so the whole `StreetMap` is client-only. Correct pattern, but it means the map surface is always a post-hydration render — costing FCP and preventing any server-rendered map analytics.
- Remediation: Acceptable as-is. If server-side rendering of the first paint ever becomes a goal, render a static preview PNG (already generated by `dashboard/scripts/inspect-map.mjs`) above the lazy-loaded interactive map.

### Live-mode 501 stubs in every ingest route

- Location: `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts:28-29`; `.../daily/route.ts`; `.../heartbeat/route.ts`; `.../config/route.ts`; `dashboard/src/app/api/cron/refresh-aggregates/route.ts:11-12`; `.../reconcile-daily/route.ts`; `.../detect-silent/route.ts`
- Severity: **high** (tech debt; blocks production)
- Description: In `live` mode every ingest and cron route returns `{ error: "live_mode_not_implemented" }` with HTTP 501. If the edge agent is pointed at a deployed Vercel preview in `live` mode, counts/daily/heartbeat payloads will all be rejected and fall into the offline buffer indefinitely.
- Remediation: Implement DB persistence per ingest route (and the three crons) before any sensor is provisioned against a live environment.

### Diagnostic log on every mount (`[CAMINA] ancestor heights`)

- Location: `dashboard/src/components/map/StreetMap.tsx:67-78`
- Severity: **low**
- Description: `TODO.md:152-153` flags this for removal. It walks the ancestor chain and logs each element's `clientHeight` on every map mount — useful while debugging the Strict Mode resize race, now noise.
- Remediation: Delete the diagnostic block, keep the `ResizeObserver`.

---

## 2. Tech Debt

### Roadmap items from `TODO.md` (Plan 02 — dashboard)

Summary of the 12 open items captured in `TODO.md:66-141`, each of which is real tech debt blocking v1:

1. **Neon Postgres connection** — `dashboard/drizzle/migrations/0000_init.sql` has to run; `dashboard/src/lib/db.ts` is lazy-wired but `streets-live.ts` throws. Severity: **high**.
2. **Google OAuth wiring** — `dashboard/src/lib/auth.ts` has an env-var allowlist fallback (`CAMINA_DEV_ALLOWED_EMAILS`) that still accepts *any* sign-in when the var is empty (`auth.ts:32-35`). Severity: **high** — see §3.
3. **Admin CRUD UIs** (`<SensorForm>`, `<StreetDrawTool>`, `/admin/members`, `PATCH /api/admin/sensors/[id]`). Severity: **medium**.
4. **Events + reconciliation + audit** (`/admin/events`, `/admin/audit`). Severity: **medium**.
5. **Cron implementations** — MV refresh, silent-sensor detection, daily reconciliation. Severity: **medium**.
6. **Security / observability** — BotID, CSP (HSTS is already in `vercel.ts`), Upstash Ratelimit, Sentry, Speed Insights. Severity: **high** (see §3).
7. **Deploy** — Vercel CLI upgrade (currently 50.44.0, target 51.8.0 per `TODO.md:109`), `vercel link`, env, rolling releases, uptime. Severity: **medium**.
8. **Street detail page polish** (`/[city]/street/[slug]` — currently 40 lines, lacks admin strip, time-range picker). Severity: **low**.
9. **Mobile UX polish** (bottom-sheet, 44×44 px tap targets). Severity: **low**.
10. **A11y** (WCAG 2.1 AA; keyboard shortcuts, ARIA live regions). Severity: **medium**.
11. **i18n** (EN + PT via `next-intl`). Severity: **low**.
12. **Tests** (live-repo integration against Dockerized PG+PostGIS; Playwright against Vercel preview; privacy regression on admin routes). Severity: **medium**.

### Roadmap items from `TODO.md` (Plan 01 — edge agent polish)

- Production entry point (`scripts/run_sensor.py`) not yet composed with YOLO + SORT — `docs/sensor_deployment.md §6` only gives a sketch. Severity: **high**.
- Integration test against a deployed Vercel preview with one real sensor — absent. Severity: **medium**.
- Short-lived JWT auth (TRL 6+) — currently opaque Bearer tokens. Severity: **medium**.
- Firmware OTA pipeline (TRL 7) — absent. Severity: **low** until field deployment.

### Legacy edge-agent TODOs (`docs/TODO.md`)

Pre-restructure items; many are still open (LoRaWAN, low-light IR testing, `near_misses_detect.py`, `accident_detect.py`, `camera_position_check.py`, motion-detector integration, dataset/visualization work). Severity: **low** — research backlog, not blockers.

### House-keeping items (`TODO.md:144-157`)

- Re-enable `cacheComponents: true` once `/[city]` and `/[city]/street/[slug]` wrap uncached reads in `<Suspense>`. Currently commented at `dashboard/next.config.mjs:7-8`. Severity: **medium** (leaves PPR perf wins on the table).
- Switch `dashboard/src/lib/auth.ts` allowlist to DB lookup once Neon is connected. Severity: **high** (see §3).

### Inline TODO/FIXME/HACK/XXX comments in source

- Location: repo-wide grep of `src/**`, `dashboard/src/**`, `scripts/**` (all `.ts`, `.tsx`, `.py`, `.mjs`, `.js`)
- Severity: **low**
- Finding: **Zero** `TODO`, `FIXME`, `HACK`, or `XXX` comments in code. All tech debt is captured out-of-band in `TODO.md` + `docs/TODO.md`. This is unusual and positive — `TODO.md` is the single source of truth.
- Remediation: Keep the discipline. When a new shortcut is accepted in code, add it to `TODO.md` instead of leaving a `// TODO` in source.

### Broken import path in `src/speed_estimation.py`

- Location: `src/speed_estimation.py:8` — `with open("src/config.yaml", "r") as f:`
- Severity: **medium**
- Description: File `src/config.yaml` does not exist; the canonical config is `configs/main_config.yaml`. The module header says "DEVELOPMENT" but any importer crashes at import time. This file is not used by the new sensor daemon but is still shipped.
- Remediation: Either delete `src/speed_estimation.py` (if superseded by the Plan 01 pipeline) or repoint the path to `configs/main_config.yaml`.

### `src/utils/` vs `src/camina/utils/` duplication

- Location: `src/utils/` (legacy: `export_ncnn.py`, `infer_image.py`, `oled_display.py`) alongside `src/camina/utils/` (current: `config.py`, `display.py`, `calibration.py`)
- Severity: **low**
- Remediation: Pick one utils package, delete or re-home the other. Referenced from `README.md §Directory Structure` but not from the new Plan 01 code paths.

### `main.py` vs. `src/camina/service/sensor_daemon.py` entry-point overlap

- Location: `main.py` (421 B launcher referenced in `README.md`) vs. `src/camina/service/sensor_daemon.py:258-273` (`main()` that deliberately raises `SystemExit` pointing at `docs/sensor_deployment.md §6`)
- Severity: **low**
- Description: There is no runnable production entry point yet. `main.py` appears to launch the legacy `ModalShareCounterApp`, `sensor_daemon.py::main()` refuses to run.
- Remediation: Ship `scripts/run_sensor.py` per Plan 01 remaining polish (see §2 above) and either delete `main.py` or repoint it.

---

## 3. Security Concerns

### `NEXT_PUBLIC_CAMINA_DEV_ADMIN` exposes admin info without auth

- Location: `dashboard/.env.example:11` (`NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`); `dashboard/.env.local:31` (currently set to `true` on dev machine); `dashboard/src/components/panels/StreetSidePanel.tsx:14-16`; `dashboard/src/app/api/admin/streets/[id]/info/route.ts:16-20`
- Severity: **high**
- Description: When `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`, the side panel renders the admin strip (sensor ID, GPS, install date, firmware, config version, last heartbeat) unconditionally; the server route `/api/admin/streets/[id]/info` *bypasses* `requireAdmin()` whenever `isMock` is true. Because the variable is `NEXT_PUBLIC_`, its value is **inlined at build time** into every client bundle. Shipping a Vercel preview build with this flag still set to `true` would leak GPS + sensor IDs to every visitor — directly violating the GDPR design principle in `plan/02-dashboard-vercel.md §0` and `TODO.md:53`.
- Remediation: (a) Add a `vercel.ts` or `proxy.ts` build-time guard that refuses to deploy to preview/production if `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`. (b) Tighten `app/api/admin/streets/[id]/info/route.ts:16-20` so the mock-mode bypass also requires `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` AND `NODE_ENV !== 'production'`. (c) Document loudly in `.env.example`.

### Dev-mode auth allowlist accepts any Google account when unset

- Location: `dashboard/src/lib/auth.ts:31-37`
- Severity: **high**
- Description: `if (devAllowlist.length === 0) return true;` — when `CAMINA_DEV_ALLOWED_EMAILS` is empty (the default in `.env.example`), any Google account is signed in. Comment says "Production MUST set the env var or run live", but there's no runtime check that enforces this.
- Remediation: Replace the default-allow with a default-deny, or wrap with `if (process.env.NODE_ENV === "production" && !process.env.DATABASE_URL) throw` at module init time.

### Real `AUTH_SECRET` present in `dashboard/.env.local`

- Location: `dashboard/.env.local:30` (contains a real `AUTH_SECRET=<REDACTED>` value — see the actual file)
- Severity: **medium**
- Description: `.env.local` is correctly excluded from git (checked: `.gitignore:39` + `dashboard/.gitignore:5`, `git ls-files` returns empty). The secret is local-only but *does* exist on the dev machine. A careless `git add -A` or a future commit that bypasses `.gitignore` would leak it. Also, the file duplicates every comment from `.env.example`, making it harder to diff.
- Remediation: (a) Rotate this secret when moving to preview/production (it's a dev-only throwaway). (b) Add a pre-commit hook (e.g. `git-secrets` or `ggshield`) that hard-blocks any staged `.env.local`. (c) Consider removing the duplicated placeholder comments from `.env.local`.

### Ingest token is a shared dev Bearer (no per-device crypto)

- Location: `dashboard/src/lib/ingest-auth.ts:9-28` (shared `CAMINA_DEV_INGEST_TOKEN`); `configs/sensor.yaml:8` (`api_token: REPLACE_WITH_PER_DEVICE_BEARER_TOKEN`); `TODO.md:30` ("Short-lived JWT auth for TRL 6+ — currently opaque Bearer token")
- Severity: **medium**
- Description: Every sensor shares one dev Bearer token; no replay protection, no per-sensor rotation, no expiry. Comment at `ingest-auth.ts:24` says live mode will do `bcrypt-compare` against `sensors.api_token_hash` but that path is empty.
- Remediation: Implement per-device token lookup against `sensors.api_token_hash` before first field deployment; move to short-lived JWTs for TRL 6+.

### Cron auth is skipped when `VERCEL_CRON_SECRET` is unset

- Location: `dashboard/src/lib/cron-auth.ts:7-12` (`if (!secret) return null; // Dev mode: skip check.`)
- Severity: **medium**
- Description: Any unauthenticated caller can trigger `/api/cron/*` in any environment where `VERCEL_CRON_SECRET` isn't set. Fine in dev; dangerous if the env-var is forgotten in a preview or prod deploy.
- Remediation: Flip the default to fail-closed when `NODE_ENV === "production"`, or when `VERCEL_ENV` is `preview|production`.

### Hardcoded sender email placeholders in `README.md`

- Location: `README.md:191-195` (example `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT`)
- Severity: **low**
- Description: Not a real secret (`"your_password"`), but the pattern is confusing and invites a copy-paste with real credentials into a `main_config.yaml` that's not explicitly gitignored (only `*.env` and `.env` are). `configs/` is committed.
- Remediation: Move email config into `.env` / `.env.example` instead of `configs/main_config.yaml`, and delete this block from `README.md`.

### Hardcoded secrets grep — overall clean

- Location: repo-wide grep for `api_key|secret|token|password|Bearer` in `src/`, `dashboard/src/`, `scripts/`, `configs/`
- Finding: No hardcoded real credentials in source. All matches are either (a) reading from `process.env` / `os.environ`, (b) parameter names in function signatures, or (c) comments. `configs/sensor.yaml:8` has the placeholder `REPLACE_WITH_PER_DEVICE_BEARER_TOKEN`.
- Severity: **low** (clean, keep it that way).

### Large committed ML model weights (multiple copies)

- Location: repo root `yolo11n.pt` (5.4 MB), `yolo11n.torchscript` (10 MB); `models/20250629_warmup_best.pt` (5.4 MB), `models/20250629_warmup_best.torchscript` (10 MB), `models/yolo11n.pt` (5.4 MB, **duplicate of repo-root**), `models/yolov8n.pt` (6.2 MB); `custom_model_train/yolo11n.pt` (5.4 MB, **third duplicate**); `custom_model_train/SDL fine-tuned_v3-cyclist_cleaned.zip` (76 MB dataset archive). Total: ~230 MB of binaries committed.
- Severity: **medium**
- Description: Mixed. For an academic artefact repo, shipping CAMINAv1 (`20250629_warmup_best.pt`) with the code is defensible for reproducibility (and the NCNN export is the only path that runs on RPi). But (a) the base `yolo11n.pt` is triplicated, (b) a 76 MB dataset `.zip` inside `custom_model_train/` bloats every clone, (c) `tests/test.mov` is 23 MB and is the test video — still not a great fit for a Git repo.
- Remediation: (a) Dedupe `yolo11n.pt` — delete the repo-root and `custom_model_train/` copies, keep only `models/yolo11n.pt`. (b) Move `SDL fine-tuned_v3-cyclist_cleaned.zip` and `tests/test.mov` to Git LFS or an external artefact store; reference by URL+hash in `custom_model_train/data.md`. (c) Keep `models/20250629_warmup_best.*` + `20250629_warmup_best_ncnn_model/` as the one canonical CAMINAv1 release.

---

## 4. Performance Concerns

### 8 063 tiles (77 MB) intentionally gitignored

- Location: `dashboard/public/tiles/` (regenerated via `dashboard/scripts/download-dublin-tiles.mjs`); `dashboard/.gitignore:19` + root `.gitignore:40`
- Severity: **low** (current choice is correct)
- Description: Gitignoring the tiles is the right call. The concern is DX: the app is silently broken on fresh clone until the 77 MB download runs (~2-3 minutes on a decent link). `TODO.md:155-156` captures this.
- Remediation: Add a dev-only startup warning in `CityMapShell.tsx` that checks for the presence of `/tiles/14/...` and renders a "Run `pnpm exec node scripts/download-dublin-tiles.mjs`" banner if missing.

### YOLO model size vs. edge device constraints (RPi5)

- Location: `models/20250629_warmup_best.pt` (5.4 MB FP32), `models/20250629_warmup_best.torchscript` (10 MB), `models/20250629_warmup_best_ncnn_model/` (NCNN-quantized, used on Pi per `README.md:104-114`)
- Severity: **low**
- Description: NCNN export is the right target for RPi5 (INT8, runtime-friendly). The `.pt` and `.torchscript` are shipped alongside for eval/benchmarking. No obvious perf issue.
- Remediation: Document in `docs/MODELS.md` which artefact is loaded in production and at what inference latency on RPi5. Track per-Pi FPS in the sensor daemon heartbeat payload (not currently reported).

### Potentially large per-class speed breakdown payloads in admin/metrics API

- Location: `dashboard/src/app/api/metrics/route.ts:13-32`; `dashboard/src/lib/repo/streets-mock.ts:107-180` (`latestMetrics`)
- Severity: **medium**
- Description: `MetricValue` includes `classBreakdown` (9 classes) and `speedBreakdown` (9 classes) per street. For Dublin's handful of streets this is fine; at ~100 streets it's ~100 × 9 × 2 ≈ 1 800 numeric fields per `/api/metrics` response — still small, but the cron `0 1 * * *` daily reconciliation + MV refresh could balloon server-side intermediate state. The mock repo loads *all* readings into memory (`loadReadings()` at `mock-loader.ts`) and iterates through them on every request — that's O(readings × streets × classes) per request.
- Remediation: (a) In `streets-mock.ts:107-180`, pre-aggregate readings by `(streetId, class, bucket)` once at import time and cache in a module-level `Map`. (b) For live mode, ensure `street_readings_15m` materialized view already does the aggregation; never fetch raw `sensor_readings` in the hot path.

### `streets-mock.ts` recomputes full dataset on every request

- Location: `dashboard/src/lib/repo/streets-mock.ts` — every method calls `loadStreets()`, `loadCoverage()`, `loadReadings()` with no memoization.
- Severity: **low** (mock-only)
- Description: In Vercel Fluid Compute instance reuse this is hot-cached, but a cold start re-parses the JSON fixtures. For v1 mock mode the latency hit is negligible; noted because the same shape will exist in the live repo if copy-pasted.
- Remediation: Wrap `loadStreets/Coverage/Readings` in `React.cache` (`import { cache } from 'react'`) so a single request reuses one read.

### Long-lived MapLibre canvas debug logs in production

- Location: `dashboard/src/components/map/StreetMap.tsx:66-78,177-199` — `console.info` on every mount, every resize, and on map ready.
- Severity: **low**
- Remediation: Gate behind `process.env.NODE_ENV !== "production"`.

### MapLibre bounds unconstrained

- Location: `dashboard/src/components/map/StreetMap.tsx:83-120`
- Severity: **medium**
- Description: The map has `minZoom: 12, maxZoom: 18` but **no `maxBounds`**. A user who pans west will see solid white (tiles 404) and may refresh, retriggering the mount race. Combined with the fact that `download-dublin-tiles.mjs` covers only `-6.31…-6.20 × 53.32…53.38`, this is both a perf and a UX issue.
- Remediation: Add `maxBounds: [[-6.40, 53.28], [-6.10, 53.42]]` (or derive from the tile download bbox) to physically clamp panning.

---

## 5. Abandoned / Legacy Folders

### `bkp/` — legacy backup folder

- Location: `bkp/presentation_ai_gen.pdf` (4.7 MB)
- Severity: **low**
- Description: Gitignored (`.gitignore:25`) and excluded from the repo, but still exists on disk with a single 4.7 MB PDF from February 2025. Nothing references it.
- Remediation: Delete the folder (`rm -rf bkp/`). It's not tracked, so no history loss.

### `img/wrong_label/` — legacy misclassification examples

- Location: `img/wrong_label/example1.jpg`, `example1_adjusted.jpg`, `example2.jpg`, `example2_adjusted.jpg` (~525 KB, tracked in git)
- Severity: **low**
- Description: Four cyclist-misclassification example images from before CAMINAv1 shipped. `docs/BUGS.md §1` marks the bug as RESOLVED. These are now documentation-only.
- Remediation: Either move to `docs/assets/cyclist-misclassification-examples/` and reference them from `docs/BUGS.md`, or delete if no longer cited.

### `src/dev/` — development-only scripts

- Location: `src/dev/` (referenced in `README.md:37-41`: `camera_position_check.py`, `lowlight_counter.py`, `motion_detector.py`, `plugged_counter.py`)
- Severity: **low**
- Description: Not loaded by Plan 01's `SensorDaemon`. Some of these (`camera_position_check.py`, `motion_detector.py`, `near_misses_detect.py`, `accident_detect.py`) are marked as "Implement" TODOs in `docs/TODO.md:6-10`. Status unclear: stubs? prototypes? working but unwired?
- Remediation: Audit each file, delete dead stubs, promote working ones into `src/camina/service/` with tests.

### `dashboard/scripts/camina-preview.png` — diagnostic screenshot committed

- Location: `dashboard/scripts/camina-preview.png` (1.25 MB, tracked)
- Severity: **low**
- Description: Output of `inspect-map.mjs` (Playwright screenshot). Useful for PR previews but adds 1.25 MB to history for a file that regenerates. Already in git.
- Remediation: Either add `dashboard/scripts/camina-preview.png` to `.gitignore` and remove from the index, or keep intentionally as a "last-known-good render" snapshot and document so in a `scripts/README.md`.

### `paper/`, `model/`, `runs/` — near-empty directories

- Location: `paper/` (12 KB), `model/` (12 KB), `runs/` (12 KB)
- Severity: **low**
- Description: Small placeholder folders. Status unclear without content audit.
- Remediation: If unused, remove. If placeholders for future artefacts, add a `README.md` explaining intent.

---

## 6. Reproducibility Risks

### `environment.yml` vs `requirements.txt` drift

- Location: `environment.yml` (12 lines, Python 3.10, 5 pip packages: torch, torchvision, ultralytics, opencv-python, filterpy) vs. `requirements.txt` (43 lines with pinned versions including numpy 2.2.5, torch 2.7.1, torchvision 0.22.0, opencv 4.11.0.86, ultralytics 8.3.123)
- Severity: **medium**
- Description: `environment.yml` pins nothing, `requirements.txt` pins everything. Running `conda env create -f environment.yml` and `pip install -r requirements.txt` yield wildly different environments. The README recommends either interchangeably (`README.md:94-101`).
- Remediation: Pick one source of truth. Recommend `uv` + `pyproject.toml` (per your global config), or at least regenerate `environment.yml` from a pinned `requirements.txt` and pin its pip deps.

### `requirements_calibration.txt` — unused extra dependency file

- Location: `requirements_calibration.txt` (17 lines, partially overlapping with `requirements.txt`: torch, torchvision, opencv-python, Pillow, numpy; plus scikit-image, transformers, timm)
- Severity: **medium**
- Description: Separate requirements file for the calibration module (`src/camina/utils/calibration.py`). Comments reference `Depth-Anything-V2` from GitHub (commented out). Not referenced from any documentation. May or may not still be needed.
- Remediation: Consolidate into `requirements.txt` with a `[calibration]` extras section in `pyproject.toml`, or delete if the calibration dependency is superseded by something already in `requirements.txt`.

### No lock file for Python dependencies

- Location: repo root (no `poetry.lock`, no `uv.lock`, no `pip-tools` `requirements.lock`)
- Severity: **medium**
- Description: `requirements.txt` has version pins but no hashes and no transitive-dependency lock. Rebuilding the exact environment a year from now is fragile (especially for `ultralytics` + `torch` + `numpy`, whose minor versions frequently break each other).
- Remediation: Adopt `uv lock` (per your user config preferring uv). Ship `uv.lock`. Also pin Python version explicitly (`.python-version` file).

### Dashboard: `pnpm-lock.yaml` present, no root `.nvmrc`

- Location: `dashboard/.nvmrc` present, `dashboard/pnpm-lock.yaml` present. No `.nvmrc` at repo root.
- Severity: **low**
- Description: Dashboard reproducibility is fine. Repo root has no Node declaration, which is consistent (root is Python-only), but means scripts that cross the boundary are ambiguous.
- Remediation: No action required.

### Test video in git (`tests/test.mov`, 23 MB)

- Location: `tests/test.mov`
- Severity: **low**
- Description: Used as the default `camera_source` in `configs/main_config.yaml:157`. Keeps tests reproducible, but bloats clones.
- Remediation: Git LFS or external storage with checksum, referenced from `tests/README.md`.

---

## 7. Documentation Gaps

### Stale legacy `docs/TODO.md`

- Location: `docs/TODO.md`
- Severity: **low**
- Description: Pre-restructure TODO list (LoRaWAN, IR, near-miss, accident detection, RPi testing). Items overlap with `TODO.md §Legacy Camina TODO` which already supersedes it. Unclear which is authoritative.
- Remediation: Delete `docs/TODO.md` (its items live in `TODO.md:158-168`) or convert to an issue tracker link.

### `README.md` describes pre-restructure layout

- Location: `README.md:24-56`
- Severity: **medium**
- Description: The directory structure in `README.md` lists `src/camina/{app.py, core/tracker.py, utils/…}` and `src/dev/` + `src/utils/` + `src/speed_estimation.py`. It does **not** mention the Plan 01 additions: `src/camina/core/counter.py`, `src/camina/io/`, `src/camina/service/sensor_daemon.py`, `configs/sensor.yaml`, `deploy/systemd/`, `docs/PROTOCOL.md`, `docs/RECONCILIATION.md`, `docs/sensor_deployment.md`. It also doesn't mention the `dashboard/` subproject at all.
- Remediation: Regenerate the directory tree and usage section; add a pointer to `plan/01-*.md` and `plan/02-*.md` as the authoritative design docs.

### `docs/BUGS.md` lists only resolved bugs

- Location: `docs/BUGS.md`
- Severity: **low**
- Description: Two entries, both RESOLVED/MITIGATED. No recent-fragile-areas content; the MapLibre race, the live-repo stub, the dev-admin flag risk, and the 501-live-mode routes are not captured here. The file pre-dates the Plan 01/02 work.
- Remediation: Either update `docs/BUGS.md` with the current fragile areas (see §1 of this document) or point it at `TODO.md` and delete it.

### `docs/CODE_STYLE.md`, `docs/MODELS.md`, `docs/CALIBRATION_SETUP.md`, `docs/EQUIPMENTS.md`

- Location: `docs/*` (dated 2026-04-02 per file mtimes — pre-restructure)
- Severity: **low**
- Description: Have not been touched since the 2026-04-02 restructure commit. Likely still accurate for the legacy pipeline but never cover `src/camina/core/counter.py`, `src/camina/io/*`, or the dashboard. No doc audit has happened since the big merge `9efbb7a`.
- Remediation: Add a "Last verified against commit <sha>" footer to each doc and refresh them alongside the next Plan 01 production wiring.

### `plan/02-dashboard-vercel.md` is authoritative but very long

- Location: `plan/02-dashboard-vercel.md` (43 743 bytes)
- Severity: **low**
- Description: Single 43 KB plan document; hard to diff as implementation progresses. `TODO.md` tracks status against it but the plan itself isn't updated with checkmarks.
- Remediation: Add a short "Implementation status" box at the top of `plan/02-*.md` that links to `TODO.md §Plan 02`, and an "Updated: YYYY-MM-DD" marker after each section.

### No `CHANGELOG.md`, no `CONTRIBUTING.md`, no `LICENSE` summary in README

- Location: root (`LICENSE` exists, 189 B; no CHANGELOG; no CONTRIBUTING)
- Severity: **low**
- Description: For a research project this is acceptable, but the 189-byte `LICENSE` is too short to identify (probably one of MIT/Apache/BSD but worth verifying).
- Remediation: Add a SPDX identifier to the top of source files or a `LICENSE.md` line in README.

---

## 8. Test Coverage Gaps

### Python edge agent — solid coverage

- Location: `tests/` — 60 unit+integration tests per `TODO.md:12` (`test_windowed_counter.py`, `test_daily_accumulator.py`, `test_offline_buffer.py`, `test_https_publisher.py`, `test_config_poller.py`, `test_sensor_daemon.py`)
- Severity: **low**
- Description: Core agent logic is well-tested.
- Remediation: Add an integration test against a fake HTTPS server (or a Vercel preview) per `TODO.md:28-29`.

### Dashboard — thin coverage

- Location: `dashboard/tests/unit/` (2 files: `schemas.test.ts`, `privacy-regression.test.ts`); `dashboard/tests/e2e/public-map.spec.ts` (1 Playwright spec)
- Severity: **medium**
- Description: Privacy regression is good. Schema tests exist. No unit tests for `streets-mock.ts` aggregation math (count-weighted running-mean speed at `streets-mock.ts:92-101` and `:154-163` is non-trivial), no tests for the MapLibre hooks (`useMapQuery`, `useMapHash`), no tests for `requireAdmin` role extraction, no tests for `ingest-auth` / `cron-auth` guards. Playwright E2E works locally only (`TODO.md:139`).
- Remediation: (a) Unit-test `latestMetrics` with fixtures covering empty, single-sensor, multi-sensor-per-street, and class-filter cases. (b) Test `ingest-auth` and `cron-auth` positive + negative paths. (c) Extend the privacy regression to hit `/api/admin/streets/[id]/info` with no session and assert 401.

### No tests for the legacy `src/camina/app.py` or `src/speed_estimation.py`

- Location: `src/camina/app.py` (13 KB); `src/speed_estimation.py` (5.9 KB, broken import)
- Severity: **low** (legacy code)
- Remediation: Either retire these files (see §2) or add smoke tests.

### No CI pipeline visible

- Location: no `.github/workflows/`, no `.gitlab-ci.yml`
- Severity: **medium**
- Description: Tests exist and pass locally; nothing enforces them on PRs. The 2026-04-22 commit `c3b6886` message is `test: showing the github workflow to guill` but no workflow file is in the tree.
- Remediation: Add `.github/workflows/ci.yml` that runs `pytest tests/` (Python) and `pnpm --dir dashboard run typecheck && pnpm --dir dashboard test` on every PR.

---

*Concerns audit: 2026-04-23*
