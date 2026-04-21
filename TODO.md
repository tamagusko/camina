# CAMINA — TODO

Snapshot on 2026-04-21. See `plan/01-windowed-counter-and-ingest.md` and
`plan/02-dashboard-vercel.md` for the authoritative implementation plans.

Legend: ✅ done · 🟡 partial · ⬜ not started

---

## ✅ Plan 01 — Edge agent (HTTPS ingest)

All 8 steps merged. **60 unit + integration tests passing.**

- ✅ `WindowedCounter` (`src/camina/core/counter.py`)
- ✅ `DailyAccumulator` with SQLite persistence
- ✅ `OfflineBuffer` (WAL SQLite FIFO outbox, cap + drop-oldest)
- ✅ `HttpClient` + `HttpsPublisher` (`src/camina/io/*`)
- ✅ `ConfigPoller` (version-gated hot-reload)
- ✅ `SensorDaemon` composed orchestrator (`src/camina/service/sensor_daemon.py`)
- ✅ `configs/sensor.yaml` start-up config template
- ✅ `deploy/systemd/camina-sensor.service`
- ✅ `docs/PROTOCOL.md`, `docs/RECONCILIATION.md`, `docs/sensor_deployment.md`

### Remaining edge-agent polish

- ⬜ Production entry point that composes `SensorDaemon` with the existing
  YOLO + SORT pipeline (outlined in `docs/sensor_deployment.md §6` —
  needs a concrete `scripts/run_sensor.py` when hardware provisioning starts)
- ⬜ Integration test against a deployed Vercel preview with one real sensor
- ⬜ Short-lived JWT auth for TRL 6+ (currently opaque Bearer token)
- ⬜ Firmware OTA pipeline (TRL 7)

---

## 🟡 Plan 02 — Dashboard on Vercel

Scaffolded end-to-end in **mock mode**. Runs locally at
<http://localhost:3000/dublin> (see Quick-start below).

### ✅ Working today (mock mode, no DB, no OAuth)

- `dashboard/` scaffolded: Next.js 16 + Tailwind + Drizzle + hand-rolled UI
- Uber-style monochrome theme from `DESIGN.md`
- Public street map with MapLibre + local Carto Positron tiles (60 MB,
  zooms 12–18) served from `dashboard/public/tiles/`
- URL query scheme `?zoom=14&lat=…&lon=…` (self-documenting, shareable)
- ResizeObserver + inline `position: absolute; inset: 0` on the map
  container (handles DevTools docking, window resize, strict-mode edge cases)
- `MetricToggle` / `ClassFilter` / `TimeWindowPicker` / `ColourLegend`
- Street-click side panel showing:
  - total count, avg speed
  - per-class count + speed breakdown sorted by count
  - **admin strip** (dev-only via `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`)
    with sensor ID, GPS, install date, firmware, config version, last heartbeat
- Colour-blind-safe ramps: viridis (counts), cividis (speed) + coalesce
  guard so null `feature-state` doesn't crash MapLibre paint
- Ingest API stubs (`/api/ingest/sensors/[id]/{counts,daily,heartbeat,config}`)
  with Bearer auth, zod validation, mock-mode accepting responses
- Admin sensor-info API (`/api/admin/streets/[id]/info`) gated by
  `requireAdmin()` in live mode
- Cron routes (`/api/cron/*`) stubbed with `VERCEL_CRON_SECRET` auth
- Privacy regression test + schema tests (Vitest)
- Playwright config + smoke test
- Diagnostic scripts: `dashboard/scripts/{inspect-map,open-preview,download-dublin-tiles}.mjs`

### ⬜ Not yet implemented

1. **Neon Postgres connection** (Step D3 live half)
   - Create Neon project via Vercel Marketplace
   - Run `dashboard/drizzle/migrations/0000_init.sql`
   - Implement `dashboard/src/lib/repo/streets-live.ts` (currently throws)
   - Finish `dashboard/src/lib/db.ts` (Drizzle client scaffolded, queries TBD)

2. **Google OAuth wiring** (Step D2 live half)
   - Create OAuth client in Google Cloud Console
   - `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env.local` and
     later via `vercel env add`
   - Populate `allowed_members` table on the live DB
   - Replace `CAMINA_DEV_ALLOWED_EMAILS` env-var fallback in `lib/auth.ts`
     with live DB lookup

