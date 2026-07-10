# Plan 02 — CAMINA Dashboard on Vercel (fully serverless)

**Branch:** `main`
**Status:** Draft — awaiting approval
**Owner:** Tiago Tamagusko
**Created:** 2026-04-21 (revised to serverless 2026-04-21)
**Depends on:** Plan 01 (edge HTTPS publisher)
**Design authority:** `DESIGN.md` (to be authored by Tiago). Where this plan and `DESIGN.md` disagree, **`DESIGN.md` wins**. This plan defines *what* is built and *how* it fits the Vercel platform; `DESIGN.md` defines *how it looks and feels*.

> **History:** earlier draft assumed an MQTT broker and a VPS-hosted ingestor. Revised after we chose plain HTTPS in Plan 01. The whole stack is now **Vercel Functions + managed Postgres (Neon via Vercel Marketplace)** — no VPS, no separate ingestor service.

---

## 0. Design Principles (binding until `DESIGN.md` supersedes)

- **Basemap:** OpenStreetMap via **Protomaps PMTiles** (pure-OSM, OSS, single-file vector tiles, no per-request billing).
- **Primary visualization:** **streets coloured by the selected metric** — not sensor pins, not popups anchored to a GPS point.
- **Privacy by design (GDPR):** the public UI **never exposes exact sensor GPS**. Sensors are an admin-only concept; the public surface speaks only in terms of *streets*. If one sensor covers one street, the public representation is still the *street*, never the sensor.
- **Metrics:** user chooses **Counts** or **Speed** (mutually exclusive). Secondary controls refine (class filter, time window).
- **UX intent:** clean, flat, minimal chrome. Map is the canvas; controls float on top and collapse when not in focus.
- **URL state:** shareable via path + query + hash (§11). Raw coordinates never appear as a *path* segment.
- Colour ramps, typography, icons, copy — deferred to `DESIGN.md`.

## 1. Goal

Ship the public dashboard and the admin console envisioned in slide 10 of the INTERREG deck, applying §0:

- A **Dublin map with OSM basemap** where **streets that host CAMINA sensors are coloured by the selected metric** (counts or speed).
- **Metric toggle** (Counts ↔ Speed), road-user **class filter** (person, cyclist, car, …), **time window** selector (Now / 1 h / 24 h / 7 d).
- Click a street → side panel with the **street** name, per-class breakdown, time-series chart. **No sensor ID, no coordinates.**
- **Admin console** (Google sign-in, allow-listed emails) to register sensors, map each sensor to one or more **street segments**, configure the publish interval (stored in DB; devices pick up on next publish via `config_version` check — Plan 01 §3.7), and view heartbeats, reconciliation, audit.
- Near-real-time freshness: UI ≤ 15 min (matches the edge window size).

Published on **Vercel** using **Next.js 16 App Router**.

## 2. Non-Goals

- Mobile app.
- Anonymous public access in v1 (sign-in + allowlist required).
- ML predictions (separate plan).
- Exposure of raw sensor GPS to non-admin users.

## 3. Why Vercel

- Zero-config Next.js deployments with Git-based previews per PR.
- **Fluid Compute** default runtime: Node.js, 300 s timeouts, instance reuse.
- **Rolling Releases** (GA 2025-06) for safe production rollouts.
- Native **Marketplace** integrations for Postgres (Neon), Redis (Upstash), observability.
- **Vercel Cron** for scheduled jobs (materialized view refresh, silent-sensor detection).
- **Vercel Analytics + Speed Insights** out of the box.

## 4. Architecture — Fully Serverless

```
┌─────────────────┐  HTTPS POST  ┌────────────────────────────────┐
│  RPi5 Sensors   │ ───────────▶ │  Next.js 16 on Vercel          │
│  (Plan 01)      │              │                                │
│  httpx client   │              │  /api/ingest/*  (device-facing)│
│                 │ ◀─────────── │  /api/streets/* (public)       │
└─────────────────┘  GET /config │  /api/admin/*   (admin)        │
                                 │                                │
                                 │  Vercel Cron                   │
                                 │    */5  → refresh aggregates   │
                                 │    */15 → silent-sensor checks │
                                 │    0 1  → reconciliation       │
                                 └────────────┬───────────────────┘
                                              │ SQL over TLS
                                              ▼
                                 ┌────────────────────────────────┐
                                 │  Neon Postgres + PostGIS       │
                                 │  (Vercel Marketplace)          │
                                 │  - sensors, streets, coverage  │
                                 │  - sensor_readings (indexed)   │
                                 │  - street_readings_15m (MV)    │
                                 │  - audit_log, allow list       │
                                 └────────────────────────────────┘
```

- **No VPS.** No broker. No separate ingestor service.
- **One code artifact** (Next.js) handling both device ingest and user UI.
- **One database** (Neon Postgres with PostGIS).
- **Cron jobs** replace long-running background workers.

