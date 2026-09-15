# Architecture Research

**Domain:** Privacy-first edge-CV + LoRaWAN + serverless-dashboard for urban mobility (TRL-6, solo-dev, 5-week sprint)
**Researched:** 2026-04-23
**Confidence:** HIGH on the stack choices already in code (verified against Vercel/Neon/Next.js 16 docs); MEDIUM on the LoRa transport design (procurement not yet done, TTN coverage not yet confirmed).

> Scope: brownfield — Plan 01 edge agent is shipped (60 tests green), Plan 02 dashboard is scaffolded in mock mode. This document compares CAMINA's current choices to how similar systems are built in 2026, and recommends a build order for the 5-week sprint.

---

## Standard Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                          EDGE (Raspberry Pi 5 8GB)                      │
│   ┌──────────┐   ┌────────┐   ┌──────────────┐   ┌──────────────────┐  │
│   │ Camera   │──▶│ YOLO11 │──▶│ Kalman +     │──▶│ WindowedCounter  │  │
│   │ libcamera│   │ (NCNN) │   │ Hungarian    │   │ + DailyAccumul.  │  │
│   └──────────┘   └────────┘   │ tracker      │   └────────┬─────────┘  │
│                                └──────────────┘            │            │
│                                ┌───────────────────────────▼─────────┐  │
│                                │        SensorDaemon (orchestrator)  │  │
│                                │  ┌─────────────────────────────┐    │  │
│                                │  │  Publisher (interface)      │    │  │
│                                │  │   ├── HttpsPublisher        │    │  │
│                                │  │   └── LoRaPublisher  (NEW)  │    │  │
│                                │  └────────────┬────────────────┘    │  │
│                                │  ┌────────────▼────────────────┐    │  │
│                                │  │  OfflineBuffer (WAL SQLite) │    │  │
│                                │  │  shared by all transports   │    │  │
│                                │  └─────────────────────────────┘    │  │
│                                │  ┌─────────────────────────────┐    │  │
│                                │  │ ConfigPoller, HeartbeatLoop │    │  │
│                                │  └─────────────────────────────┘    │  │
│                                └─────────────────────────────────────┘  │
└──────┬──────────────────────────────────┬──────────────────────────────┘
       │ HTTPS POST (primary)             │ LoRaWAN Class A uplink (<200 B)
       │ 15-min counts / 5-min heartbeat  │ Fair-use ≤30 s airtime/day
       ▼                                  ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│  Vercel Fluid Compute   │      │  The Things Network (TTN)   │
│  Next.js 16 App Router  │      │  Community network server   │
│  /api/ingest/sensors/*  │      │  Webhook → POST             │
│  /api/ingest/lora/*  ◀──┼──────┤  /api/ingest/lora/uplink    │
│  (Node 24, 300 s max)   │      └─────────────────────────────┘
│                         │
│  Cron (vercel.ts):      │
│   */15 refresh-aggregates
│   */15 detect-silent    │
│    1 0  reconcile-daily │
└──────────┬──────────────┘
           │ SQL over TLS (postgres-js / TCP pool)
           ▼
┌────────────────────────────────────────────────────────────┐
│        Neon Postgres + PostGIS (Vercel Marketplace)        │
│  ┌────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │ sensors    │  │ sensor_readings    │  │ streets      │  │
│  │ (admin)    │  │ (BRIN on window)   │  │ (PostGIS)    │  │
│  └────────────┘  │ PARTITION BY month │  └──────────────┘  │
│                  └────────────────────┘                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MATERIALIZED VIEW street_readings_15m (public)      │   │
│  │ refreshed CONCURRENTLY by cron every 15 min         │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────────────────────────┘
           │ Drizzle (server-only import) — static shell + streamed metrics
           ▼
