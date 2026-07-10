# Dublin 8-Sensor Simulation Mode

This document describes the mock Dublin sensor network produced by
`scripts/generate_mock_dublin.py`. The generator writes deterministic JSON
fixtures to `data/mock/dublin/`, which the dashboard reads directly when
`DATA_SOURCE=mock` (via `dashboard/src/lib/mock-loader.ts`). No database, no
live edge devices, and no network are required — the simulation exists so the
dashboard can be developed and demoed against realistic, reproducible data.

## What the simulation is

Eight virtual CAMINA sensors are placed on real Dublin streets across two
zones — the **UCD Belfield campus** and the **city-centre → UCD access
corridor**. Each sensor produces 14 days of 15-minute count windows
(UTC-aligned, `WINDOW_MINUTES = 15`) with plausible diurnal traffic shapes,
per-transport reporting reliability, heartbeats (WiFi/cellular only), and daily
rollups. Everything is seeded (`SEED = 20260421`) so re-running the generator
reproduces byte-identical fixtures.

The simulation also exercises a **reference implementation of the planned
Phase-4 LoRaWAN 17-byte codec** to prove the payload fits the 200-character
LoRa cap — see [LoRa reference packer](#lora-reference-packer).

## Sensor table

| ID | Location | Coords (lat, lon) | Zone | Transport |
|----|----------|-------------------|------|-----------|
| `cam-dub-01` | UCD Stillorgan Road Entrance | 53.30670, -6.22420 | ucd | lora |
| `cam-dub-02` | UCD Wynnsward Drive / Clonskeagh Entrance | 53.30980, -6.22800 | ucd | lora |
| `cam-dub-03` | N11 Belfield Flyover | 53.30500, -6.22350 | ucd | wifi |
| `cam-dub-04` | UCD Foster's Avenue Entrance | 53.30290, -6.22140 | ucd | cellular |
| `cam-dub-05` | Leeson Street Lower | 53.33320, -6.25230 | corridor | lora |
| `cam-dub-06` | Morehampton Road, Donnybrook | 53.32530, -6.23850 | corridor | lora |
| `cam-dub-07` | N11 Stillorgan Road at RTE / Montrose | 53.31720, -6.22960 | corridor | wifi |
| `cam-dub-08` | Ranelagh Road | 53.32550, -6.25550 | corridor | cellular |

Transport split per zone: **UCD** = 2 LoRa + 1 WiFi + 1 cellular; **corridor**
= 2 LoRa + 1 WiFi + 1 cellular. Network total: **4 LoRa, 2 WiFi, 2 cellular**.

Coordinates are the midpoint of a compact 2-point street polyline (in
`streets.json` / `streets.geojson`); precise OSM geometry will come from the
admin draw tool in production. The `transport` field lives **only** in
`sensors.json` metadata (dashboard-internal, admin-only). It is deliberately
**not** added to any ingest payload validated by
`dashboard/src/lib/schemas.ts` (counts, daily, heartbeat) — those strict zod
schemas remain untouched.

### Traffic character

- **UCD sensors** skew pedestrian / cyclist / e-scooter heavy and get sharpened
  weekday AM (~08:30) and PM (~17:30) commuter peaks (campus mobility).
- **Corridor sensors** skew car / bus / freight heavy (arterial commuter
  traffic).

The 9-class taxonomy is `person, cyclist, car, e-scooter, SUV, motorcyclist,
bus, delivery_van, truck`, kept in sync with the dashboard's
`ROAD_USER_CLASSES` (`dashboard/src/lib/types.ts`).

## Per-transport reporting patterns

Each transport reports every 15-min window except for injected gaps, which
model real-world reliability differences:

| Transport | Missing windows | Heartbeats | Notes |
|-----------|-----------------|------------|-------|
| **WiFi** (2) | ~0.5% (isolated) | yes (every 5 min, last 24 h) | Brief WiFi/HTTPS outages. |
| **Cellular** (2) | ~1.5% (isolated) | yes (every 5 min, last 24 h) | HTTPS over a cellular bearer; identical payloads to WiFi. `produced_at` latency jitter up to +90 s (see caveat below). |
| **LoRa** (4) | ~4% (isolated + 1–2 window bursts) | **none** | TTN uplink loss. LoRa sensors emit counts only, so they have no heartbeat rows and `last_heartbeat = null`. |

Gaps are deterministic per sensor (seeded independently of the count stream).
Daily rollups (`sensor_daily_totals.json`) reflect gaps via a reduced
`window_count` (< 96 on affected days).

### Cellular `produced_at` latency caveat

The cellular latency jitter (up to +90 s) is an **ingest-time** property that
would appear on the `produced_at` field of the counts payload. The DB-shaped
`sensor_readings.json` fixture has **no `produced_at` column** (that field
exists only in the ingest `countsPayload`, not in stored readings), so the
jitter is documented here but not materialised in the fixture. Cellular is
otherwise byte-for-byte identical to WiFi in the fixtures; the only observable
difference is the slightly higher missing-window rate.

## LoRa reference packer

`pack_lora_reference(counts, sensor_num, epoch) -> bytes` in the generator is a
**REFERENCE implementation only** of the planned Phase-4 LoRaWAN codec. The
production encoder will live in the edge `LoRaPublisher` (Phase 4); this
function exists so the mock generator can assert the codec fits the LoRa cap.

**17-byte layout:**

| Bytes | Field | Encoding |
|-------|-------|----------|
| 3 | camera id | ASCII `"LNN"` (e.g. `sensor_num=1` → `b"L01"`) |
| 4 | epoch | `uint32` big-endian, UTC seconds |
| 9 | counts | `uint8` per class, `CLASSES` order, clamped to 255 |
| 1 | schema version | `uint8` = 1 |

Total = **17 bytes**. base64 of 17 bytes = **24 characters**, far under the
**200-character** LoRa payload cap.

### 200-char check and 255 saturation caveat

For **every** generated LoRa window the generator packs the counts, base64
-encodes them, and asserts `len(base64) <= 200`. It also records a `saturated`
warning (logged and counted in `meta.json → lora_reference`) whenever any class
count exceeds 255.

**Important:** counts > 255 are clamped to 255 in the **packed reference bytes
only**. The fixture JSON (`sensor_readings.json`, `sensor_daily_totals.json`)
always keeps the **true, unclamped** counts. Saturation is realistic at busy
UCD pedestrian peaks (e.g. `person` counts of 300–425 in a 15-min window) and
signals a real design constraint for the future Phase-4 codec: a `uint8`
per-class field cannot represent more than 255 events per window.

## How to regenerate

```bash
python scripts/generate_mock_dublin.py
```

Output is written to `data/mock/dublin/`:

- `streets.json`, `streets.geojson` — 8 street polylines (public geometry)
- `sensors.json` — 8 sensors incl. admin-only coords + `transport` metadata
- `sensor_street_coverage.json` — 1:1 sensor→street mapping
- `sensor_readings.json` — 15-min count windows (the bulk of the data)
- `sensor_heartbeats.json` — 5-min heartbeats, last 24 h, WiFi/cellular only
- `sensor_daily_totals.json` — per-sensor daily rollups
- `meta.json` — generation metadata incl. `transport_counts`, `gap_stats`, and
  `lora_reference` (windows packed, max b64 length, saturation counts)

The entire `data/` directory is gitignored (`.gitignore` line 17), so
regenerating the fixtures produces **no git changes** — only the generator and
this document are tracked.

## Cellular scope note

Cellular in this simulation is **HTTPS over a cellular bearer**. The edge
publisher is bearer-agnostic (it performs no network-interface checks), so
running CAMINA over cellular requires **no code change** — the existing
`HttpsPublisher` path works unchanged. Cellular therefore remains **out of v1
hardware scope** per `.planning/research/FEATURES.md` ("no cellular" is an
accepted v1 feature gap vs. peers); it is included in the mock only to exercise
the dashboard's handling of a third transport label and a distinct reliability
profile.