## 5. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Next.js 16 App Router | Vercel default; Cache Components + PPR |
| Language | TypeScript (strict) | Type safety, DX |
| Runtime | Fluid Compute (default), Node.js 24 | Current Vercel defaults |
| Config | `vercel.ts` (typed) | Replaces `vercel.json`; crons declared here |
| Bundler | Turbopack | Next.js 16 default |
| Styling | Tailwind CSS v4 | Standard; shadcn-compatible |
| UI primitives | shadcn/ui | Accessible; theme from `DESIGN.md` |
| Basemap | MapLibre GL JS + **OSM via Protomaps PMTiles** | Pure-OSM, OSS, single-file vector tiles, cache-friendly |
| Data overlay | MapLibre `line` layer with data-driven paint | Streets coloured by selected metric |
| Geometry | PostGIS server-side; `@turf/turf` client-side | Snap GPS→way, simplify, bbox |
| Auth | **Auth.js v5** + **Google provider only** + Drizzle adapter | Google Workspace covers UCD + partners; free |
| Allowlist | DB-backed `allowed_members` + `allowed_domains` | Admin invites without re-deploy |
| Database | **Neon Postgres + PostGIS** (Vercel Marketplace) | Serverless; branch-per-preview; TLS; PostGIS supported |
| DB client | Drizzle ORM | Typed, light, good PostGIS support |
| Rate limiting | Upstash Ratelimit (Marketplace) | Protect ingest + admin endpoints |
| Validation | `zod` | Client/server shared schemas |
| Bot protection | **Vercel BotID** on sign-in + admin mutations | GA 2025-06 |
| Observability | Vercel Analytics + Speed Insights + Sentry | Standard set |
| Tests | Vitest (unit) + Playwright (E2E on preview) | Fast + Vercel-native |
| Env vars | `vercel env pull / add` | Per environment |

**Why Neon over Supabase?** — Neon is a pure-Postgres-on-Vercel-Marketplace product; no bundled auth/storage to reason about. Auth.js + Google is enough for us. Supabase also works (both support PostGIS) — pick Neon unless we later want Supabase Storage for PMTiles or Supabase Realtime.

**Why no TimescaleDB?** — Our volume is small (≤ ~2 M reading rows/year). Vanilla Postgres with sensible indexes and a 15-min materialized view refreshed by Vercel Cron is plenty. If we scale past ~10 M rows/year, revisit.

## 6. Information Architecture

```
PAGES
/                              Redirects to default city (e.g. /dublin)
/[city]                        Public street map (sign-in + allowlist)
/[city]/street/[slug]          Street detail — metric chart + class breakdown (no sensor info)
/admin                         Admin home (role=admin)
/admin/sensors                 Register / edit sensors (GPS admin-only)
/admin/sensors/[id]            Per-sensor config: interval, zone, street coverage, notes
/admin/streets                 Manage street catalogue
/admin/members                 Google sign-in allow list
/admin/events                  Silent sensors, reconciliation failures, audit

DEVICE-FACING API  (Bearer token per device)
POST /api/ingest/sensors/[id]/counts
POST /api/ingest/sensors/[id]/daily
POST /api/ingest/sensors/[id]/heartbeat
GET  /api/ingest/sensors/[id]/config

PUBLIC API  (session required; no GPS, no sensor_id in responses)
GET  /api/streets
GET  /api/streets/[id]
GET  /api/streets/[id]/readings?metric=counts|speed&class=…&from=…&to=…&bucket=…
GET  /api/health

ADMIN API  (session + role=admin)
GET/POST     /api/admin/sensors
GET/PATCH/DELETE /api/admin/sensors/[id]
POST/DELETE  /api/admin/sensors/[id]/coverage
GET/POST/PATCH/DELETE /api/admin/streets
GET/POST/DELETE /api/admin/members
GET          /api/admin/audit

CRON
/api/cron/refresh-aggregates   every 5 min
/api/cron/detect-silent        every 15 min
/api/cron/reconcile-daily      01:00 UTC
```

Admin config changes only touch the DB. Devices learn of changes on their next POST when the response's `latest_config_version` differs — then they call GET `/config`. No persistent connection needed anywhere.

## 7. Privacy Model (GDPR-facing)

- **Only two public identifiers exist:** `street_id` and `class_name`.
- **Sensor rows never leave the admin boundary.** No non-admin API response contains `sensor_id`, `latitude`, or `longitude`. Automated **privacy regression test** in CI asserts this for every public response body.
- **Street-level invariant (single-sensor case):** even with one sensor per street, the public representation is the *street*'s aggregate.
- **Aggregation rule (multi-sensor case):** counts summed; speeds count-weighted-averaged.
- **k-sensor guard:** if a street has ever had only one covering sensor and that sensor is now removed/idle, the street is dropped from `/api/streets` until a new sensor is mapped — prevents inferring sensor location from addition/removal events.
- **Audit log** on every admin action touching GPS or coverage.
- **Retention:** raw `sensor_readings` 13 months; materialized aggregates indefinitely. Deleting a sensor deletes its raw rows but preserves street-level aggregates (no sensor reference).

## 8. Database Schema (Neon Postgres + PostGIS)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