┌──────────────────────────────────────────────────────────────┐
│     Browser — Next.js 16 RSC + MapLibre GL (dynamic import)  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ <Suspense> boundary: streams <StreetMap>             │    │
│  │   source: streets.geojson (static, bbox-bounded)     │    │
│  │   feature-state: Map<street_id, {count, speed}>      │    │
│  │   paint: ['interpolate', ..., ['feature-state', …]]  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component                  | Responsibility (wire-level)                                                   | Current Status                                                                 |
|----------------------------|-------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| `SensorDaemon`             | Owns the main loop; injects `frame_source` + `detect_and_track`; fan-out       | Shipped; missing `scripts/run_sensor.py` that composes real YOLO               |
| `WindowedCounter`          | Unique-ID dedup per 15-min wall-clock window; produces `WindowSnapshot`        | Shipped                                                                         |
| `DailyAccumulator`         | UTC-midnight rollover; SQLite-persisted totals; produces `DailySnapshot`       | Shipped                                                                         |
| `Publisher` (interface)    | Single method `publish(endpoint, payload) -> (ok, latest_config_version)`      | **Does not exist yet** — `HttpsPublisher` is concrete. Extract before LoRa.     |
| `HttpsPublisher`           | POST to `/api/ingest/sensors/{id}/{counts,daily,heartbeat}`                    | Shipped                                                                         |
| `LoRaPublisher` (NEW)      | Encode `WindowSnapshot` to ≤200 B; submit to local LoRa modem (serial/SPI)     | Not yet built; codec un-designed; hardware un-procured                         |
| `OfflineBuffer`            | WAL-SQLite FIFO shared by ALL transports; drop-oldest at cap                   | Shipped — already transport-agnostic (stores `endpoint` + `payload` BLOB)      |
| `ConfigPoller`             | Compare version from response header; GET `/config`; apply hot                 | Shipped (HTTPS only; must no-op when transport is LoRa-only)                   |
| TTN webhook handler (NEW)  | `POST /api/ingest/lora/uplink` — validate TTN signature, decode, dedupe         | Not yet built                                                                   |
| Ingest routes (HTTPS)      | Bearer auth; zod validate; idempotent INSERT on `(sensor_id, window_start, class_name)` | Shipped as stubs; DB writes wait on M2                                  |
| Cron: `refresh-aggregates` | `REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m`                   | Route skeleton shipped; body pending live DB                                    |
| Cron: `detect-silent`      | `SELECT sensor_id WHERE last_heartbeat < NOW() - '15 min'`                     | Skeleton shipped                                                                |
| Cron: `reconcile-daily`    | Sum of 15-min windows vs daily payload; flag mismatches                        | Skeleton shipped                                                                |
| `StreetsRepo`              | Mock or live; all routes/RSCs depend on this interface                         | Mock shipped; `streets-live.ts` throws                                          |
| MapLibre `StreetMap`       | Static basemap + `feature-state` painting; no sensor fields ever in props      | Shipped in mock mode                                                            |
| Admin UI + `requireAdmin`  | Google OAuth + allowlist; only surface for `sensors.latitude/longitude`        | Shell shipped; real auth + CRUD pending                                         |

---

## Recommended Project Structure

The current layout is already close to best practice; the two structural moves worth making before M1 ends:

```
src/camina/
├── core/                   # Pure logic; no I/O
│   ├── counter.py          # WindowedCounter, DailyAccumulator  [existing]
│   └── tracker.py          # Kalman + Hungarian                  [existing]
├── io/                     # Anything that does network or disk
│   ├── publisher.py        # NEW — Protocol/ABC: Publisher interface
│   ├── https_publisher.py  # implements Publisher               [refactor]
│   ├── lora_publisher.py   # NEW — implements Publisher
│   ├── lora_codec.py       # NEW — encode/decode ≤200-B payload
│   ├── http_client.py      # [existing]
│   ├── offline_buffer.py   # transport-agnostic FIFO            [existing]
│   ├── config_poller.py    # HTTPS-only; no-op in LoRa-only mode [existing]
│   └── schemas.py          # [existing]
├── service/
│   └── sensor_daemon.py    # wires transports chosen by config   [modify]
└── utils/                  # [existing]

scripts/
└── run_sensor.py           # NEW — composes YOLO + tracker + SensorDaemon

dashboard/src/app/api/
├── ingest/sensors/[id]/…   # HTTPS ingest                        [existing]
└── ingest/lora/
    └── uplink/route.ts     # NEW — TTN webhook

dashboard/src/lib/
├── lora-codec.ts           # NEW — mirror of Python codec; shared test vectors
└── ttn-auth.ts             # NEW — HMAC/Basic auth for TTN webhook
```

### Structure Rationale

- **`io/publisher.py` (new):** every textbook review of dual-transport IoT agents ends up with the same conclusion — hoist the transport behind a single interface before adding the second one; otherwise branching spreads to `SensorDaemon`, `OfflineBuffer`, and `ConfigPoller`. The `OfflineBuffer` schema (`endpoint TEXT, payload BLOB`) was already written to be transport-agnostic, so this refactor is small (<100 lines) and high-leverage.
- **`io/lora_codec.py` + `dashboard/src/lib/lora-codec.ts`:** codec is shared logic, mirrored in both languages (same pattern as `schemas.py` ↔ `schemas.ts`). Ship joint fuzz-test vectors in `tests/fixtures/lora/` so drift is caught mechanically.
- **`scripts/run_sensor.py` is the M1 blocker:** `sensor_daemon.py::main` deliberately raises `SystemExit` pointing at this — without it no real Pi benchmark can run. Write first, everything else in M1 follows.

