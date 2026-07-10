# Plan 01 — Windowed Counter + HTTPS Ingest + Daily Reconciliation

**Branch:** `main`
**Status:** Draft — awaiting approval before implementation
**Owner:** Tiago Tamagusko
**Created:** 2026-04-21 (revised to HTTPS 2026-04-21)

> **History:** this plan previously specified MQTT pub/sub. It was revised to plain HTTPS POST because our scale (≤ ~500 devices, one message per 15 min) does not justify a broker, and the HTTPS stack is fully serverless on Vercel.

---

## 1. Goal

Replace the current cumulative-since-start, file-based logging in `src/camina/app.py` with:

1. **Windowed counting** — per-class unique-ID counts reset at every window boundary (default 15 min, configurable).
2. **HTTPS publishing** — windows are POSTed to the backend as JSON.
3. **Daily cumulative backup** — a per-day running total is persisted on-device and POSTed once per day at 00:00 UTC for reconciliation.
4. **Remote configuration** — the publish interval (and other settings) can be changed from the admin dashboard; device picks up the new config on the next publish via a `config_version` check.
5. **Offline resilience** — if the backend is unreachable, windows are buffered on disk (SQLite) and flushed FIFO when connectivity returns.
6. **Heartbeat** — every 5 min the device POSTs `/heartbeat` with uptime, CPU temp, last window end, and current `config_version` so the backend can detect silent sensors.

The existing SORT tracker (`src/camina/core/tracker.py`) and detector pipeline stay unchanged.

## 2. Non-Goals

- Backend API routes, database schema, admin console, and dashboard UI — covered in Plan 02.
- Over-the-air model updates.
- Re-ID / cross-camera tracking.
- Changes to the detection or tracking algorithms.
- Removal of the local `.log` file — kept behind a flag for one milestone, removed in a later plan.

## 3. Design Decisions

### 3.1 Windowed counting (Option A)

- At each window boundary, `WindowedCounter.snapshot_and_reset()` returns the per-class count and clears the internal `seen_track_ids` set.
- Windows align to wall clock (e.g., 10:00, 10:15, 10:30 UTC).
- First window after startup is partial: publish it with `"partial": true` so the backend can handle it.

### 3.2 Daily cumulative backup

- A `DailyAccumulator` holds per-class totals since 00:00 UTC.
- Persisted to SQLite (`state.db`, table `daily_totals`) after every window so reboots never lose more than one window.
- POSTed at 00:00 UTC to `/v1/sensors/{id}/daily`, then the in-memory row resets.
- If the device misses 00:00 (power cut), on next boot it POSTs the stale row with `"late": true` before starting the new day.

### 3.3 HTTPS API (device → backend)

Base URL from config, e.g. `https://camina.ucd.ie/api/ingest`.

| Method | Path | Purpose | Response |
|---|---|---|---|
| POST | `/v1/sensors/{id}/counts`   | Windowed counts | `{ ok, latest_config_version }` |
| POST | `/v1/sensors/{id}/daily`    | Daily cumulative | `{ ok, latest_config_version }` |
| POST | `/v1/sensors/{id}/heartbeat`| Status + telemetry | `{ ok, latest_config_version }` |
| GET  | `/v1/sensors/{id}/config`   | Fetch latest config | config JSON + `config_version` |

Every write returns `latest_config_version`. If it differs from the device's current `config_version`, the device fetches `/config` and hot-reloads. Config propagation latency is therefore bounded by the publish interval (≤ 15 min by default).

### 3.4 Auth

- **Bearer token** per device in `Authorization: Bearer <token>` header.
- TRL 5 lab: opaque token from config (rotated manually via SSH).
- TRL 6+: short-lived JWT signed by a per-device key; device refreshes via a `/v1/sensors/{id}/token` endpoint (out of scope for v1, added later).
- All traffic over TLS 1.2+.

### 3.5 Payload schemas

**`/counts`:**
```json
{
  "schema_version": "1.0",
  "sensor_id": "cam-dub-01",
  "window_start": "2026-04-21T10:00:00Z",
  "window_end":   "2026-04-21T10:15:00Z",
  "partial": false,
  "counts": {"person":68,"cyclist":91,"e-scooter":22,"car":310,
             "SUV":85,"motorcyclist":18,"bus":0,"delivery_van":55,"truck":43},
  "avg_speed_kmh": {"person":4.1,"cyclist":18.3,"car":32.7},
  "config_version": "abc123",
  "fw_version": "0.2.0",
  "produced_at": "2026-04-21T10:15:00.342Z"
}
```