-- ── Admin-only ─────────────────────────────────────────────────────
CREATE TABLE sensors (
  id                TEXT PRIMARY KEY,
  display_name      TEXT NOT NULL,
  latitude          DOUBLE PRECISION NOT NULL,     -- ADMIN-ONLY
  longitude         DOUBLE PRECISION NOT NULL,     -- ADMIN-ONLY
  install_date      DATE NOT NULL,
  active            BOOLEAN NOT NULL DEFAULT TRUE,
  config_json       JSONB NOT NULL,
  config_version    TEXT NOT NULL,                 -- opaque version (e.g. short hash)
  last_heartbeat    TIMESTAMPTZ,
  fw_version        TEXT,
  notes             TEXT,
  api_token_hash    TEXT NOT NULL,                 -- bcrypt/argon2; raw token never stored
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE streets (
  id                TEXT PRIMARY KEY,              -- slug, e.g. 'dame-st-grafton-to-trinity'
  display_name      TEXT NOT NULL,
  osm_way_ids       BIGINT[] NOT NULL,
  geom              GEOMETRY(MultiLineString, 4326) NOT NULL,
  bbox              GEOMETRY(Polygon, 4326) NOT NULL,
  city              TEXT NOT NULL,
  active            BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_streets_geom ON streets USING GIST (geom);
CREATE INDEX idx_streets_bbox ON streets USING GIST (bbox);
CREATE INDEX idx_streets_city_active ON streets (city, active);

CREATE TABLE sensor_street_coverage (
  sensor_id   TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  street_id   TEXT NOT NULL REFERENCES streets(id) ON DELETE RESTRICT,
  weight      REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (sensor_id, street_id)
);
CREATE INDEX idx_coverage_street ON sensor_street_coverage (street_id);

-- ── Readings (partitioned, not hypertable) ────────────────────────
CREATE TABLE sensor_readings (
  sensor_id         TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  window_start      TIMESTAMPTZ NOT NULL,
  window_end        TIMESTAMPTZ NOT NULL,
  class_name        TEXT NOT NULL,
  count             INTEGER NOT NULL,
  avg_speed_kmh     REAL,
  partial           BOOLEAN NOT NULL DEFAULT FALSE,
  received_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sensor_id, window_start, class_name)
) PARTITION BY RANGE (window_start);

-- Monthly partitions, created by a cron job 1 month ahead of time.
CREATE INDEX idx_readings_window_start ON sensor_readings USING BRIN (window_start);
CREATE INDEX idx_readings_sensor_window ON sensor_readings (sensor_id, window_start);

CREATE TABLE sensor_daily_totals (
  sensor_id     TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  day           DATE NOT NULL,
  totals_json   JSONB NOT NULL,
  window_count  INTEGER NOT NULL,
  late          BOOLEAN NOT NULL DEFAULT FALSE,
  reconciled    BOOLEAN NOT NULL DEFAULT FALSE,
  mismatch_json JSONB,
  received_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sensor_id, day)
);

CREATE TABLE sensor_heartbeats (
  sensor_id        TEXT NOT NULL,
  ts               TIMESTAMPTZ NOT NULL,
  uptime_s         INTEGER,
  cpu_temp_c       REAL,
  last_window_end  TIMESTAMPTZ,
  config_version   TEXT,
  PRIMARY KEY (sensor_id, ts)
);
-- Short retention enforced by a cron that deletes rows older than 14 days.

-- ── Public aggregates (no sensor_id exposed) ──────────────────────
CREATE MATERIALIZED VIEW street_readings_15m AS
SELECT
  c.street_id,
  r.class_name,
  date_trunc('minute',
             r.window_start - (EXTRACT(MINUTE FROM r.window_start)::int % 15) * INTERVAL '1 minute'
             ) AS bucket,
  SUM(r.count) AS total_count,
  CASE WHEN SUM(r.count) > 0
       THEN SUM(r.avg_speed_kmh * r.count) / NULLIF(SUM(r.count), 0)
       ELSE NULL END AS avg_speed_kmh
FROM sensor_readings r
JOIN sensor_street_coverage c ON c.sensor_id = r.sensor_id
GROUP BY c.street_id, r.class_name, bucket;
CREATE UNIQUE INDEX uidx_street_15m ON street_readings_15m (street_id, class_name, bucket);

CREATE MATERIALIZED VIEW street_readings_hourly AS
SELECT street_id, class_name,
       date_trunc('hour', bucket) AS hour,
       SUM(total_count) AS total_count,
       AVG(avg_speed_kmh) AS avg_speed_kmh
FROM street_readings_15m
GROUP BY street_id, class_name, date_trunc('hour', bucket);
CREATE UNIQUE INDEX uidx_street_hour ON street_readings_hourly (street_id, class_name, hour);

-- Refreshed by /api/cron/refresh-aggregates every 5 min (CONCURRENTLY on 15m, then hourly).

-- ── Auth (Auth.js + Google) ───────────────────────────────────────
CREATE TABLE allowed_members (
  email         TEXT PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('admin','viewer')),
  invited_by    TEXT,
  invited_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE allowed_domains (
  domain        TEXT PRIMARY KEY,
  default_role  TEXT NOT NULL CHECK (default_role IN ('admin','viewer'))
);
-- Auth.js standard tables created by Drizzle adapter.