---

## Architectural Patterns

### Pattern 1 — Publisher interface + shared OfflineBuffer (dual-transport)

**What:** `Publisher` is a Protocol with `publish(endpoint: str, payload: bytes) -> PublishResult`. `HttpsPublisher` and `LoRaPublisher` both implement it. `OfflineBuffer` accepts `(endpoint, payload)` regardless of origin. `SensorDaemon` holds a list of enabled publishers; on each window boundary it fans out (primary → fallback) with a single durable outbox behind both.

**When to use:** Any edge agent that needs two transports and does not want to duplicate retry/buffer state. This is the pattern used by OPC Publisher (Azure IoT Edge), the Balena fleet agent, and most production LoRa+Cellular nodes.

**Trade-offs:**
- ✓ Backpressure and cap behaviour live in one place.
- ✓ `WindowedCounter` / `DailyAccumulator` / `ConfigPoller` stay transport-oblivious.
- ✗ Introduces an indirection; one extra file to trace. Worth it the moment you have two transports.

**Example (Python):**

```python
# src/camina/io/publisher.py
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class PublishResult:
    ok: bool
    latest_config_version: str | None = None

class Publisher(Protocol):
    name: str                             # "https" | "lora"
    def publish(self, endpoint: str, payload: bytes) -> PublishResult: ...
    def supports(self, endpoint: str) -> bool: ...   # LoRa does not support /config GET
```

### Pattern 2 — Idempotent ingest with natural primary key

**What:** Every ingest row has a natural PK (`sensor_id`, `window_start`, `class_name`). `INSERT ... ON CONFLICT DO NOTHING`. TTN dedup key is `(sensor_id, f_cnt)` — check before forwarding to the counts table.

**When to use:** Any at-least-once delivery pipeline. CAMINA has this at the HTTPS layer already; extend it to LoRa by using TTN's `f_cnt` as the idempotency key.

**Trade-offs:**
- ✓ Safe for retries, safe for TTN "delivered multiple times by different gateways".
- ✗ Requires discipline — one future schema change that forgets the PK and the invariant cracks.

### Pattern 3 — Mock/live repository with type-enforced privacy boundary

**What:** `StreetsRepo` is a TypeScript interface; `mockStreetsRepo` and `liveStreetsRepo` both implement it; selection by `CAMINA_DATA_SOURCE` env. `StreetSummary` (public) and `StreetAdminInfo` (admin-only) are distinct types; `adminInfo()` is the only method that returns GPS; routes gate it with `if (!isMock) requireAdmin()`.

**When to use:** CAMINA already uses this — it is the load-bearing privacy pattern. Do not weaken it. The privacy regression test in `dashboard/tests/unit/privacy-regression.test.ts` enforces it at CI time.

**Trade-offs:**
- ✓ Privacy invariant is structural, not aspirational.
- ✓ Dashboard dev unblocked before Neon is provisioned.
- ✗ Two implementations drift unless covered by the same integration tests. Mitigation: run the public-read test suite against both adapters in CI.

### Pattern 4 — Static shell + streamed metrics (Next.js 16 PPR)

**What:** The map route is mostly static — basemap, street GeoJSON, chrome — and should prerender. The per-street metrics (counts/speed per window) stream into a `<Suspense>` boundary. Currently `cacheComponents: true` is commented out in `next.config.mjs` because those boundaries are not yet in place.

**When to use:** Any Next.js 16 route that mixes static chrome with per-request data. The map is the poster child.

**Trade-offs:**
- ✓ First paint is instant; metrics fill in without blocking.
- ✓ Edge-cacheable basemap fetch (60 MB tiles) is separated from metrics (changes every 15 min).
- ✗ Requires discipline wrapping every dynamic read in `<Suspense>` with a sensible fallback.

**Example:**

```tsx
// dashboard/src/app/[city]/page.tsx
import { Suspense } from 'react';
import { MapShell } from './MapShell';         // 'use cache' — static
import { MetricsPainter } from './MetricsPainter'; // reads from streetsRepo.latestMetrics()

export default async function CityPage({ params }) {
  const { city } = await params;              // Next.js 15+ async params
  return (
    <MapShell city={city}>
      <Suspense fallback={<LegendSkeleton />}>
        <MetricsPainter city={city} />         {/* dynamic; streams */}
      </Suspense>
    </MapShell>
  );
}
```

### Pattern 5 — CONCURRENTLY-refreshed materialized view as public cache