**`/daily`:**
```json
{
  "schema_version": "1.0",
  "sensor_id": "cam-dub-01",
  "day":        "2026-04-21",
  "totals":     {"person":6421,"cyclist":8733,"...":"..."},
  "window_count": 96,
  "late": false,
  "config_version": "abc123",
  "fw_version": "0.2.0",
  "produced_at": "2026-04-22T00:00:00.021Z"
}
```

**`/heartbeat`:**
```json
{
  "sensor_id": "cam-dub-01",
  "ts": "2026-04-21T10:20:00Z",
  "uptime_s": 88231,
  "cpu_temp_c": 52.4,
  "last_window_end": "2026-04-21T10:15:00Z",
  "config_version": "abc123",
  "fw_version": "0.2.0"
}
```

**`/config` response (GET):**
```json
{
  "config_version": "def456",
  "publish_interval_minutes": 15,
  "heartbeat_interval_minutes": 5,
  "daily_publish_time_utc": "00:00",
  "detection_zone": {"type":"polygon","points":[[x1,y1],[x2,y2]]},
  "frame_skip": 5,
  "min_track_hits": 3
}
```

### 3.6 Offline buffer

- SQLite file `state.db`, table `outbox(id, endpoint, payload, enqueued_at, attempts)`.
- On any HTTP failure (connection error, 5xx, 408, 429): enqueue.
- On next success: drain FIFO, max 50 per cycle to avoid long stalls.
- Size-capped at 10 000 messages (~10 days of 15-min windows + heartbeats). Beyond cap: drop oldest, increment `messages_dropped` metric, log WARN.

### 3.7 Failure handling matrix

| Failure mode | Detection | Device action | Data loss |
|---|---|---|---|
| No network / DNS / TLS / timeout | `httpx.ConnectError`, `ReadTimeout` | Exp. backoff 1 s→60 s; if still failing → enqueue in outbox; keep counting. | None until outbox cap (~10 days). |
| Backend 5xx / 408 / 504 | status | Same — retry, then enqueue. | None in normal durations. |
| Rate-limited (429) | status + `Retry-After` | Respect `Retry-After`; enqueue if persists. | None. |
| Auth failure (401 / 403) | status | **No retry.** Log ERROR, set `auth_error=true` on next heartbeat. Admin rotates token. | Only after token truly revoked; daily payload still reconciles once fixed. |
| Bad payload (400) | status | **No retry.** Move to local dead-letter table; log; continue. | Just that one window; daily covers it. |
| Unknown sensor (404) | status | Same as auth failure; admin must register. | Same as auth. |
| Outbox > 10 000 msgs (offline > ~10 days) | size check | Drop-oldest; increment `messages_dropped`. | Old 15-min windows lost — **daily cumulative still preserves totals**. |
| Device reboot mid-publish | next boot | WAL-mode SQLite restores outbox; drain on boot. | None. |
| Power cut across 00:00 UTC | next boot detects unpublished row | Publish with `"late": true`. | None. |
| Clock drift (no NTP) | backend compares `produced_at` vs server time | Backend corrects ordering; big drifts flagged in reconciliation | None; shows as audit entry. |
| Backend stores corruptly | daily reconciliation sum mismatch | `sensor_daily_totals.reconciled=false`; admin event. | Detectable; manual replay tool. |
| Duplicate delivery after retry | backend PK `(sensor_id, window_start, class_name)` | `INSERT ... ON CONFLICT DO NOTHING`. | None — idempotent. |

Two invariants make this work:

- **Backend idempotency:** every ingest row has a natural PK; replays are no-ops.
- **Daily payload as safety net:** even if 15-min windows are lost, the daily cumulative keeps totals correct.

### 3.8 Remote config hot-reload

- `ConfigPoller` compares `latest_config_version` from any POST response to the currently applied version.
- On mismatch: GET `/config`, validate with pydantic, apply via thread-safe setters on `WindowedCounter` / app, persist new `config_version` to SQLite.
- On validation failure: keep previous config, log error, surface via next heartbeat (`"config_error": true`).

## 4. Module Layout

```
src/camina/
├── core/
│   ├── tracker.py              (unchanged)
│   └── counter.py              NEW — WindowedCounter + DailyAccumulator
├── io/                         NEW package
│   ├── __init__.py
│   ├── http_client.py          shared httpx.AsyncClient with retries + backoff
│   ├── https_publisher.py      POST /counts, /daily, /heartbeat
│   ├── config_poller.py        version check + GET /config + hot-reload
│   ├── offline_buffer.py       SQLite FIFO outbox
│   └── schemas.py              pydantic models + JSON schemas
├── utils/                      (unchanged)
└── app.py                      MODIFIED — uses WindowedCounter + HttpsPublisher

configs/
└── sensor.yaml                 NEW / extended — api_base_url, sensor_id, bearer token, defaults

tests/
├── test_windowed_counter.py    NEW
├── test_daily_accumulator.py   NEW
├── test_offline_buffer.py      NEW
├── test_https_publisher.py     NEW (respx / httpx.MockTransport)
└── test_config_poller.py       NEW
```

