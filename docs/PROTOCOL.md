# CAMINA Ingest Protocol

Version: 1.1

This document specifies the wire protocol between a CAMINA edge sensor and
the backend. The protocol is plain HTTPS with Bearer-token auth — no MQTT, no
persistent connection. Rationale and alternatives are discussed in
`plan/01-windowed-counter-and-ingest.md`.

## 1. Base URL

    https://{HOST}

All paths below are relative to that base. TLS 1.2 or newer is required.

## 2. Authentication

    Authorization: Bearer <per-device-token>

Tokens are provisioned by the admin console at sensor-creation time and
stored on the device as part of `configs/sensor.yaml`. They are opaque to
the device. Token rotation is performed by the admin UI.

## 3. Idempotency

Every write carries an `Idempotency-Key` header (UUIDv4). The backend
MUST deduplicate based on the natural primary keys listed in
`plan/02-dashboard-vercel.md` §8:

- `/counts` → `(sensor_id, window_start, class_name)`
- `/daily`  → `(sensor_id, day)`
- `/heartbeat` → `(sensor_id, ts)` (or latest-wins, implementation choice)

## 4. Endpoints

### 4.1 `POST /api/ingest/sensors/{id}/counts`

Windowed per-class counts produced by `WindowedCounter.maybe_rollover`.

**Request body**:

    {
      "schema_version": "1.1",
      "sensor_id": "cam-dub-01",
      "window_start": "2026-04-21T10:00:00Z",
      "window_end":   "2026-04-21T10:15:00Z",
      "partial": false,
      "counts": {"person": 68, "cyclist": 91, "car": 310},
      "counts_by_direction": {
        "AB": {"person": 40, "cyclist": 51, "car": 170},
        "BA": {"person": 28, "cyclist": 40, "car": 140}
      },
      "avg_speed_kmh": {"person": 4.1, "cyclist": 18.3, "car": 32.7},
      "config_version": "abc123",
      "fw_version": "0.2.0",
      "produced_at": "2026-04-21T10:15:00.342Z"
    }

`counts_by_direction` is optional. A sensor using a screenline sends it and
sets `schema_version` to `"1.1"`; a sensor using movement mode omits it and
continues to send `"1.0"`. Its only allowed direction keys are `AB` and `BA`,
and its inner keys use the same road-user classes and integer range (0–65535)
as `counts`. For every class, a missing direction cell counts as zero and
`AB + BA` MUST equal `counts[class]`. The backend rejects violations with 400.
`avg_speed_kmh` remains per class rather than per direction.

The edge sends raw measured window counts, direction cells, daily totals, and
average speeds to its authenticated server. It does not apply `k_min` on the
wire. The dashboard applies `k_min = 5` at public API read time, after summing
the relevant windows, so small per-window cells contribute to larger displayed
aggregates. The edge sends an average speed for every class it measured; the
server hides that speed when the class count in the displayed bucket is below 5.

Hiding a cell is not enough when the values around it add up to it, so the
public API also applies complementary suppression (rules and reasoning in
`dashboard/src/lib/privacy.ts`): if either direction cell of a class is hidden,
both are hidden, and so are both when some rows of the class in the bucket have
no direction cells; a street total is the sum of the published class counts
only, with `hasHidden: true` when any class was hidden. A published number is
always the sum of the published numbers beneath it.

**Response 200**:

    { "ok": true, "latest_config_version": "abc123" }

### 4.2 `POST /api/ingest/sensors/{id}/daily`

Per-day cumulative totals published at 00:00 UTC, or on next boot with
`"late": true` if the device missed the boundary.

**Request body**:

    {
      "schema_version": "1.0",
      "sensor_id": "cam-dub-01",
      "day": "2026-04-21",
      "totals": {"person": 6421, "cyclist": 8733, "...": 0},
      "window_count": 96,
      "late": false,
      "config_version": "abc123",
      "fw_version": "0.2.0",
      "produced_at": "2026-04-22T00:00:00.021Z"
    }

### 4.3 `POST /api/ingest/sensors/{id}/heartbeat`