**What:** Raw `sensor_readings` is partitioned by month, BRIN-indexed on `window_start`. A materialized view `street_readings_15m` joins sensor→street via `sensor_street_coverage` and strips `sensor_id`. Cron refreshes it CONCURRENTLY every 15 min. Public API reads only from the MV.

**When to use:** Whenever "public aggregate" ≠ "raw event" and you need both (a) fast public reads and (b) right-to-erasure of raw rows.

**Trade-offs:**
- ✓ Right-to-erasure: `DELETE FROM sensors WHERE id = ?` cascades raw rows; MV rebuilds minus that sensor. **But** the public MV does not include `sensor_id`, so historical aggregates can remain without re-identifying anyone (aggregation = anonymisation under EDPB guidance).
- ✓ TimescaleDB's hypertables are overkill at CAMINA's scale (≤10 sensors × 96 windows/day × 9 classes ≈ 3.15 M rows/year; Postgres + BRIN handles this easily).
- ✗ CONCURRENTLY requires a UNIQUE index on the MV (already in the schema: `uidx_street_15m`).
- ✗ 15-min refresh cadence introduces up to 15 min of public-map staleness (acceptable, matches the edge publish cadence).

---

## Data Flow

### Request flow — camera frame → public map tile

```
[Pi camera — libcamera]
    ↓  ~10 FPS frame
[YOLO11 NCNN — Detector]
    ↓  List[Detection]
[Kalman + Hungarian tracker]
    ↓  List[Tracked(track_id, class)]
[WindowedCounter.add()]
    ↓  on wall-clock 15-min boundary
[WindowSnapshot]  ──→  [DailyAccumulator.add_window()]  (SQLite persist)
    ↓
[SensorDaemon fan-out]
    ├─▶ [HttpsPublisher] → POST /api/ingest/sensors/{id}/counts
    │         ├─ success → response.latest_config_version → [ConfigPoller]
    │         └─ failure → [OfflineBuffer.enqueue()]  (drained next cycle)
    └─▶ [LoRaPublisher]  → encode ≤200 B → UART → LoRa modem → radio
              └─ TTN gateway → TTN network server → webhook
                    ↓
              [POST /api/ingest/lora/uplink]
                    ↓ decode, dedupe on (sensor_id, f_cnt)
              [same ingest path as HTTPS]

                   BACKEND:
              [INSERT ... ON CONFLICT DO NOTHING into sensor_readings]
                   ↓ (every 15 min)
              [CRON: REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m]
                   ↓
              [revalidateTag('streets:list'), revalidateTag(`street:${id}`)]
                   ↓
              [Next.js cache invalidated; next public request re-reads MV]

                   FRONT-END:
              [/[city]/page.tsx — RSC]
                   ├─ MapShell: 'use cache' — static OSM basemap + streets GeoJSON
                   └─ <Suspense>
                        └─ MetricsPainter — reads streetsRepo.latestMetrics()
                              ↓
                        [MapLibre setFeatureState(street_id, {count, speed})]
                              ↓
                        [line-color: interpolate → viridis/cividis ramp]
```

### State management

- **Edge, in-memory:** `WindowedCounter.seen_track_ids` (cleared per window), `DailyAccumulator._totals` (cleared per UTC midnight).
- **Edge, durable:** `state.db` (daily_totals, sensor_meta) + `state.outbox.db` (FIFO). WAL mode. Reboot-safe.
- **Cloud, durable:** raw `sensor_readings` (13-month retention), `sensor_daily_totals`, `sensor_heartbeats` (14 days).
- **Cloud, derived:** `street_readings_{15m,hourly}` materialized views.
- **Cloud, cache:** Next.js cache-component tags (`streets:list`, `street:{id}`); Vercel edge cache on `/api/streets`.
- **Client UI:** `useState` for metric/class/window; URL hash for viewport (`#z/lat/lon`); URL query for filters (`?m=counts&w=1h`).

### Key data flows

1. **Uplink (HTTPS):** 15-min window → HTTPS POST → Postgres INSERT (idempotent) → MV refresh in ≤15 min → public map repaint on next poll or tag-revalidate.
2. **Uplink (LoRa):** 15-min window → ≤200-B codec → TTN → webhook → same INSERT path; `f_cnt` dedupes multi-gateway receptions.
3. **Config downlink:** Admin PATCHes `sensors.config_json` → `config_version` bumped → next HTTPS response includes `latest_config_version` → device GETs `/config` → applies hot. **No LoRa downlink in v1.**
4. **Heartbeat:** 5-min cadence → HTTPS only in v1 (LoRa airtime is too precious for heartbeats under TTN fair use).
5. **Reconciliation:** 01:00 UTC cron sums windows; flags mismatches; writes `audit_log`.
6. **Right-to-erasure:** `DELETE FROM sensors WHERE id = ?` → `ON DELETE CASCADE` to readings, heartbeats, coverage → MV rebuilt minus that sensor → historical public aggregates already contained no `sensor_id` (anonymous under EDPB aggregation guidance).