## 5. On-Device Data Model (SQLite `state.db`)

```sql
CREATE TABLE daily_totals (
  day           TEXT PRIMARY KEY,     -- 'YYYY-MM-DD'
  totals_json   TEXT NOT NULL,
  window_count  INTEGER NOT NULL,
  published     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE outbox (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint      TEXT NOT NULL,        -- 'counts' | 'daily' | 'heartbeat'
  payload       BLOB NOT NULL,        -- JSON bytes
  enqueued_at   INTEGER NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_outbox_enqueued ON outbox(enqueued_at);

CREATE TABLE sensor_meta (
  key           TEXT PRIMARY KEY,
  value         TEXT NOT NULL
);  -- fw_version, config_version, last_config_hash, etc.
```

## 6. Implementation Steps

Each step is independently shippable. Tree stays green after every commit.

### Step 1 — `WindowedCounter` (pure, no I/O)
- **Files:** `src/camina/core/counter.py` (new); `tests/test_windowed_counter.py` (new).
- **API:** `WindowedCounter(classes, window_seconds, anchor)`, `.add(track_id, class, now)`, `.maybe_rollover(now) -> Optional[WindowSnapshot]`, `.force_snapshot(now)`.
- **Verify:** duplicate `(track_id, class)` within a window counted once; same `track_id` across windows counted per-window; boundaries align to wall clock; `partial=True` only on first post-startup window.

### Step 2 — `DailyAccumulator` + SQLite persistence
- **Files:** extend `src/camina/core/counter.py`; `tests/test_daily_accumulator.py`.
- **API:** `.add_window(snapshot)`, `.maybe_rollover(now) -> Optional[DailySnapshot]`, `.pending_unpublished()`, `.mark_published(day)`.
- **Verify:** crossing 00:00 UTC triggers rollover; reboot mid-day preserves totals; late publication on next boot.

### Step 3 — `OfflineBuffer` (SQLite FIFO outbox)
- **Files:** `src/camina/io/offline_buffer.py`, `src/camina/io/__init__.py`, `tests/test_offline_buffer.py`.
- **API:** `.enqueue(endpoint, payload)`, `.drain(send_fn, max=50) -> int`, `.stats()`.
- **Verify:** size cap, FIFO order, concurrent access.

### Step 4 — `HttpClient` + `HttpsPublisher`
- **Files:** `src/camina/io/http_client.py`, `src/camina/io/https_publisher.py`, `tests/test_https_publisher.py`.
- **Dependency:** `httpx>=0.27` (add to `requirements.txt`).
- **Features:** shared `httpx.Client` with connection pooling, TLS verification, Bearer auth, idempotency key on POSTs, exponential-backoff retry (1 s → 60 s) on 5xx / 408 / 429 / connection errors. On success, returns `(status, latest_config_version)`.
- **Verify:** mock transport tests covering success, 5xx retry, 4xx no-retry, connection error, rate-limit respect of `Retry-After`.

### Step 5 — `ConfigPoller`
- **Files:** `src/camina/io/config_poller.py`, `src/camina/io/schemas.py`, `tests/test_config_poller.py`.
- **Dependency:** `pydantic>=2.5`.
- **Behaviour:** after every POST, compares returned `latest_config_version` to current. If different, GET `/config`, validate, apply, persist. On validation failure, keep previous + flag error.
- **Verify:** tests cover mismatch → GET fires; invalid response → previous config retained; applied new config → setters invoked.

### Step 6 — Wire into `app.py`
- **Files:** `src/camina/app.py` (modify); `configs/sensor.yaml` (new/extend).
- **Changes:**
  - Replace `seen_ids` / `counts` dicts with `WindowedCounter`.
  - On every accepted tracked detection: `counter.add(...)`.
  - Per frame: `snap = counter.maybe_rollover(now)`; if snap: `publisher.post_counts(snap)` + `daily.add_window(snap)`.
  - Per frame: `daily_snap = daily.maybe_rollover(now)`; if daily_snap: `publisher.post_daily(daily_snap)`.
  - Scheduled task: publisher posts heartbeat every 5 min.
  - On every publisher response, call `config_poller.check(version)`.
  - Keep `DataLogger` behind `logging.local_file` flag (default on for this milestone).