Observability signal emitted every ~5 min regardless of counts activity.

    {
      "sensor_id": "cam-dub-01",
      "ts": "2026-04-21T10:20:00Z",
      "uptime_s": 88231,
      "cpu_temp_c": 52.4,
      "last_window_end": "2026-04-21T10:15:00Z",
      "config_version": "abc123",
      "fw_version": "0.2.0",
      "auth_error": false,
      "config_error": false,
      "outbox_depth": 12,
      "outbox_dropped_total": 3
    }

### 4.4 `GET /api/ingest/sensors/{id}/config`

Returns the latest configuration the backend wants the device to apply.
The device fetches this lazily — only when a previous ingest response
advertises a `latest_config_version` different from the one currently
applied.

**Response 200**:

    {
      "config_version": "def456",
      "publish_interval_minutes": 15,
      "heartbeat_interval_minutes": 5,
      "daily_publish_time_utc": "00:00",
      "detection_zone": null,
      "frame_skip": 1,
      "min_track_hits": 3
    }

The device applies `publish_interval_minutes`, `heartbeat_interval_minutes`
and `min_track_hits` (the tracker's confirmation count), and saves the applied
config next to its `state.db` so a reboot keeps it. This firmware rejects, with
a logged warning, a `frame_skip` other than 1 (detection runs on every frame),
a `daily_publish_time_utc` other than `"00:00"` (daily totals roll over at
midnight UTC) and a non-null `detection_zone` (counting uses the screenline in
the local sensor config); the rest of the config still applies.

## 5. Status codes

| Code | Meaning for the device |
|---|---|
| 200 | Accepted. Read `latest_config_version` from the body. |
| 202 | Accepted, processing async (device treats identical to 200). |
| 400 | Bad payload — **do not retry**; dead-letter locally. |
| 401 / 403 | Auth failure — **do not retry**; surface in next heartbeat `auth_error=true`; admin must rotate the token. |
| 404 | Unknown sensor — same as 401. |
| 422 | Timestamp outside the server's window (counts `window_end`, heartbeat `ts`, daily `produced_at`; see §7). Body `{"error": "timestamp_in_future"}`: the device clock is fast — **keep the row** in the outbox, do not charge an attempt, log the clock skew, retry later. Body `{"error": "timestamp_too_old"}` or `"invalid_timestamp"`: permanent — drop the row. |
| 408 / 425 / 429 / 5xx | Retry with exponential backoff (1 s → 60 s). Honour `Retry-After` on 429. |

## 6. Offline handling

When a write fails after exhausting retries, the device enqueues the payload
to a local SQLite outbox. On the next successful request, the device drains
up to 50 outbox rows in FIFO order before sending the fresh payload. The
outbox is capped (default 10 000 rows); beyond the cap the oldest rows are
dropped and a counter is surfaced in heartbeats. Heartbeats may include the
nonnegative integer fields `outbox_depth` (currently queued rows) and
`outbox_dropped_total` (rows dropped by the cap or permanently rejected during
drain). The dashboard validates these fields but does not persist them in this
branch.

## 7. Clock

- All timestamps are ISO-8601 with an explicit `Z` UTC suffix.
- The device requires NTP at boot. `produced_at` lets the backend detect and
  correct ordering when wall-clock drift occurs.
- The server rejects with 422 a counts `window_end`, heartbeat `ts` or daily
  `produced_at` more than 60 s ahead of its own clock (`timestamp_in_future`)
  or more than 10 days behind it (`timestamp_too_old`). A fast device clock
  therefore stops counts, dailies and heartbeats: the server sees the sensor go
  silent, and the device keeps its counts and dailies buffered and logs the
  skew until the clock is corrected (`HttpsPublisher.clock_skew`). A row is
  accepted once server time reaches its timestamp minus 60 s, and dropped once
  it is more than 10 days old.

## 8. Forward compatibility

Payloads carry `schema_version` (current counts versions are `"1.0"` and
`"1.1"`). The backend MUST
accept minor-version bumps that add optional fields without breaking older
devices. Major-version bumps are coordinated via config rollout followed by
firmware update.