---

## Scaling Considerations

CAMINA's north star is **one Pi on one Dublin street for ≥1 week**. Scale discussion is only relevant if v2 happens.

| Scale                 | Adjustments                                                                                                                                 |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| v1 (1–10 sensors)     | No change. Current stack already over-provisioned. Neon free tier + Vercel hobby suffice.                                                    |
| v1.x (10–100 sensors) | Add Upstash rate-limit on `/api/ingest/*` (already planned). MV refresh moves from 15 min to 5 min if needed.                               |
| v2 (100–1000 sensors) | Partition `sensor_readings` by week (from monthly). Move heartbeats off MV path entirely. Consider TimescaleDB hypertables at this point.    |
| v2+ (1000+ sensors)   | Split device-facing ingest to its own Vercel project (smaller deploy surface). Consider a message queue (Vercel Queues, GA) in front of DB.  |

### Scaling priorities — what breaks first

1. **TTN fair-use airtime** at ≥100 LoRa sensors on the community plan. At 96 uplinks/day per sensor × ~200 ms airtime = ~19 s/day/sensor (within the 30 s cap, but thin). Mitigation: lengthen publish interval to 30 min for LoRa-only sensors, or self-host a gateway to leave the fair-use regime.
2. **MV refresh latency** if sensor count grows without partition tuning. Mitigation above.
3. **Connection exhaustion** on Neon — Fluid Compute reuses warm instances so a TCP pool of ~10 is normally sufficient. If cold-start rate climbs, switch to `@neondatabase/serverless` HTTP driver for routes that do one-shot reads.

---

## Anti-Patterns

### Anti-Pattern 1 — Branching transports inside `SensorDaemon`

**What people do:** Add `if config.transport == "lora": self._post_via_lora(...)` sprinkled through the daemon.
**Why it's wrong:** Every subsequent feature (retries, config-poller, heartbeats, metrics) inherits the branch. Test matrix doubles. `OfflineBuffer` ends up with transport-specific logic.
**Do this instead:** Extract the `Publisher` interface **before** writing `LoRaPublisher`. Refactor is ~50–100 lines of edits in `sensor_daemon.py` plus one new file. Do it first.

### Anti-Pattern 2 — Using TTN for heartbeats or config polls

**What people do:** Port the full HTTPS protocol to LoRa.
**Why it's wrong:** TTN fair-use policy is **30 s airtime/day per device** (community network). A 15-min publish cadence already burns most of that budget. Heartbeats (5 min, 288/day) would blow the cap, and TTN throttles/disconnects over-budget devices. LoRa downlink capacity is ~10 msg/day — not enough for config poll.
**Do this instead:** LoRa = counts only, uplink only, 15-min cadence (or 30-min if airtime is tight). HTTPS = counts + daily + heartbeat + config. Sensors configured `transport=lora` have no config-poller and no heartbeat; the backend treats "no heartbeat" as normal for these and uses uplink timestamps for liveness.

### Anti-Pattern 3 — Swapping systemd for Docker on the Pi for v1

**What people do:** Wrap the daemon in Docker "for parity with production".
**Why it's wrong:** Single-node edge, solo researcher, TRL-6 demo. Docker adds image-build pipeline, registry, update ceremony, overlay-network questions — all for zero benefit at N=1. systemd + `apt install` + `pip` is the reference deployment for research Pi fleets; Balena/Docker becomes compelling at 10+ devices needing OTA (explicitly deferred to TRL-7).
**Do this instead:** Keep `deploy/systemd/camina-sensor.service`. Document `journalctl -u camina-sensor -f` as the log-viewing command. Add Docker at TRL-7 if and when a second site needs it.

### Anti-Pattern 4 — TimescaleDB for ≤10 sensors

**What people do:** Adopt hypertables because "it's time series".
**Why it's wrong:** CAMINA's volume is ~3.15 M rows/year at the single-Pi scale. BRIN on `window_start` + monthly RANGE partitioning is ≤50 lines of DDL and uses vanilla Postgres. TimescaleDB adds an extension dependency, operational learning curve, and is not yet available as a first-class Neon-Marketplace feature. The current plan's explicit rejection is correct.
**Do this instead:** Keep the existing schema (already shipped). Revisit at >10 M rows/year.

### Anti-Pattern 5 — Storing GPS in client state or URL

