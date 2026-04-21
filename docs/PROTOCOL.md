# CAMINA Ingest Protocol

Version: 1.0

This document specifies the wire protocol between a CAMINA edge sensor and
the backend. The protocol is plain HTTPS with Bearer-token auth — no MQTT, no
persistent connection. Rationale and alternatives are discussed in
`plan/01-windowed-counter-and-ingest.md`.

## 1. Base URL

    https://{HOST}/api/ingest

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

### 4.1 `POST /v1/sensors/{id}/counts`

Windowed per-class counts produced by `WindowedCounter.maybe_rollover`.

**Request body**:

    {
      "schema_version": "1.0",
      "sensor_id": "cam-dub-01",
      "window_start": "2026-04-21T10:00:00Z",
      "window_end":   "2026-04-21T10:15:00Z",
      "partial": false,
      "counts": {"person": 68, "cyclist": 91, "car": 310, "...": 0},
      "avg_speed_kmh": {"person": 4.1, "cyclist": 18.3, "car": 32.7},
      "config_version": "abc123",
      "fw_version": "0.2.0",
      "produced_at": "2026-04-21T10:15:00.342Z"
    }

**Response 200**:

    { "ok": true, "latest_config_version": "abc123" }

### 4.2 `POST /v1/sensors/{id}/daily`

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

### 4.3 `POST /v1/sensors/{id}/heartbeat`

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
      "config_error": false
    }

### 4.4 `GET /v1/sensors/{id}/config`

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
      "detection_zone": {"type": "polygon", "points": [[x1, y1], [x2, y2]]},
      "frame_skip": 5,
      "min_track_hits": 3
    }

## 5. Status codes

| Code | Meaning for the device |
|---|---|
| 200 | Accepted. Read `latest_config_version` from the body. |
| 202 | Accepted, processing async (device treats identical to 200). |
| 400 | Bad payload — **do not retry**; dead-letter locally. |
| 401 / 403 | Auth failure — **do not retry**; surface in next heartbeat `auth_error=true`; admin must rotate the token. |
| 404 | Unknown sensor — same as 401. |
| 408 / 425 / 429 / 5xx | Retry with exponential backoff (1 s → 60 s). Honour `Retry-After` on 429. |

## 6. Offline handling

When a write fails after exhausting retries, the device enqueues the payload
to a local SQLite outbox. On the next successful request, the device drains
up to 50 outbox rows in FIFO order before sending the fresh payload. The
outbox is capped (default 10 000 rows); beyond the cap the oldest rows are
dropped and a counter is surfaced in heartbeats.

## 7. Clock

- All timestamps are ISO-8601 with an explicit `Z` UTC suffix.
- The device requires NTP at boot. `produced_at` lets the backend detect and
  correct ordering when wall-clock drift occurs.

## 8. Forward compatibility

Payloads carry `schema_version` (current value `"1.0"`). The backend MUST
accept minor-version bumps that add optional fields without breaking older
devices. Major-version bumps are coordinated via config rollout followed by
firmware update.
