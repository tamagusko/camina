# Stack Research

**Project:** CAMINA — Dublin privacy-first traffic sensor
**Domain:** Brownfield — finishing an in-flight TRL-6 demo (5-week window)
**Researched:** 2026-04-23
**Overall confidence:** HIGH (Pi edge + Vercel cloud) / MEDIUM (LoRaWAN — hardware not yet on-hand)

---

## Executive Verdict

Your existing stack is **largely correct for 2026**. The big-picture choices (YOLO11 + NCNN + filterpy Kalman, HTTPS primary transport, Next.js 16 App Router on Fluid Compute, Neon + Drizzle + PostGIS, MapLibre + Protomaps, Auth.js v5 + Google) match current best practice. The gaps are **finishing details**, not architecture changes. In priority order:

1. **Finish the NCNN path** on Pi 5 — your edge benchmark is the only unknown that can invalidate the TRL-6 demo.
2. **Pick RAK3172-as-a-module + TTN Dublin** for LoRa (don't self-host ChirpStack for v1).
3. **Wire `attachDatabasePool` from `@vercel/functions`** — your current Drizzle+postgres.js setup on Fluid Compute needs this to avoid connection exhaustion under Rolling Releases.
4. **Keep `cacheComponents` disabled** for the TRL-6 demo — Suspense-wrap later; see Pitfalls.
5. **Don't buy a Hailo AI HAT** for v1 — ~8 FPS NCNN on CPU is sufficient for 15-min windowed counting and Hailo adds ~€80 + an untested software path under your 5-week deadline.

---

## Part A — Pi 5 Edge Inference

**Confidence:** HIGH. Verified against Ultralytics official docs (via Context7) + multiple independent 2026 benchmarks.

### Recommended Core Stack (keep what you have, finish the wiring)

| Technology | Version | Purpose | Why Recommended (2026) |
|------------|---------|---------|------------------------|
| **Python** | **3.11** (upgrade from 3.10) | Edge agent runtime | 3.11 gives 10–25 % speedup over 3.10 on CPython workloads; picamera2 + libcamera + Ultralytics all support 3.11 on Raspberry Pi OS Bookworm. 3.13 works but is newer; 3.11 is the sweet spot on Pi 5. |
| **Ultralytics** | **`8.3.x`** (current) | YOLO11 model + NCNN export | Your pinned `8.3.123` is fine; current stable 8.3 line supports NCNN export and YOLO11. Upgrading to the `8.3.x` head at end of M1 is low-risk. |
| **PyTorch** | **`2.7.x`** | Model loading + NCNN conversion only | Inference runs via NCNN, so torch is just used at export time and for `yolo11n.pt` loading in tests. Current pin is correct. |
| **NCNN (via Ultralytics export)** | bundled | Production ARM inference | **Confirmed SOTA for Pi 5 ARM64.** Ultralytics docs explicitly: *"Out of all the model export formats supported by Ultralytics, NCNN delivers the best inference performance when working with Raspberry Pi devices."* Cuts inference time up to 62 % vs PyTorch. |
| **picamera2** | latest (apt) | Camera capture pipeline | Official Raspberry Pi library, integrates with libcamera stack. **Strongly preferred over OpenCV `VideoCapture`** for Pi Camera Module 3 — gives direct RGB888 arrays into numpy without format conversion overhead. |
| **libcamera** | system package | Underlying camera stack | The only supported stack on Bookworm for Pi Camera Module 3. Your `cv2.VideoCapture` in `app.py` works for USB webcams but will not expose full Camera Module 3 capability; Plan 01 `frame_source` injection makes the swap trivial. |
| **OpenCV** | **4.11.0.86** (opencv-python-headless on Pi) | Frame drawing + resizing | Switch Pi install to `opencv-python-headless` to avoid pulling in Qt/GTK dependencies on a headless daemon. Your dev machine can keep full `opencv-python`. |
| **filterpy + scipy** | `1.4.5` / `1.15.2` | Kalman + Hungarian tracker | Custom tracker is the right call — DeepSORT-style learned re-id is overkill for single-camera aggregate counting and contradicts your privacy model. No changes needed. |
| **httpx** | `>=0.27` | HTTPS publisher | Current choice is correct. Keep. |
| **pydantic** | `>=2.5` | Wire schemas | Current choice is correct. Keep. |
| **systemd + sdnotify** | via `systemd-watchdog` PyPI | Service supervision + liveness | **ADD THIS.** Set `Type=notify` and `WatchdogSec=60` in `camina-sensor.service`; daemon calls `sd_notify("WATCHDOG=1")` once per window. Catches stuck/zombie detector thread (e.g., camera wedged, GIL-locked worker). This is the 2026 best practice per RHEL/Ubuntu systemd guides. |

### Camera Pipeline — Preferred Path

**Pi Camera Module 3 → picamera2 → YOLO NCNN → custom tracker → WindowedCounter**

Reference pattern (straight from Ultralytics docs, adapted for your daemon):

```python
from picamera2 import Picamera2
from ultralytics import YOLO

picam2 = Picamera2()
picam2.preview_configuration.main.size = (640, 640)   # match YOLO input
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.align()
picam2.configure("preview")
picam2.start()

model = YOLO("models/20250629_warmup_best_ncnn_model")   # NCNN dir

def frame_source():
    while True:
        yield picam2.capture_array()

def detect_and_track(frame):
    results = model(frame, verbose=False, imgsz=640, conf=0.3)
    # feed to tracker.py (existing)
    ...
```

Wire this into `scripts/run_sensor.py` (your pending TODO). Keep the `frame_source`/`detect_and_track` injection contract so CI remains import-safe.

### Performance Expectations (Pi 5 8GB, 640×640, YOLO11n NCNN)

| Config | Expected FPS | Source |
|--------|--------------|--------|
| YOLO11n NCNN, stock | **6.8–8 FPS** | Ultralytics 2026 benchmarks + learnopencv |
| YOLO11n NCNN + imgsz=480 | **10–12 FPS** | learnopencv 2026 |
| YOLO11n NCNN + quantized/FP16 | +10–20 % | NCNN built-in quantization |
| YOLO26n NCNN (if you retrain) | ~15 % faster than YOLO11n | Ultralytics YOLO26 benchmarks |

**Implication for CAMINA:** at 7 FPS with `frame_skip=3` you get ~2.3 effective detection Hz, which is plenty for 15-minute aggregate counting of road users. **You do not need a Hailo accelerator for the TRL-6 demo.**

### Thermal & Power

Pi 5 8GB under sustained YOLO11n NCNN inference runs at ~55–65 °C with the official **Active Cooler** fan (£5). Without a fan, expect thermal throttling after ~5 min of continuous inference. Budget £5 + 5 min install; do not skip.

- Read `/sys/class/thermal/thermal_zone0/temp` every heartbeat (you already do).
- Alert via heartbeat flag when CPU temp > 75 °C sustained.

### Explicit "Don't Use" — Pi Edge

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Hailo-8L AI HAT for v1** | +€80/unit; requires HailoRT Python bindings + .HEF model compilation pipeline; YOLO11n on Hailo-8 clocks 11 FPS — only marginally better than NCNN CPU for your workload. Untested integration path under a 5-week deadline = risk you cannot afford. | Pure NCNN CPU inference. Revisit Hailo at TRL-7 if you scale to multi-camera or higher resolution. |
| **ONNX Runtime** | Works on Pi 5 but slower than NCNN for ARM (NCNN was built for this). INT8 ONNX quantization helps but still loses to NCNN FP16 in published benchmarks. | NCNN export (`model.export(format='ncnn')`). |
| **TorchScript at inference time** | Your `yolo11n.torchscript` committed in the repo — OK for testing, but ~2.5× slower than NCNN on Pi 5 CPU. | NCNN for production; keep torchscript for CI smoke tests only. Consider removing the 11 MB `yolo11n.torchscript` from git after NCNN wiring is proven (already flagged in CONCERNS.md). |
| **Docker on Pi** | Adds ~150 MB overhead, doubles systemd complexity, solves no real problem for a single-daemon deployment. | Bare systemd unit + venv (what you already have). |
| **cv2.VideoCapture with Pi Camera Module 3** | Works via V4L2 shim but loses format control (always YUV420 → BGR, extra conversion) and blocks full resolution modes. | `picamera2` + RGB888 output. Keep `cv2.VideoCapture` only for USB webcam dev path. |
| **`opencv-python` on Pi** | Pulls in Qt/GTK GUI libs (~150 MB) that the headless daemon never uses. | `opencv-python-headless` in the Pi-specific requirements file. |
| **Raspberry Pi AI Camera (Sony IMX500)** | IMX500 on-sensor NPU is neat but requires the `imx` export format and locks you into YOLO11/26 as supplied by Sony. Not worth the retooling for the demo window. | Pi Camera Module 3 (standard) + Pi 5 CPU NCNN. |

### systemd Hardening — Concrete Additions

Your current `deploy/systemd/camina-sensor.service` is solid. Add for TRL-6:

```ini
[Service]
Type=notify
WatchdogSec=60
Restart=on-failure
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300
# Resource caps so a wedged detector can't OOM the Pi
MemoryMax=4G
CPUQuota=380%          # 4 cores × ~95%
# Journald rotation
StandardOutput=journal
StandardError=journal
```

And in `/etc/systemd/journald.conf.d/camina.conf`:

```ini
[Journal]
Storage=persistent
SystemMaxUse=500M
SystemMaxFileSize=50M
MaxRetentionSec=30day
```

---

## Part B — LoRaWAN ≤200-char Transport

**Confidence:** MEDIUM. Hardware not yet on-hand; TTN Dublin coverage needs ground-truth verification before committing.

### Recommended Core Stack

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **LoRa module** | **RAK3172 (Breakout or WisBlock)** | End-device radio | ARM Cortex-M4 + SX1262; EU868 Class A/B/C; 1.69 µA sleep; AT-command interface over UART = trivial to drive from Python on the Pi. €10–15 per unit. **Preferred over Dragino RS485-LN** (which is an RS485-to-LoRa bridge, wrong abstraction for an on-Pi radio). |
| **Alternative: Heltec HT-RA62 USB dongle** | current | Plug-and-play option | If you want USB-not-UART, Heltec's USB LoRaWAN dongles work. Slightly more expensive, slightly easier install. RAK3172 is lower-risk for production. |
| **LoRaWAN network server** | **The Things Network Community v3 (TTN / TTS Community)** | Device management + webhook | **Zero infra for v1.** Free community tier. Webhook integration posts JSON to your `/api/ingest/lora/*` endpoint. Dublin community exists but coverage is **thin** (TTN map shows most of central Dublin has 1 gateway at best) — **you may need to host a gateway yourself** at the deployment site. |
| **Gateway (if needed)** | **The Things Indoor Gateway (TTIG) EU868** | Local coverage | €90 plug-and-play indoor gateway, 8-channel SX1308. Sufficient for ≤500 m radius. Deploy at UCD or near the sensor site if TTN community coverage fails. |
| **Payload encoder** | **Custom compact bit-pack** (not CayenneLPP) | ≤200-char payload | Your 9 counts + camera ID + timestamp fit in ~20 bytes raw. CayenneLPP is overhead-heavy (2 bytes channel+type per field) and wasteful here. See encoding below. |
| **Python LoRa library** | **pyserial + custom AT driver** | UART comms to RAK3172 | Thin wrapper around AT commands (`AT+JOIN`, `AT+SEND=port:hex-payload`). **Don't use paho-lorawan or abstracted libraries** — the AT interface is tiny and hand-rolled code is easier to debug on a Pi. |
| **TTN webhook integration** | built-in | Dashboard ingest | TTS Community includes a webhook integration that POSTs uplinks as JSON to your chosen URL. No MQTT broker needed from TTN to dashboard. |

### Payload Encoding — Concrete Proposal

Your spec: camera ID `LNN` (3 ASCII), timestamp `YYMMDDHHMM` (10 ASCII), 9 class counts.

A LoRaWAN EU868 SF7 uplink payload can be up to **242 bytes**; at SF12 it drops to **51 bytes**. Your ≤200-char constraint is the HTTPS-compatible ASCII representation (hex/base64), meaning the binary payload is ≤100 bytes for hex or ≤150 bytes for base64. Plenty of room.

**Recommended binary layout (17 bytes):**

```
byte 0..2   camera_id ascii "D01" (3 bytes, printable)
byte 3..6   epoch_minute_since_2026 (uint32 little-endian; covers 8000 years)
byte 7..15  9× uint8 class counts (0..255 per window — sufficient for 15-min bucket)
byte 16     schema_version (0x01)
```

- **If counts can exceed 255 in 15 min** (e.g., cars on a busy road): promote cars to uint16 → 18 bytes.
- **No CayenneLPP.** CayenneLPP's channel+type framing adds ~2 bytes per field × 9 = 18 bytes of pure overhead for identical information.
- Encode as **base64 → 24 characters** in the webhook JSON. Well under 200.
- Validate both ends with a single `struct.pack`/`struct.unpack` contract mirrored in TypeScript (`Buffer.from(b64, 'base64')`).

### LoRaPublisher Architecture

Parallel to `HttpsPublisher`, behind the same `Publisher` protocol:

```
src/camina/io/lora_publisher.py
├── class LoRaPublisher:
│     def __init__(self, uart_device, dev_eui, app_key, confirmed=False): ...
│     def post_counts(self, snapshot) -> PublishResult: ...
│     def post_daily(self, snapshot) -> PublishResult: ...
│     def post_heartbeat(self, hb) -> PublishResult: ...
│
│     # Internals:
│     def _join(self): AT+JOIN until success (backoff)
│     def _send(self, port: int, payload_b64: str): AT+SEND=...
│     def _encode_counts(self, snapshot) -> bytes: struct.pack
```

**No `/config` endpoint over LoRa.** LoRaWAN Class A downlinks are only allowed in the 1-s and 2-s receive windows after an uplink and are bandwidth-starved. Config stays HTTPS-only; LoRa is uplink-only telemetry.

### Transport Selection

Your Plan 01 design (`configs/sensor.yaml` → `transport: https | lora | both`) is correct. For `both`, emit counts and daily over LoRa (robust, cheap) and keep heartbeats + config polling over HTTPS (richer, lower duty-cycle concern).

### Dashboard-side — `/api/ingest/lora/*`

- **Single webhook endpoint:** `POST /api/ingest/lora/uplink`.
- TTN webhook header includes `X-Downlink-Apikey` — verify it against an env var.
- Body includes `end_device_ids.device_id` (→ your `sensor_id`), `uplink_message.frm_payload` (base64 bytes), `uplink_message.received_at`.
- Decode → same downstream writer as HTTPS ingest → same Neon tables. **Reuse the same Drizzle repo methods.**
- Idempotency: `(sensor_id, window_start, class_name)` PK on `sensor_readings` dedupes if TTN retries.

### Explicit "Don't Use" — LoRaWAN

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **CayenneLPP encoding** | 2 bytes of channel+type overhead per field is wasteful when your schema is fixed. | Custom 17-byte struct.pack layout (above). |
| **Self-hosted ChirpStack for v1** | Adds PostgreSQL + Redis + ChirpStack services to self-host. Useful for commercial deployments with multi-tenant needs. Overkill for "one Pi, one street." | TTN Community v3 + free webhook integration. Revisit ChirpStack at TRL-7 only if TTN community limits become a problem. |
| **MQTT as LoRa transport to dashboard** | TTN supports MQTT, but you already rejected MQTT in Plan 01 (Vercel is serverless). Don't re-introduce it for the LoRa path. | TTN webhook → Vercel route. |
| **Dragino RS485-LN as end-device radio** | It's a sensor-bridge product (RS485 field bus → LoRaWAN), not a radio module for a host system. Your README mentions it but it's the wrong abstraction. | RAK3172 breakout or WisBlock. |
| **LoRaWAN Class C** | Continuously-listening mode drains power and doesn't help uplink-only telemetry. | Class A (your Plan 01 decision — correct). |
| **Confirmed uplinks for every message** | Confirmed uplinks eat downlink airtime (EU868 duty cycle 1 % → very scarce). Use only for `daily` payloads if you want end-to-end ACK. | Unconfirmed uplinks for 15-min counts; consider confirmed for daily only. |
| **Cross-gateway redundancy via multiple TTN apps** | TTN already handles multi-gateway receive-dedup at the network layer. | Single app, trust the network layer. |

### Duty Cycle Budget — Reality Check

EU868 enforces 1 % duty cycle on most sub-bands. At SF7, a 17-byte uplink takes ~50 ms airtime → 1 upload every 5 s is the ceiling per device. Your 15-min cadence is 900× lower than that. **You have enormous headroom.** Daily uplink (identical size) is fine. Heartbeat over LoRa (if ever enabled) still fits. Don't worry about duty cycle at this cadence.

---

## Part C — Vercel + Neon + Next.js 16 (Production)

**Confidence:** HIGH. Verified against Vercel docs (Context7) and current Neon/Drizzle guidance.

### Recommended Core Stack (keep, plus targeted additions)

| Technology | Version | Purpose | Why Recommended (2026) |
|------------|---------|---------|------------------------|
| **Next.js** | **`^16.0.0`** (stable) | App Router framework | Your `^16.0.0` pin is correct. Use Turbopack (default). Keep `proxy.ts` (v16 rename from middleware.ts). |
| **React** | **`^19.0.0`** | UI library | Correct. |
| **Node.js** | **22.11 LTS** (your `.nvmrc`) | Runtime | Your pin is correct. Vercel defaults to Node 24 LTS now — safe to bump in post-demo tech-debt. |
| **pnpm** | **`9.12.0`** | Package manager | Correct. |
| **Fluid Compute** | default | Runtime for all routes | Correct. **Do not use Edge runtime** for DB routes — Vercel themselves deprecated the "prefer Edge" guidance in 2026. Fluid gives full Node + instance reuse + 300 s timeout at the same price. |
| **`@vercel/functions`** | `^1.x` — **ADD THIS** | Connection pool lifecycle | **CRITICAL MISSING DEP.** Use `attachDatabasePool(pool)` immediately after creating your `postgres()` client so Fluid Compute releases idle connections before suspending the instance. Without this, you'll exhaust Neon's connection limit under Rolling Releases. |
| **Drizzle ORM** | **`^0.36.4`** | Type-safe SQL + migrations | Your pin is correct. Drizzle has mature PostGIS support (`geometry` + `geography` types with `tuple`/`xy` modes). |
| **drizzle-kit** | **`^0.29.1`** | Migrations + `drizzle-kit push/migrate` | Correct. |
| **postgres.js** | **`^3.4.5`** | Low-level PG driver | Correct choice over `pg` — postgres.js is lighter, has native WebSocket support, and your `{ max: 5, prepare: false }` setting is right for Neon pooled mode. Combine with `attachDatabasePool`. |
| **Neon Postgres + PostGIS** | latest (Marketplace) | Serverless DB | Correct. Use the **pooled** `DATABASE_URL` for app traffic, **unpooled** `DATABASE_URL_UNPOOLED` only for migrations (drizzle-kit). Your env split is correct. |
| **Auth.js v5** | **`^5.0.0-beta.25`** | Google OAuth | v5 is still in beta at 2026-04 but stable in practice for Google-only flows. Your implementation is correct. |
| **zod** | **`^3.23.8`** | Schema validation | Correct. Consider `^4.x` post-demo (breaking changes, not worth the churn pre-TRL-6). |
| **MapLibre GL JS** | **`^4.7.1`** | Map renderer | Correct. **Known issue:** incompatible with Turbopack dev server for clustering workers (issue #86495). Solution: keep your current non-clustered line layer approach — no clustering needed for street polylines anyway. |
| **PMTiles** | **`^3.2.0`** | Vector basemap format | Correct. Ship the Dublin extract via **Vercel Blob** (public, immutable, CDN-cached). Alternative: serve via `/basemap/*` route with `Cache-Control: public, max-age=1 week, immutable` already declared in your `vercel.ts`. |
| **Upstash Ratelimit** | **`@upstash/ratelimit@^2.x`** + **`@upstash/redis@^1.34.x`** — **ADD** | Rate limiting | Sliding window per device on `/api/ingest/*` and per IP on `/api/admin/*`. Your env vars are already declared; you just need to install and wire. |
| **Vercel BotID** | via `@vercel/functions` | Bot challenge | Wrap `/sign-in` submit and admin `PATCH` mutations. GA as of 2025-06. |
| **Sentry (`@sentry/nextjs`)** | **`^8.x`** — **ADD** | Error tracking | Install `@sentry/nextjs`, wire `instrumentation.ts`, `beforeSend` scrubber to strip `sensor_id`, `latitude`, `longitude` from event payloads (privacy invariant even in errors). |
| **Vercel Analytics** | **`@vercel/analytics@^1.x`** — **ADD** | Page view metrics | One-line install. Free on Hobby. |
| **Vercel Speed Insights** | **`@vercel/speed-insights@^1.x`** — **ADD** | CWV tracking | One-line install. Free on Hobby. |
| **Vitest** | **`^2.1.5`** | Unit tests | Correct. |
| **Playwright** | **`^1.48.0`** | E2E tests | Correct. |
| **Tailwind CSS** | **`^3.4.15`** | Styling | Your v3 pin is fine. Plan 02 mentioned v4 — don't migrate mid-milestone; v4 has breaking changes in `@import` syntax. |

### Connection Pool — Correct Pattern for Fluid Compute

Your current `dashboard/src/lib/db.ts`:

```typescript
// CURRENT
const client = postgres(url, { max: 5, prepare: false });
export const db = drizzle(client);
```

**Upgrade to:**

```typescript
// RECOMMENDED
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import { attachDatabasePool } from '@vercel/functions';

const client = postgres(process.env.DATABASE_URL!, {
  max: 5,
  idle_timeout: 5,      // close idle connections within 5s (Fluid best practice)
  prepare: false,       // required for Neon pooled connection
});

// Critical on Fluid Compute — releases idle connections before suspend
attachDatabasePool(client);

export const db = drizzle(client);
```

This single change prevents "too many connections" errors under Rolling Releases (new deployment + old deployment both holding pools).

### Drizzle + PostGIS — Your Schema is Right

Your `dashboard/drizzle/migrations/0000_init.sql` uses raw `GEOMETRY(MultiLineString, 4326)` + GIST indexes. This is the correct 2026 pattern — Drizzle's `geometry()` type maps to this directly. Confirmed against Drizzle official docs.

For post-demo polish, you can migrate the schema to Drizzle types:

```typescript
import { geometry } from 'drizzle-orm/pg-core';
// ...
geom: geometry('geom', { type: 'multilinestring', srid: 4326 }).notNull(),
```

But your current raw SQL migration is fine and ships today.

### Cron — Keep Current Schedules, Verify Rolling Release Interaction

Your three crons (`*/5`, `*/15`, `0 1`) are correct. **Watch:** Vercel Cron fires against the *current production deployment only*. During a Rolling Release (e.g., 10 % new, 90 % old), the cron still goes to whichever deployment is promoted as production. This means:

- Do **not** put migrations in cron (they'll run on the old build).
- Jobs must be idempotent on `(sensor_id, …)` — you already have this.
- A mid-rollout cron firing is safe as long as the job body is pure (materialized view refresh, silent-sensor detection, reconciliation — all idempotent ✓).

### Rolling Releases — Concrete Plan

Per Vercel's current docs, enable **10 % → 50 % → 100 %** with health gates. Recommended gates:

1. `/api/health` — 200 status
2. Response time p95 < 500 ms on `/api/streets` and `/api/metrics`
3. Error rate < 1 % on `/api/ingest/*`

Set **auto-abort on gate failure** so a bad deployment rolls back before it hurts devices in the field.

### cacheComponents — Status: Keep Disabled Until Post-Demo

Your `next.config.mjs` has `cacheComponents` commented. **Leave it commented for M1/M2.**

Why:
- Enabling `cacheComponents` requires every uncached `await` in RSC to be wrapped in `<Suspense>` or flagged with `use cache`.
- Your `/[city]/page.tsx` does `Promise.all([streetsRepo.list(city), streetsRepo.latestMetrics(...)])` at the route level — this will throw "Uncached data accessed outside of `<Suspense>`" the moment you enable it.
- Fixing this is straightforward but touches every dynamic page.
- It's a post-TRL-6 polish, not a demo blocker.

Track in tech-debt. When you re-enable, wrap dynamic reads in `<Suspense>` and the static shell (map canvas, controls) prerenders while data streams.

### reactStrictMode — Known Issue, Known Workaround

Your `reactStrictMode: false` workaround for MapLibre canvas sizing race is correct. Re-enable it after wrapping `StreetMap` init in a ref-guard (`useEffect` with `initialised.current` boolean). This is a 1-hour fix, low priority.

### Explicit "Don't Use" — Cloud

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Edge runtime for DB routes** | No pooled connections; small Node API subset; Vercel themselves now recommend Fluid. | Fluid Compute (default). |
| **`@neondatabase/serverless` WebSocket driver** | Fine on Edge, slower than postgres.js on Fluid for your workload. | postgres.js + `attachDatabasePool`. |
| **`pg` (node-postgres)** | Heavier than postgres.js, no built-in WebSocket path, prepared statements mismatch Neon pooler defaults. | postgres.js (your current choice). |
| **TimescaleDB** | Already rejected in Plan 02. ≤2 M rows/year doesn't need it. | Plain Postgres + materialized views refreshed by cron. |
| **Supabase** | Bundles auth/storage you'd ignore; pricing less favorable for the Vercel research tier. | Neon via Vercel Marketplace. |
| **Tailwind CSS v4 migration mid-milestone** | Breaking `@import "tailwindcss"` syntax + config changes. High risk for 5-week window. | Stay on v3.4.15; schedule v4 post-demo. |
| **zod v4 migration mid-milestone** | Breaking error API changes. | Stay on v3.23.8. |
| **`cacheComponents: true` before M2 ships** | Requires Suspense boundaries around every dynamic read. | Keep commented; fix in tech-debt phase. |
| **Client-side data fetching with `useEffect` for admin data** | Duplicates logic, risks privacy leaks if a client bundle accidentally imports a server-only repo. | Server Components + `server-only` import (you already do this — keep enforcing). |
| **Vercel's `ioredis`-over-HTTP** | Upstash Redis REST is simpler and already in your env vars. | `@upstash/redis` + `@upstash/ratelimit`. |
| **Adding a session store (Redis) for Auth.js** | JWT sessions are fine for ≤500 users. Redis adds complexity. | Auth.js default JWT session. |
| **Vercel KV** | Deprecated. Use Upstash via Marketplace. | `@upstash/redis`. |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **NCNN inference** | ONNX Runtime + ARM NEON INT8 | If NCNN export breaks on a future YOLO upgrade; ONNX is the more universal path. |
| **Pi 5 CPU** | Hailo-8L AI HAT (13 TOPS) | TRL-7 multi-camera or higher-res (1080p @ 30 FPS). Not worth it for v1. |
| **RAK3172 breakout** | Heltec ESP32-LoRa V3 | If you want onboard MCU for sleep-mode aggregation (no Pi needed). Overkill — your sensor has a Pi anyway. |
| **TTN Community v3** | Self-hosted ChirpStack on UCD VPS | Commercial deployment with >100 sensors, or if TTN community SLA becomes a blocker. |
| **TTS Community webhook** | TTN MQTT integration | If dashboard needs sub-second latency on uplinks (you don't). |
| **postgres.js + `attachDatabasePool`** | `@neondatabase/serverless` HTTP driver | If you move route handlers to Edge runtime (you shouldn't). |
| **Auth.js v5 beta** | Clerk / Lucia | Clerk is heavier; Lucia is DIY. Auth.js handles your Google-only allowlist flow cleanly. |
| **Upstash Ratelimit** | Vercel Functions built-in rate limiting | Vercel's built-in is cruder (per-IP, no sliding window). Upstash is more flexible. |
| **Recharts for time series** | Visx / D3 / uPlot | uPlot wins on large datasets (>10 k points). Recharts is enough for your 7-day × 15-min = 672 points. |

---

## Stack Patterns by Variant

**If TTN Dublin coverage fails:**
- Add TTIG EU868 indoor gateway (€90) at the UCD deployment site.
- Still use TTN Community (just as a public network server with your own gateway contributing back).
- Do not self-host ChirpStack unless you have multi-site rollout beyond v1.

**If NCNN FPS comes in below 5 on your actual hardware:**
- Drop `imgsz` from 640 to 480 — expect 10–12 FPS (stock Ultralytics benchmark).
- Increase `frame_skip` in `configs/sensor.yaml` (tracker handles skipped frames).
- Consider YOLO26n (~15 % faster) *after* demo.
- Hailo-8L becomes justified *only* if the sensor needs 1080p full-FPS inference.

**If Neon connection count issues appear:**
- Drop `max: 5` to `max: 2` in postgres.js config.
- Confirm `attachDatabasePool` is present.
- Check Neon dashboard for idle connections during Rolling Release window.

**If LoRa + HTTPS `both` mode risks duplicate DB writes:**
- Keep the `(sensor_id, window_start, class_name)` PK that already dedupes.
- Send a `transport` field in the payload so audit can tell which path delivered.

---

## Version Compatibility Matrix

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `ultralytics@8.3.x` | `torch>=2.0,<2.8`, Python 3.10–3.12 | Python 3.13 works but newer; stay on 3.11 for Pi 5. |
| `picamera2` | libcamera 0.2+, Python 3.11+, Raspberry Pi OS Bookworm | Pre-installed on Pi OS Bookworm. Do not attempt on Bullseye. |
| `postgres@^3.4.5` | Drizzle `^0.36.x`, Neon pooled endpoint, Node 20+ | **Must** set `prepare: false` for Neon pooler. |
| `@vercel/functions` | Next.js 15+ on Fluid Compute | Not needed on Edge runtime (don't use Edge anyway). |
| `drizzle-orm@0.36` | `drizzle-kit@0.29`, Postgres 14+ | Your Neon is PG 16. Compatible. |
| `maplibre-gl@4.7` | React 18/19, Tailwind 3/4 | Incompatible with Turbopack clustering workers — you don't cluster, so OK. |
| `next@16` | React 19, Node 20.11+ | Keep `reactStrictMode: false` until MapLibre init is ref-guarded. |
| `@auth/core@0.x` (via next-auth) | Next.js 15/16 App Router | Beta but stable for Google-only flow. |
| RAK3172 firmware | LoRaWAN 1.0.3 / 1.1 | Use 1.0.3 for TTN Community compat. |

---

## Installation — Concrete Commands

**Pi edge (Raspberry Pi OS Bookworm, Pi 5 8GB):**

```bash
# System packages
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera \
                    python3-venv libatlas-base-dev

# Venv (uv-compatible; matches your global preference)
python3 -m venv /opt/camina/venv
source /opt/camina/venv/bin/activate

# Python deps (Pi-specific variant of requirements.txt)
pip install --upgrade pip
pip install ultralytics==8.3.123 \
            opencv-python-headless==4.11.0.86 \
            filterpy==1.4.5 scipy==1.15.2 \
            httpx pydantic>=2.5 PyYAML>=6.0 \
            systemd-watchdog

# Optional LoRa
pip install pyserial

# Install systemd unit
sudo cp deploy/systemd/camina-sensor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camina-sensor
```

**Dashboard (additions to existing):**

```bash
cd dashboard

# Critical for Fluid Compute pool lifecycle
pnpm add @vercel/functions

# Rate limiting
pnpm add @upstash/ratelimit @upstash/redis

# Observability
pnpm add @sentry/nextjs @vercel/analytics @vercel/speed-insights
```

**LoRa (end-device, once hardware arrives):**

```bash
# Minicom to flash / test RAK3172 AT firmware
sudo apt install minicom
minicom -D /dev/ttyUSB0 -b 115200
# Flash latest RUI3 firmware per RAK docs
# Python side uses pyserial directly
```

---

## Sources (HIGH confidence unless noted)

### Pi Edge
- Ultralytics YOLO docs (via Context7): https://docs.ultralytics.com/guides/raspberry-pi/ — NCNN export, picamera2 integration, Pi 5 benchmarks
- LearnOpenCV YOLO11 on Raspberry Pi (2026): https://learnopencv.com/yolo11-on-raspberry-pi/
- Nature Scientific Reports 2026 — YOLO edge efficiency: https://www.nature.com/articles/s41598-026-46453-6
- PyTorch Real Time Inference on Raspberry Pi tutorial: https://docs.pytorch.org/tutorials/intermediate/realtime_rpi.html
- Raspberry Pi AI Kit (Hailo): https://www.raspberrypi.com/products/ai-kit/ — evaluated, not recommended for v1
- systemd watchdog best practice 2026: https://oneuptime.com/blog/post/2026-03-04-systemd-service-watchdogs-auto-restart-rhel-9/view

### LoRaWAN
- RAK3172 datasheet: https://docs.rakwireless.com/product-categories/wisduo/rak3172-evaluation-board/datasheet/ (HIGH)
- TTN EU868 regional parameters: https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/eu868/ (HIGH)
- TTN Dublin community: https://www.thethingsnetwork.org/community/dublin/ (MEDIUM — coverage claims need on-site verification)
- ChirpStack vs TTN comparison: https://store.rokland.com/blogs/news/chirpstack-vs-ttn-the-things-network (MEDIUM)
- TTIG EU868 gateway: https://www.thethingsnetwork.org/docs/gateways/thethingsindoor/ (HIGH)

### Cloud
- Vercel Functions API docs (via Context7): https://vercel.com/docs/functions/functions-api-reference/vercel-functions-package — `attachDatabasePool` is authoritative
- Neon + Drizzle guide: https://neon.com/docs/guides/drizzle (HIGH)
- Neon Vercel connection methods: https://neon.com/docs/guides/vercel-connection-methods (HIGH)
- Vercel connection pooling with functions: https://vercel.com/kb/guide/connection-pooling-with-functions (HIGH)
- Drizzle PostGIS guide: https://orm.drizzle.team/docs/guides/postgis-geometry-point (HIGH)
- Next.js 16 cacheComponents docs: https://nextjs.org/docs/app/api-reference/config/next-config-js/cacheComponents (HIGH)
- Next.js 16 Turbopack + MapLibre issue: https://github.com/vercel/next.js/issues/86495 (HIGH — current known issue)
- Vercel Rolling Releases: https://vercel.com/docs/rolling-releases (HIGH)
- Sentry Next.js 2026 setup: https://blog.sentry.io/setting-up-next-js-source-maps-sentry/ (HIGH)
- Protomaps PMTiles docs: https://docs.protomaps.com/pmtiles/ (HIGH)
- Upstash Ratelimit Vercel guide: https://upstash.com/blog/edge-rate-limiting (HIGH)

---

*Stack research for: CAMINA brownfield TRL-6 milestone*
*Researched: 2026-04-23*