**What people do:** A "centre map on sensor" button that encodes sensor lat/lon in the URL hash.
**Why it's wrong:** Breaks the privacy contract and the privacy regression test.
**Do this instead:** "Centre on street" uses the street centroid (PostGIS `ST_Centroid(geom)`), which is already public-safe. GPS never leaves the server.

### Anti-Pattern 6 — Deferring the Pi benchmark to M2

**What people do:** Trust unit tests for the edge pipeline and only run it on Pi during integration week.
**Why it's wrong:** FPS / thermal / memory on Pi 5 are the highest-risk unknowns in the whole project. If YOLO11n + NCNN on Pi 5 can't sustain the target FPS with the Kalman tracker, the whole windowing design is moot.
**Do this instead:** Benchmark in week 1 of M1. `scripts/run_sensor.py` + `docs/sensor_deployment.md §benchmark` first. Everything else is downstream of that number.

---

## Integration Points

### External Services

| Service                    | Integration Pattern                                                | Notes / Gotchas                                                                                     |
|----------------------------|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| The Things Network (TTN)   | Webhook HTTP POST → `/api/ingest/lora/uplink` with Basic/HMAC auth | **Fair use: 30 s airtime/day uplink, 10 msg/day downlink.** Needs Dublin coverage check before M1 starts. |
| Neon Postgres              | postgres-js driver over TCP, connection pooled by Fluid Compute    | Use `DATABASE_URL` (pooled) for routes, `DATABASE_URL_UNPOOLED` for migrations. HTTP driver only if cold-start rate climbs. |
| Google OAuth               | Auth.js v5 provider                                                 | UCD Google Workspace can take days to verify; start early. Allowlist domain `ucd.ie` as `viewer`.    |
| Vercel Cron                | `vercel.ts::crons`; invoked via HTTPS with `VERCEL_CRON_SECRET`    | Max 3 retries; idempotent bodies mandatory. Cron does not wake Neon on its own — current schedule does in practice (every 15 min is frequent enough). |
| Upstash Redis (Ratelimit)  | Marketplace integration; per-device + per-IP                       | Cheap; already planned.                                                                              |
| Vercel BotID               | Middleware/proxy layer on `/sign-in` + admin mutations             | GA since 2025-06. No config for legitimate users.                                                    |
| Sentry                     | Client + server SDK                                                 | **Must configure PII scrubber** — counts/speeds are non-PII but sensor IDs and admin emails are.    |
| Protomaps PMTiles          | Static file on Vercel Blob                                          | Planned for production; dev uses local Carto Positron tiles already committed.                       |

### Internal boundaries

| Boundary                          | Communication              | Notes                                                                                  |
|-----------------------------------|----------------------------|----------------------------------------------------------------------------------------|
| `core/*` ↔ `io/*`                 | Dataclass snapshots        | Keeps `core` pure; any I/O test stub works without real network.                       |
| `io/Publisher` ↔ `OfflineBuffer`  | `(endpoint, payload)`      | The whole dual-transport hinge. Schema already transport-agnostic.                      |
| `io/schemas.py` ↔ `lib/schemas.ts`| JSON over wire             | Shared `schema_version` field; both sides zod/dataclass-validated. Extend same way for LoRa codec. |
| RSC ↔ `lib/repo`                  | Async function calls       | Server-only import. `streets-mock` / `streets-live` implement identical interface.     |
| Public API ↔ Admin API            | Type-level separation      | `StreetSummary` vs `StreetAdminInfo`. Regression test enforces at CI.                  |
| Ingest routes ↔ DB                | Drizzle + zod               | Ingest returns 202 fast; write is synchronous + idempotent PK.                          |

---

## Comparison: CAMINA vs 2026 Best Practice