3. **Admin CRUD UIs** (Steps D9–D10)
   - `<SensorForm>` create/edit with GPS fields (admin-only)
   - `<StreetDrawTool>` to click OSM ways and save coverage
   - `/admin/members` invite / revoke / role UI
   - `PATCH /api/admin/sensors/[id]` — update config, bump `config_version`,
     write audit row
   - UI "awaiting device ack" → "✓ applied" indicator driven by next heartbeat

4. **Events + reconciliation + audit** (Step D11)
   - `/admin/events` list backed by cron output
   - Acknowledge / dismiss workflow
   - `/admin/audit` filterable log view

5. **Cron implementations** (Step D12)
   - `REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m` then hourly
   - Silent-sensor detection (`last_heartbeat < NOW() - 15min` → insert event)
   - Daily reconciliation per `docs/RECONCILIATION.md`

6. **Security / observability** (Step D13)
   - Vercel BotID on `/sign-in` and admin mutations
   - CSP + HSTS headers via `vercel.ts` (basic headers already there; CSP TBD)
   - Upstash Ratelimit on `/api/admin/*` and per-sensor `/api/ingest/*`
   - Sentry (client + server) with PII scrubber
   - Speed Insights + Analytics enabled
   - Uniform route-handler logging wrapper

7. **Deploy** (Step D14)
   - `pnpm add -g vercel@latest` (CLI is currently 50.44.0, latest 51.8.0)
   - `vercel link` → link to the project
   - `vercel env add` every key from `dashboard/.env.example` (preview + prod)
   - Enable Rolling Releases (10 % → 50 % → 100 % with health gates)
   - Auto-rollback on error spike
   - Uptime monitor on `/api/health`
   - `dashboard/docs/RUNBOOK.md`

8. **Street detail page polish** (`/[city]/street/[slug]`)
   - Mirror the side-panel richness (total, avg speed, class table) above
     the time-series chart
   - Time-range selector (1 h / 24 h / 7 d / 30 d)
   - Admin strip on the detail page for logged-in admins

9. **Mobile UX polish** (per plan 02 §9-bis)
   - Bottom-sheet with 3 snap points (peek / half / full) on < 600 px
   - Verify 44×44 px tap targets on every control
   - Reduced-motion fallback audit

10. **A11y** (WCAG 2.1 AA)
    - Keyboard-reachable map controls (shortcuts `M`, `C`, `T`, `Esc`, `?`)
    - ARIA live region for metric-toggle announcements
    - Protanopia / Deuteranopia preview toggle on `/admin`

11. **i18n** (v1.1)
    - `next-intl` scaffold
    - English + Portuguese

12. **Tests**
    - Integration tests against a Dockerized Postgres + PostGIS for live repo
    - Playwright E2E against a preview deploy (currently only works locally)
    - Privacy regression extended to admin routes (ensure they 401 without session)

---

## House-keeping

- ⬜ Re-enable `reactStrictMode: true` in `dashboard/next.config.mjs` once
  MapLibre init is fully guarded (ResizeObserver + inline styles in place;
  strict-mode still off as a safety net)
- ⬜ Re-enable `cacheComponents: true` in `dashboard/next.config.mjs` once
  `/[city]` and `/[city]/street/[slug]` wrap uncached reads in `<Suspense>`
- ⬜ Remove the temporary `[CAMINA] ancestor heights` diagnostic log in
  `StreetMap.tsx` once we stop debugging canvas sizing
- ⬜ Switch `dashboard/src/lib/auth.ts` dev allowlist to a live DB lookup when
  Neon is connected
- ⬜ `dashboard/public/tiles/` is gitignored — run
  `pnpm exec node scripts/download-dublin-tiles.mjs` on a fresh clone

---

## Legacy Camina TODO (from before the restructure)

These items pre-date the Plan 01 / Plan 02 work and may already be partly
addressed by the new pipeline. Kept here for traceability.

- ⬜ Average Speed Detection at logging-interval granularity
- ⬜ Auto-labeling for new classes (e-scooter, delivery van, SUV)
- ⬜ Hardware compatibility & assembly guide

---

## Quick-start (for tomorrow)

```bash
# Dashboard (mock mode, no DB needed)
cd dashboard
pnpm install                                       # first time only
pnpm exec node scripts/download-dublin-tiles.mjs   # first time only, ~60 MB
pnpm dev                                           # → /dublin

# Edge-agent tests (repo root)
pytest tests/                                      # 60 tests, ~0.3 s

# Preview screenshot (headless, handy while on the train)
cd dashboard
pnpm exec node scripts/inspect-map.mjs             # → scripts/camina-preview.png
```