- **Verify:** end-to-end smoke against a stub server (`pytest-httpserver`); observe three POSTs/heartbeats over 30 min of synthetic video.

### Step 7 — Packaging & ops
- **Files:** `requirements.txt`, `deploy/systemd/camina-sensor.service`, `docs/sensor_deployment.md`.
- **Verify:** systemd unit starts, restarts on crash, logs to journald; install steps reproduce on a fresh RPi5.

### Step 8 — Documentation
- Update `README.md` with the HTTPS architecture diagram.
- Add `docs/PROTOCOL.md` describing endpoints, payloads, schema versioning, idempotency, error handling.
- Add `docs/RECONCILIATION.md` describing daily-vs-windowed check.

## 7. Dependencies to Add

```txt
httpx>=0.27
pydantic>=2.5
```

(Drop `paho-mqtt`.)

## 8. Test Strategy

- Unit tests for `WindowedCounter`, `DailyAccumulator`, `OfflineBuffer`, `HttpsPublisher`, `ConfigPoller`.
- **Integration** against `pytest-httpserver`:
  - 100 windows over simulated time → exactly 100 POSTs to `/counts`.
  - Server returns 503 for 2 min → outbox fills; server recovers → outbox drains in FIFO.
  - Server returns 200 with `latest_config_version = new`; next tick, GET `/config` fires and new interval applies.
  - Rate-limit (429 with `Retry-After`) honoured.
- Target coverage: 80 %+ on new modules.

## 9. Verification Checklist (per CLAUDE.md §4)

- [ ] `mypy src/camina/` passes
- [ ] `ruff check src/camina/ tests/` passes
- [ ] `pytest tests/` green
- [ ] Manual: webcam demo POSTs to local stub; logs show counts + heartbeats
- [ ] Manual: stub returns 503; outbox grows; stub recovers; outbox drains FIFO
- [ ] Manual: stub advertises new `config_version`; GET `/config` fires; device applies without restart
- [ ] Reconciliation: sum of 15-min counts equals the daily payload for a simulated day

## 10. Rollout Plan

1. Implement Steps 1–6 behind `use_https: false` feature flag.
2. Deploy to one sensor in dual-mode (local file logger + HTTPS).
3. Run 7 days, daily reconciliation check.
4. Flip flag to `use_https: true`, keep file logger one more week.
5. Remove file logger (separate small PR).

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Backend briefly unavailable (deploys, DB maintenance) | Medium | Low | Outbox + exponential retry; Vercel Rolling Releases minimize downtime |
| Backend rate-limiting under fleet growth | Low | Medium | Honour `Retry-After`; stagger device start times; cap per-device retry concurrency |
| SQLite corruption after power loss | Low | Medium | WAL mode; `PRAGMA synchronous=NORMAL`; daily `PRAGMA integrity_check` |
| Clock drift on RPi5 (no RTC) | Medium | Medium | NTP required at boot; `produced_at` lets backend correct ordering |
| Bearer token leak | Low | High | TLS everywhere; rotate on compromise; TRL 6+ moves to short-lived JWT |
| Config JSON breaks device | Low | High | Pydantic validation + fallback to last-known-good + heartbeat error flag |
| Duplicate posts after retry | Medium | Low | Backend deduplicates on `(sensor_id, window_start, endpoint)` primary keys |

## 12. Decisions

- [x] **Transport:** HTTPS POST (dropped MQTT after scale review).
- [x] **Daily boundary:** UTC 00:00. Dashboard converts to local time for display only.
- [x] **Heartbeat interval:** 5 min.
- [x] **Auth:** opaque Bearer token at TRL 5; short-lived JWT from TRL 6+.
- [x] **Offline buffer cap:** 10 000 messages (~10 days).
- [x] **Retry policy:** exponential backoff 1 s → 60 s; honour `Retry-After`; dead-letter never (drop-oldest when cap hit).

## 13. Estimated Effort

| Step | Estimate |
|---|---|
| 1. `WindowedCounter` + tests | 0.5 d |
| 2. `DailyAccumulator` + tests | 0.5 d |
| 3. `OfflineBuffer` + tests | 0.5 d |
| 4. `HttpClient` + `HttpsPublisher` + tests | 1.0 d |
| 5. `ConfigPoller` + tests | 0.5 d |
| 6. Wire into `app.py` + stub-server smoke test | 1.0 d |
| 7. Packaging (systemd, docs) | 0.5 d |
| 8. README / PROTOCOL / RECONCILIATION docs | 0.5 d |
| **Total** | **~5 days** |

---

**Next action after approval:** Step 1 — `src/camina/core/counter.py` with `WindowedCounter` + unit tests. `app.py` stays untouched until Step 6.