| Decision                        | CAMINA's current choice            | 2026 best practice                                    | Verdict                                                              |
|---------------------------------|------------------------------------|-------------------------------------------------------|----------------------------------------------------------------------|
| Edge deployment                 | systemd service on Pi 5            | systemd (<10 sensors) or Balena/Docker (10+)          | ✓ Aligned for v1. Keep.                                              |
| Primary transport               | HTTPS POST over WiFi               | HTTPS for ≤500 devices at 15-min cadence              | ✓ Aligned. MQTT rejection was correct.                                |
| Secondary transport             | LoRaWAN Class A uplink, TTN        | LoRa for network-poor sites; TTN for research         | ✓ Aligned, with caveats on fair-use budget.                          |
| Downlinks                       | None (uplink-only)                 | Uplink-only for ≤10 msg/day TTN policy                | ✓ Aligned. Downlinks are for commercial/self-hosted networks.        |
| Serverless ingest               | Vercel Fluid Compute (Node 24)     | Fluid > Edge Functions for anything with a DB client  | ✓ Aligned. Edge Functions would have forced HTTP driver.             |
| DB driver                       | postgres-js / TCP pool              | TCP + pool for Fluid; HTTP driver only for high cold-start | ✓ Aligned (already wired lazily in `dashboard/src/lib/db.ts`).        |
| Time-series storage             | Neon + BRIN + monthly partitions   | TimescaleDB only at >10 M rows/year                   | ✓ Aligned. Rejection of Timescale was correct.                        |
| Aggregate refresh               | `REFRESH MATERIALIZED VIEW CONCURRENTLY` every 15 min | CONCURRENTLY; 5–15 min cadence typical      | ✓ Aligned.                                                            |
| Right-to-erasure                | `DELETE FROM sensors` cascades raw; MV stays (aggregate = anonymous) | EDPB-compatible when MV strips identifiers | ✓ Aligned (the MV drops `sensor_id` by construction).                |
| Auth                            | Auth.js v5 + Google + allowlist    | Match                                                  | ✓ Aligned.                                                            |
| Front-end rendering             | Next.js 16 RSC + dynamic-import MapLible, PPR deferred | Static shell + `<Suspense>` streams         | ⚠ **Not yet aligned** — `cacheComponents: true` commented out pending Suspense wrappers. Low-hanging fruit. |
| Privacy model                   | Type-enforced + regression test    | Match or exceed                                       | ✓ Aligned.                                                            |
| Mock/live toggle                | `CAMINA_DATA_SOURCE` env + repo pattern | Match                                              | ✓ Aligned.                                                            |
| OTA updates                     | Deferred to TRL-7                   | Deferred for single-node research; Balena for fleets  | ✓ Aligned.                                                            |

---

## Build-Order Recommendation (5-Week Sprint)

The research finding that most shifts the build order: **TTN coverage in Dublin is not yet verified and LoRa hardware is not yet procured**. These are the longest-lead items and the only items with non-software dependencies. They must start week 1 — even if the code lands later.

### Recommended sequence (re-weights the two-milestone plan)

**Week 1 — kill the highest-risk unknowns in parallel.**
- **Edge path:** write `scripts/run_sensor.py`. Run the full real-hardware pipeline once. Capture FPS / CPU temp / memory. If FPS is too low, reduce to 5 FPS + frame-skip and measure again. Decision gate for the whole project lives here.
- **Transport refactor:** extract `Publisher` interface from `HttpsPublisher`. Zero-behaviour-change refactor, unlocks LoRa work.
- **LoRa pre-work (no code):** confirm TTN coverage at target Dublin street (TTN Mapper + community forum). Procure LoRa HAT (RAK2287 or similar). Design ≤200-B codec on paper (9 classes × 2 bytes = 18 B + camera ID 3 B + timestamp 5 B = 26 B; easily fits). Compute airtime at SF7 (≈50 ms) → 96 uplinks/day × 50 ms = 4.8 s/day ≪ 30 s budget.
- **Dashboard PPR cleanup:** wrap `[city]/page.tsx` and `street/[slug]/page.tsx` in `<Suspense>`; re-enable `cacheComponents: true`; re-enable `reactStrictMode` once MapLibre init race is re-tested.

**Week 2 — deliver the edge demo, in two places.**
- Pi benchmark documented in `docs/sensor_deployment.md`.
- End-to-end Pi → Vercel-preview HTTPS → mock DB path exercised for 24 h continuous.
- `LoRaPublisher` + `lora_codec.py` + joint test vectors.
- `/api/ingest/lora/uplink` route + TTN webhook wired against a real TTN dev device (not the Pi yet).

**Week 3 — land the cloud live half.**
- Neon provisioned; migration `0000_init.sql` applied.
- `streets-live.ts` implemented (was throwing); mock/live parity tests.
- Admin CRUD: `SensorForm`, `StreetDrawTool`, `/admin/members`, audit rows.
- Cron bodies (refresh-aggregates, detect-silent, reconcile-daily) implemented.
- Google OAuth live; dev-allowlist env fallback removed.

**Week 4 — harden and deploy.**
- BotID, CSP, Upstash rate limits, Sentry.
- Rolling Releases; `/api/health`; uptime monitor.
- Integration: Pi over LoRa → TTN → production Vercel → live Postgres → public map (7-day soak).

**Week 5 — 1-week TRL-6 soak, paper/benchmark drafts, margin for failure.**
- If week 2 slipped (most likely: Pi FPS surprise or TTN coverage gap), this week absorbs it.
- If everything on schedule, Pi deployed on the real Dublin street; dashboard live; `RUNBOOK.md` finalised.