CREATE TABLE audit_log (
  id          BIGSERIAL PRIMARY KEY,
  actor_email TEXT NOT NULL,
  action      TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  payload     JSONB,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_actor_ts ON audit_log (actor_email, ts DESC);
```

## 9. Rendering Strategy (Next.js 16 Best Practices)

- **Cache Components + PPR:** static shell (map canvas, nav, control rail) prerendered; dynamic data (street metrics, legend) streamed in `<Suspense>`.
- **`use cache` directive** with tags (`street:{id}`, `streets:list`, `street:{id}:bucket:{window}`) on DB reads. `revalidateTag` fires on admin writes and at the end of each cron refresh cycle.
- **Route segment `export const revalidate = 60`** on street detail pages.
- **Client polling** at 60 s for the latest-bucket tile. Metric/class/time changes recompute the paint client-side from already-fetched data where possible.
- **Map rendering pipeline:**
  1. Basemap: Protomaps PMTiles served from `/api/basemap/[z]/[x]/[y].pbf` (proxied through Vercel, edge-cached) **or** directly from Vercel Blob URL.
  2. Streets GeoJSON: single bounded-bbox fetch from `/api/streets`.
  3. Metrics: keyed `Map<street_id, value>` fetched per window; joined client-side via MapLibre `feature-state`.
  4. Colour ramp: 5-stop linear scale driven by `paint.line-color: ['interpolate', ['linear'], ['feature-state', 'metric'], …]` — ramp stops from `DESIGN.md`.
- **No Edge Functions.** Middleware and API routes run on Fluid Compute with full Node.js.

## 9-bis. Mobile-first UX

The map is the primary interface, including on small screens. Design for
375 × 667 px first; scale up. Binding rules:

### Layout at small screens (≤ 600 px)

- **Full-bleed map**, edge-to-edge, no margins.
- **Single floating bottom bar** replaces all top controls. One row, horizontally scrollable if needed:
  `[Metric pill ◎] [Class chip] [Time chip] [Legend toggle]`
- Each control is a 44 × 44 px tap target minimum (matches `DESIGN.md` §8).
- The mock-data pill moves to the **top-centre** as a thin capsule so it doesn't collide with system chrome (notch / status bar).
- No hover-dependent states. All interactions must be tap-reachable.

### Side panel → bottom sheet

On ≤ 600 px, `<StreetSidePanel>` becomes a **bottom sheet** with three snap points:

| Snap | Height | Content |
|---|---|---|
| Peek | 80 px | Street name + current metric value only |
| Half | 50 vh | + class breakdown + 1 h sparkline |
| Full | 92 vh | + full time-series chart + reconciliation note |

- Drag handle (3 × 40 px capsule) at the top of the sheet.
- While sheet is open at ≥ Half, map gestures are disabled on the covered region; a single-finger swipe on the visible top third still pans the map so users aren't trapped.
- Hardware back button / swipe-back dismisses the sheet before leaving the page.

### Hit-testing street lines

A 2 m-wide line on a phone is nearly impossible to tap accurately. Therefore:

```
// components/map/StreetMap.tsx
map.addLayer({
  id: 'streets-visible',
  type: 'line',
  source: 'streets',
  paint: { 'line-color': <metric-driven>, 'line-width': 4 },
  interactive: false,
});
map.addLayer({
  id: 'streets-hit',      // invisible wider hitbox
  type: 'line',
  source: 'streets',
  paint: { 'line-color': 'transparent', 'line-width': 22 },
  interactive: true,
});
map.on('click', 'streets-hit', openStreetSheet);
```

The invisible 22 px-wide layer is forgiving for fingers without disturbing the
clean visual.

### Map gestures

- **One-finger drag:** pan.
- **Pinch:** zoom.
- **Double-tap:** zoom in.
- **Two-finger tap:** zoom out.
- **Long-press:** no-op (reserved for future context menu).
- **Rotate/tilt:** disabled in v1 (keep the map flat and predictable).

### Desktop layout (≥ 768 px)

- Controls split into **top-right vertical stack**: Metric toggle / Class filter / Time window.
- Legend floats **bottom-left**.
- Side panel slides in from the **right**, fixed 400 px width, content is a static chart (no snap points).
- Keyboard: `M` cycles metric, `C` opens class filter, `T` opens time window, `Esc` closes the panel. Shortcuts surfaced by pressing `?`.

### Performance budget for mobile

- First map paint < 2.5 s on a mid-tier Android (Moto G Power class) over 4G.
- PMTiles over-the-wire payload for the Dublin extract < 6 MB gzipped (verify during Step D7 build; compress further if needed).
- JS bundle for the `/[city]` route < 180 kB gzipped (enforced by `@next/bundle-analyzer` in CI).
- Main thread work for metric toggle < 50 ms (no refetch; paint update only).

## 9-ter. Accessible Colour

The black/white brand means the **only** colour in the UI is the metric ramp.
It must be colour-blind safe.

### Pinned ramps (can be overridden by `DESIGN.md`, but not weakened)

- **Counts** → **viridis** (5-stop): `#440154 → #3b528b → #21918c → #5ec962 → #fde725`.
  Perceptually uniform, Deuteranopia/Protanopia/Tritanopia safe, prints well in greyscale.
- **Speed** → **cividis** (5-stop): `#00224e → #3c456b → #7c7b78 → #c0ac5d → #fee838`.
  Deuteranomaly-optimised, increases linearly in lightness (useful when speed correlates with urgency).

Both ramps are sequential; speed is **not** diverging because a diverging scale
implies a "neutral midpoint" that doesn't apply to average speed.

### Rules

- Line weight of the coloured layer: **4 px** on desktop, **5 px** on mobile (stronger visual presence at small scale; still clean).
- **Never encode meaning by colour alone.** Hovering or tapping a street always shows the numeric value and class label. The side sheet always carries the same information in text.
- **Contrast:** streets must keep ≥ 3:1 against the OSM basemap in all ramp stops. Protomaps basemap is mid-grey; verified 3:1 for viridis `#3b528b` (the darkest against grey) during Step D7 (add a regression screenshot test).
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables:
  - Bottom-sheet spring animations (replaced by instant transitions ≤ 100 ms).
  - Map fly-to on segment select (replaced by instant zoom).
  - Legend hover pulse.
- **Admin preview:** `/admin` has a toolbar toggle that applies Protanomaly / Deuteranomaly / Tritanomaly / greyscale filters to the whole page (CSS filter matrix). Lets admins sanity-check the ramp before publishing a new street.
- **Legend:** always visible on desktop; collapsed behind a legend-toggle pill on mobile (the `◎` control). The legend labels endpoints with numeric values (*"0 · 300/15min"*), not just colour gradients.

### Privacy interaction

The mock-data pill and the colour-blindness preview toggle both set
`aria-live="polite"` announcements when engaged, so screen-reader users are
informed the view has changed.

## 10. URL State Management

**Principle:** the URL is both shareable and cache-safe. We partition state into three slots by churn rate:

| Slot | Purpose | Example | Caching impact |
|---|---|---|---|
| **Path** | Bounded, named scopes | `/dublin`, `/dublin/street/dame-st-grafton-to-trinity` | Cacheable; tiny value space |
| **Query** | Filter state (small discrete sets) | `?m=counts&w=1h&cls=cyclist` | Cacheable per permutation; small |
| **Hash** | Map viewport (continuous, high-cardinality) | `#14.5/53.3385/-6.2521` | Never sent to server → never cached |

**Patterns:**

- `/dublin` — public map for Dublin, default view.
- `/dublin?m=speed&w=24h&cls=cyclist` — same map, Speed metric, 24 h window, cyclists only.
- `/dublin#14.5/53.3385/-6.2521` — same map, specific viewport (shared link).
- `/dublin/street/dame-st-grafton-to-trinity?w=7d` — street detail page.

**Why not `/dublin/zoom14/53.3385/-6.2521`?**
- Infinite unique URLs → cache explosion on Vercel's edge cache.
- Breaks `revalidatePath` (unbounded invalidation surface).
- Next.js expects route params to be bounded; dynamic viewport values pollute generated types.
- The OSM reference pattern (`osm.org/#map=14/53.3385/-6.2521`) uses the hash for exactly this reason.

**Implementation:**
- Hash read/written via a tiny `useMapHash()` hook — updates MapLibre on `hashchange`, and serialises viewport to hash on `moveend` (debounced).
- Query read via Next.js `useSearchParams`; default-merged on the server for SSR-friendly first paint.
- Path `[city]` is statically generated for known cities; unknown slugs → 404.
- **City slugs** from `DESIGN.md` list (initially just `dublin`).
- **Street slugs** from `streets.id` (kebab-case, stable, human-readable).

## 11. Admin Config Change Flow (HTTPS, no MQTT)

1. Admin submits form at `/admin/sensors/[id]`.
2. `PATCH /api/admin/sensors/[id]` validates (zod), updates `sensors.config_json`, recomputes `config_version` (short hash of canonical config), writes audit log.
3. Response returns immediately — no broker hop.
4. On the next device POST (worst case `publish_interval_minutes` later), the response includes `latest_config_version`. Device detects mismatch, GETs `/config`, applies, persists.
5. On the device's next heartbeat, `config_version` matches; admin UI flips "Awaiting device ack" → "✓ applied". Shown relative time: *"applied 2 min ago"*.

No server→device push is required. The only tradeoff is config-propagation latency bounded by the publish interval — acceptable since that interval is already the product SLA.

## 12. Module Layout

```
dashboard/
├── vercel.ts                              # framework, headers, crons
├── package.json
├── drizzle.config.ts
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                       # redirects to default city
│   │   ├── [city]/page.tsx                # street map
│   │   ├── [city]/street/[slug]/page.tsx  # street detail
│   │   ├── (auth)/sign-in/page.tsx        # Google button only
│   │   ├── (auth)/error/page.tsx
│   │   ├── admin/
│   │   │   ├── layout.tsx                 # role=admin middleware
│   │   │   ├── page.tsx
│   │   │   ├── sensors/page.tsx
│   │   │   ├── sensors/[id]/page.tsx
│   │   │   ├── streets/page.tsx
│   │   │   ├── members/page.tsx
│   │   │   ├── events/page.tsx
│   │   │   └── audit/page.tsx
│   │   ├── api/
│   │   │   ├── health/route.ts
│   │   │   ├── ingest/sensors/[id]/counts/route.ts
│   │   │   ├── ingest/sensors/[id]/daily/route.ts
│   │   │   ├── ingest/sensors/[id]/heartbeat/route.ts
│   │   │   ├── ingest/sensors/[id]/config/route.ts
│   │   │   ├── streets/route.ts
│   │   │   ├── streets/[id]/route.ts
│   │   │   ├── streets/[id]/readings/route.ts
│   │   │   ├── basemap/[z]/[x]/[y]/route.ts
│   │   │   ├── admin/sensors/route.ts
│   │   │   ├── admin/sensors/[id]/route.ts
│   │   │   ├── admin/sensors/[id]/coverage/route.ts
│   │   │   ├── admin/streets/route.ts
│   │   │   ├── admin/members/route.ts
│   │   │   ├── admin/audit/route.ts
│   │   │   ├── cron/refresh-aggregates/route.ts
│   │   │   ├── cron/detect-silent/route.ts
│   │   │   ├── cron/reconcile-daily/route.ts
│   │   │   └── auth/[...nextauth]/route.ts
│   ├── components/
│   │   ├── map/StreetMap.tsx              # MapLibre client component
│   │   ├── map/ColourLegend.tsx
│   │   ├── map/MetricToggle.tsx
│   │   ├── map/ClassFilter.tsx
│   │   ├── map/TimeWindowPicker.tsx
│   │   ├── map/useMapHash.ts              # hash↔viewport sync
│   │   ├── charts/StreetTimeSeries.tsx
│   │   ├── panels/StreetSidePanel.tsx
│   │   ├── admin/SensorForm.tsx
│   │   ├── admin/StreetDrawTool.tsx
│   │   └── ui/*                           # shadcn
│   ├── lib/
│   │   ├── db.ts                          # Drizzle client (server-only)
│   │   ├── auth.ts                        # Auth.js + Google + allowlist
│   │   ├── ingest-auth.ts                 # Bearer token verification + rate limit
│   │   ├── config-version.ts              # canonical-hash helper
│   │   ├── schemas.ts                     # zod (shared with device side via OpenAPI)
│   │   ├── cache-tags.ts                  # typed tag factory
│   │   └── geo.ts                         # bbox, colour scales, slug helpers
│   └── styles/globals.css
├── tests/
│   ├── unit/*.test.ts
│   └── e2e/*.spec.ts
└── public/
```

## 13. Vercel Best Practices Checklist

### Project setup
- [ ] `pnpm create next-app@latest` (TS, App Router, Tailwind, src/ layout)
- [ ] `vercel.ts` with framework, cron, headers, redirects (`/` → `/dublin`)
- [ ] shadcn primitives — don't pull in a full component library

### Environments
- [ ] Three envs: `development` (local), `preview` (per PR, Neon branch DB), `production`
- [ ] Secrets via `vercel env add`; `vercel env pull` locally
- [ ] **Never** expose the DB connection string to the client

### Performance
- [ ] Turbopack for dev + prod build (Next.js 16 default)
- [ ] `next/font` with local fonts
- [ ] `next/image` for imagery
- [ ] PMTiles served via Vercel Blob or a cached route
- [ ] CWV targets: LCP < 2.0 s, CLS < 0.05, INP < 150 ms; verify with Speed Insights post-deploy

### Caching
- [ ] `fetch()` with `{ next: { tags: [...] } }` on DB reads
- [ ] `revalidateTag` on admin writes + cron refreshes
- [ ] `use cache` / `unstable_cache` for expensive DB queries
- [ ] HTTP `Cache-Control: s-maxage=60, stale-while-revalidate=300` on `/api/streets`

### Security & privacy
- [ ] **Vercel BotID** on sign-in and all admin mutations
- [ ] CSP / HSTS / X-Content-Type-Options / Referrer-Policy / Permissions-Policy in `vercel.ts`
- [ ] All admin routes protected by Auth.js middleware + server-side re-check
- [ ] **Ingest routes protected by Bearer token + Upstash Ratelimit** (per-device)
- [ ] **Privacy regression test** in CI: asserts no public API body contains `sensor_id`, `latitude`, `longitude`
- [ ] Audit log row on every admin mutation + every config version bump

### Reliability
- [ ] Ingest route returns 202/200 fast; writes are synchronous (Postgres is fast enough) but idempotent on `(sensor_id, window_start)`
- [ ] Cron retries handled by Vercel (max 3); idempotent job bodies
- [ ] Aggregate refresh is `CONCURRENTLY` so admin reads don't block

### Deployment flow
- [ ] Git → Vercel Preview on every PR (Neon branch DB spun up automatically)
- [ ] Playwright E2E runs on preview URL
- [ ] **Rolling Releases** on prod: 10 % → 50 % → 100 % with health gates
- [ ] Auto-rollback on error spike
- [ ] Slack webhook on deploy/failure

### Observability
- [ ] Analytics + Speed Insights enabled
- [ ] Sentry (client + server) with PII scrubber
- [ ] Custom events: `config.published`, `sensor.created`, `street.mapped`, `ingest.received`
- [ ] Uptime ping on `/api/health` (BetterStack)
- [ ] Dashboard of ingest rate per sensor (spots dead sensors fast)

## 14. Implementation Steps

> **Prerequisite:** Plan 01 at Step 4 (HttpsPublisher working) so preview deploys can be exercised end-to-end against a real (stub) device emitter.

### Step D1 — Scaffolding + deploy-on-main
Next.js 16, TS, Tailwind, Drizzle, `vercel.ts`. Hello-world deploy, Git previews confirmed.
**Verify:** prod URL returns 200; preview spawns an isolated Neon branch DB.

### Step D2 — Auth (Google-only) + allowlist
Auth.js v5 + Google provider + Drizzle adapter. `signIn` callback rejects unless `email ∈ allowed_members` OR `domain ∈ allowed_domains`. `/sign-in` page with a single "Continue with Google" button. Middleware gates `/admin/*` (role=admin) and `/[city]` (any allowed member).
**Verify:** non-allowlisted email → friendly reject; admin → `/admin`; viewer → `/[city]`.

### Step D3 — DB schema + migrations + seed
Drizzle schema mirrors §8. Neon-compatible migrations. Seed script for Dublin (5 streets, 2 sensors, mocked coverage, 7 days of fake readings).
**Verify:** `pnpm db:migrate && pnpm db:seed` runs clean on a fresh Neon branch.

### Step D4 — Public street API
`GET /api/streets` (bounded bbox), `GET /api/streets/[id]`, `GET /api/streets/[id]/readings?metric=…&class=…&from=…&to=…&bucket=…`. Cache tags, `revalidate=60`.
**Verify:** Vitest + privacy-regression test (no sensor fields in responses). Postman collection green.

### Step D5 — Device ingest API
`POST /api/ingest/sensors/[id]/counts`, `/daily`, `/heartbeat`. Bearer auth against `sensors.api_token_hash`. Idempotent on primary keys. Returns `{ ok, latest_config_version }`. Upstash rate-limit per device.
**Verify:** integration test with a mock device (same httpx client from Plan 01) posting 100 windows; all land in DB; replays are no-ops.

### Step D6 — Device config API
`GET /api/ingest/sensors/[id]/config` returns current config + version. On bump, admin UI sees the new version immediately; device catches up at its next publish.
**Verify:** `PATCH /api/admin/sensors/[id]` → new `config_version` → GET returns it → mock device applies.

### Step D7 — Public street map (hero view)
`<StreetMap>` (client) with MapLibre + Protomaps OSM PMTiles. `/api/streets` bounded fetch, `feature-state` paint, controls (`MetricToggle`, `ClassFilter`, `TimeWindowPicker`, `ColourLegend`). Hash-based viewport state (§10).
**Verify:** Lighthouse LCP < 2.0 s on preview; tile cache hit > 95 %; metric toggle ≤ 50 ms client-side.

### Step D8 — Street detail page + time series
`/[city]/street/[slug]` with `<StreetTimeSeries>`. Ranges 1 h / 24 h use `street_readings_15m`; 7 d / 30 d use `street_readings_hourly`. 60 s client polling on latest bucket.
**Verify:** renders for seeded street; handles empty/partial/gap states.

### Step D9 — Admin: sensor CRUD + street mapping
`/admin/sensors` list + form (GPS visible here only). `<StreetDrawTool>` lets admin draw or click OSM ways; PostGIS snaps; saves to `sensor_street_coverage`. `/admin/streets` manages the catalogue.
**Verify:** create sensor + map to street → street appears on public map after cache invalidation; removing the mapping hides it.

### Step D10 — Admin: config change UX
`PATCH /api/admin/sensors/[id]` updates DB and bumps `config_version`. Form fields: `publish_interval_minutes`, `heartbeat_interval_minutes`, `frame_skip`, `zone_polygon` (map-drawn). UI shows "awaiting device ack" → "✓ applied" when a heartbeat arrives with matching version.
**Verify:** change interval; simulated device picks it up on its next POST (within `publish_interval_minutes`); UI flips.

### Step D11 — Events / reconciliation / audit
`/admin/events`: silent sensors (> 15 min since last heartbeat), reconciliation mismatches from the nightly cron, config-apply failures. `/admin/audit` filterable log. Acknowledge workflow.
**Verify:** pause simulated device → event appears; resume → clears.

### Step D12 — Cron jobs
`/api/cron/refresh-aggregates` (every 5 min), `/api/cron/detect-silent` (every 15 min), `/api/cron/reconcile-daily` (01:00 UTC). All idempotent; each logs its own audit row.
**Verify:** Vercel Cron UI shows green runs; reconciliation job flags a seeded mismatch correctly.

### Step D13 — BotID, CSP, rate limits, observability
BotID on sign-in + admin PATCH. CSP in `vercel.ts`. Upstash Ratelimit on writes + per-device ingest. Sentry + Analytics + Speed Insights.
**Verify:** automated bot hits sign-in → challenged; human flow clean.

### Step D14 — Rolling Release + runbook
Enable Vercel Rolling Releases (10 / 50 / 100) with health gates. `docs/RUNBOOK.md`: rollback, DB incident, ingest storm. Uptime monitor on `/api/health`.
**Verify:** dry-run rolling deploy; synthetic error → auto-rollback.

## 14-bis. Data Source Toggle (Mock vs Live)

Dashboard development must work **before any real sensor is deployed**. The app
therefore supports two data sources, selected by an environment variable:

```
CAMINA_DATA_SOURCE=mock   # dev default — serves data/mock/dublin/*.json
CAMINA_DATA_SOURCE=live   # production — queries Postgres
```

### Behaviour

- `mock`:
  - Public reads (`/api/streets`, `/api/streets/[id]`, `/api/streets/[id]/readings`) are served from the JSON fixtures under `data/mock/dublin/`.
  - Device ingest routes (`/api/ingest/*`) **respond 202 but do nothing** — there are no real devices in mock mode. This lets a mock device exercise the code path without polluting fixtures.
  - Admin writes (`PATCH /api/admin/sensors/[id]`) update an **in-memory shadow copy** scoped to the session, so admins can exercise the config-change UX without a real DB. Shadow state resets on process restart.
  - A persistent pill in the top-right corner reads **"Mock data — Dublin demo"** (per `DESIGN.md` palette: Uber Black pill with white text).
- `live`:
  - Everything queries the real DB as specified in §§ 4, 8.
  - The mock pill disappears.

### Implementation pattern

```
lib/data-source.ts
└── dataSource: 'mock' | 'live' = process.env.CAMINA_DATA_SOURCE === 'mock' ? 'mock' : 'live'

lib/repo/streets.ts
└── if (dataSource === 'mock') import mock adapter, else import pg adapter
    (both satisfy the same `StreetRepo` interface → swap at import time, no branching in routes)
```

Routes depend on the `StreetRepo` interface, not a concrete adapter — this
keeps the privacy regression test applicable to both sources.

### Preview deploys

- Vercel preview deploys default to `CAMINA_DATA_SOURCE=mock` (env scoped to
  the `preview` environment in Vercel settings).
- Production uses `live` once a database is attached.
- Storybook / Playwright E2E always use `mock` for determinism.

### Fixtures

See `scripts/generate_mock_dublin.py` and `data/mock/dublin/README.md`.
Regenerate with:

```bash
python scripts/generate_mock_dublin.py
```

Already generated at plan time:

| File | Rows |
|---|---|
| `streets.json` / `streets.geojson` | 10 |
| `sensors.json` (admin-only — GPS included) | 10 |
| `sensor_street_coverage.json` | 10 |
| `sensor_readings.json` (7 days × 15-min windows) | ~50 k |
| `sensor_heartbeats.json` (last 24 h × 5 min) | 2880 |
| `sensor_daily_totals.json` | 70 |

## 15. Environment Variables

```
# Database (Neon via Vercel Marketplace)
DATABASE_URL                  # pooled
DATABASE_URL_UNPOOLED         # direct, for migrations

# Auth.js + Google
AUTH_SECRET                   # openssl rand -base64 32
AUTH_URL                      # https://camina.ucd.ie (prod) / preview URL
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET

# Basemap
PROTOMAPS_PMTILES_URL         # Vercel Blob URL for dublin.pmtiles

# Observability
SENTRY_DSN
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN

# Optional
VERCEL_CRON_SECRET            # verify cron origin
```

Per-device API tokens are **not** env vars — they're generated on sensor creation, hashed with Argon2, and stored in `sensors.api_token_hash`. The device receives the raw token via a one-time provisioning flow.

## 16. Test Strategy

- **Unit (Vitest):** zod schemas, Drizzle queries, `config-version` helper, cache-tag helpers, colour-scale.
- **Privacy regression:** for every public route, assert body contains no `sensor_id` / `latitude` / `longitude`.
- **Integration (Dockerized Postgres + PostGIS):** all API routes end-to-end.
- **E2E (Playwright on preview):**
  - non-allowlisted Google rejected
  - admin creates sensor, maps to street, sees it on `/dublin`
  - viewer cannot reach `/admin/*`
  - mock device posts → street turns coloured within next aggregate refresh
  - admin changes interval → mock device applies on next post
  - metric toggle recolours without refetching basemap
  - street side panel has zero sensor fields (automated attribute check)
- **Load (k6):** 200 concurrent viewers + 50 mock devices posting every 30 s; p95 < 500 ms on `/api/streets`, no 5xx on ingest.

## 17. Verification Checklist

- [ ] `pnpm typecheck && pnpm lint && pnpm test` green in CI
- [ ] Privacy regression test green (no GPS/sensor_id leakage)
- [ ] Playwright E2E green on preview
- [ ] Lighthouse ≥ 95 Performance & Accessibility
- [ ] CWV inside §13 targets
- [ ] `server-only` isolation verified by bundle analyzer
- [ ] `vercel env ls` matches §15 per environment
- [ ] Rolling Release health gates set
- [ ] End-to-end: admin config change applies within one publish interval
- [ ] `DESIGN.md` compliance review (once delivered)

## 18. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GPS leak via a future route | Medium | High | CI privacy-regression test + `server-only` guards + review checklist |
| Rate-limit abuse on public endpoints | Low | Medium | Upstash Ratelimit + sign-in gating |
| Compromised per-device token | Low | Medium | Rotate via admin UI (updates `api_token_hash`); device receives new token on provisioning |
| Google OAuth verification delay | Medium | Medium | Use UCD internal Google app type; start verification early |
| Cron job overlap / long refresh | Low | Medium | Lock via advisory lock; refresh CONCURRENTLY; split 15m/hourly into two cron entries |
| Neon cold-start latency | Low | Low | Neon serverless wakes in < 1 s; keep-alive via the cron itself |
| Single-sensor street → GPS inference | Low | Medium | k-sensor guard (§7); admin review before activating a new street |
| PMTiles file too large | Low | Low | Pre-build Dublin extract (< 50 MB) and host on Vercel Blob |

## 19. `DESIGN.md` — What It Must Specify

1. Primary / secondary / accent palette.
2. Sequential colour ramp for the metric layer (5 stops); separate ramps for Counts vs. Speed if desired.
3. Typography: heading + body + mono font.
4. Iconography set (Lucide or custom) for classes.
5. Empty / loading / error states (copy + visuals).
6. Tone of voice.
7. Dark/light strategy.
8. Logo placement (UCD, Spatial Dynamics Lab, INTERREG).
9. Map control layout (position, stacked vs inline, collapse behaviour).
10. Side-panel behaviour (slide-in right / bottom sheet).
11. Animation durations and easing; reduced-motion fallback.
12. City slugs (initial: `dublin`).

## 20. Estimated Effort

| Step | Estimate |
|---|---|
| D1 Scaffolding | 0.5 d |
| D2 Auth.js + Google + allowlist | 1.0 d |
| D3 DB schema + migrations + seed | 0.5 d |
| D4 Public street API | 1.0 d |
| D5 Device ingest API | 1.0 d |
| D6 Device config API | 0.5 d |
| D7 Public street map (hero) | 1.5 d |
| D8 Street detail + charts | 1.0 d |
| D9 Admin CRUD + street mapping | 1.5 d |
| D10 Admin config change UX | 0.5 d |
| D11 Events / reconciliation / audit | 0.5 d |
| D12 Cron jobs | 0.5 d |
| D13 BotID / CSP / rate limits / obs | 0.5 d |
| D14 Rolling Release + runbook | 0.5 d |
| **Total** | **~10.5 days** |

Plus ~2 days of theming once `DESIGN.md` lands.

## 21. Next Actions After Approval

1. Author `DESIGN.md` (can proceed in parallel with D1–D3).
2. Link the Neon database via Vercel Marketplace; capture `DATABASE_URL` into `vercel env`.
3. Create Google OAuth credentials (UCD Google Cloud project).
4. Start Step D1.

---

## Appendix A — Vercel references applied

- Next.js 16 App Router / Cache Components / PPR
- Fluid Compute (no Edge Functions)
- `vercel.ts` typed config with cron declarations
- Rolling Releases (GA 2025-06)
- Vercel BotID (GA 2025-06)
- Vercel Analytics + Speed Insights
- Neon Postgres + PostGIS via Vercel Marketplace
- Upstash Ratelimit via Vercel Marketplace