### What this re-ordering changes vs the current plan

The current plan puts `scripts/run_sensor.py` and the LoRa stack both inside M1 (by 2026-05-15). That is too much unvalidated hardware work for one milestone. The re-order above splits it:

- **Non-negotiable week-1 spike:** Pi FPS benchmark + TTN coverage verification. If either fails, scope collapses (e.g. drop LoRa, stay HTTPS-only on WiFi).
- **Transport-abstraction refactor first:** prevents the LoRa work from touching `SensorDaemon` internals.
- **Cloud live half moves to week 3:** currently M2 stretches from 2026-05-15 to 2026-05-31. Two weeks is tight for Neon + OAuth + admin CRUD + crons + Rolling Releases. Starting week 3 gives 2 full weeks plus a buffer.
- **Week 5 is reserved for integration soak** — not new features. This matches how "one Pi on one real street for ≥1 week" actually works in research deployments.

### What breaks this plan

| Risk                                          | Mitigation                                                                                     |
|-----------------------------------------------|------------------------------------------------------------------------------------------------|
| Pi 5 FPS below threshold with YOLO11n NCNN    | Already have 8GB headroom; drop to YOLO11n-seg off, reduce input resolution, use frame-skip.   |
| TTN gateway not in range of target Dublin street | Fall back to HTTPS-only (WiFi on-site). Keep `LoRaPublisher` code; flag as future-work.       |
| Neon PostGIS gotcha                            | PostGIS is supported on Neon (verified in Neon docs). Keep migrations in raw SQL for PostGIS DDL. |
| Google OAuth verification slow                 | Start week 1. Use personal allowlist `CAMINA_DEV_ALLOWED_EMAILS` until verified.               |
| MapLibre Strict-Mode double-mount regression   | Already known; current mitigation is `reactStrictMode: false`. Re-enable after PPR cleanup; guard with dedicated Vitest + Playwright test before re-enabling.  |

---

## Sources

- [The Things Network — Fair Use Policy explained](https://www.thethingsnetwork.org/forum/t/fair-use-policy-explained/1300) — confirms 30 s airtime/day uplink, 10 msg/day downlink cap (HIGH).
- [The Things Network — Duty Cycle](https://www.thethingsnetwork.org/docs/lorawan/duty-cycle/) — regulatory vs TTN policy (HIGH).
- [The Things Stack — Webhooks](https://www.thethingsindustries.com/docs/integrations/webhooks/) — TTN uplink webhook mechanics (HIGH).
- [Neon — Connecting to Neon from Vercel](https://neon.com/docs/guides/vercel-connection-methods) — TCP + pool recommendation for Fluid (HIGH).
- [Vercel — Efficiently manage DB connection pools with Fluid Compute](https://vercel.com/kb/guide/efficiently-manage-database-connection-pools-with-fluid-compute) — instance reuse model (HIGH).
- [Neon — `postgis` extension](https://neon.com/docs/extensions/postgis) — Neon PostGIS support (HIGH).
- [Neon — Serverless driver](https://neon.com/docs/serverless/serverless-driver) — when HTTP driver beats TCP (MEDIUM).
- [PostgreSQL — REFRESH MATERIALIZED VIEW](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html) — CONCURRENTLY requires UNIQUE index (HIGH).
- [Next.js 16 — Streaming](https://nextjs.org/docs/app/guides/streaming) — Suspense + PPR mechanics (HIGH).
- [Next.js 16 — PPR Platform Guide](https://nextjs.org/docs/app/guides/ppr-platform-guide) — mixing static shell and dynamic streams (HIGH).
- [EDPB — Right to erasure coordinated enforcement action](https://www.edpb.europa.eu/our-work-tools/our-documents/other/coordinated-enforcement-action-implementation-right-erasure_en) — aggregation-as-anonymisation threshold (MEDIUM).
- [Ultralytics — Raspberry Pi 5 object detection with YOLO](https://www.raspberrypi.com/news/object-detection-with-ultralytics-yolo26-on-raspberry-pi/) — Pi 5 + NCNN reference deployment (MEDIUM).
- [Roboflow — Deploy CV models to Raspberry Pi with Docker](https://blog.roboflow.com/deploy-computer-vision-models-raspberry-pi-docker/) — Docker vs systemd tradeoff context (MEDIUM).
- [LoRa Alliance — LoRaWAN Payload Codec API](https://resources.lora-alliance.org/home/lorawan-payload-codec-api) — codec conventions for compact uplink (MEDIUM).

---

*Architecture research for: privacy-first edge-CV + serverless-dashboard (CAMINA, TRL-6)*
*Researched: 2026-04-23*
